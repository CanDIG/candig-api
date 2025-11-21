import asyncio
from typing import Dict, Optional

#from pymongo.cursor import Cursor
#from pymongo.collection import Collection
from sqlalchemy import text
from ...beacon.omop import engine
from ...beacon.request.model import RequestParams
import logging
import aiosql
import itertools

LOG = logging.getLogger(__name__)

CDM_SCHEMA='cdm'
VOCABULARIES_SCHEMA='vocabularies'

from pathlib import Path
queries_file = Path(__file__).parent / "sql" / "individuals.sql"
individual_queries = aiosql.from_path(queries_file, "psycopg2")

# Function to know if generator is empty
def peek(iterable):
    try:
        first = next(iterable)
    except StopIteration:
        return None
    return first, itertools.chain([first], iterable)


def search_ontology(concept_id):
    records = individual_queries.sql_get_ontology(engine,
                                                    concept_id=concept_id)
    return records


def search_ontologies(dictValues):
    for person_id, listVariableValues in dictValues.items():    # For each id
        for dictVariableValue in listVariableValues:                        # For each object of the list   
            for variable, value in dictVariableValue.items():                                     
                # If id in variable, extract the label and OntologyId
                if "concept_id" in variable:
                    if value == 0:
                        dictVariableValue[variable] = {'id':"None:No matching concept", 'label':"No matching concept"}
                        continue
                    records = search_ontology(value)
                    if records:
                        label = records[0]
                        id = records[1]
                    else:
                        label = "No matching concept"
                        id = "None:No matching concept"

                    dictVariableValue[variable] = {'id':id, 'label':label}
    return dictValues
        
        
async def basic_query(query: str):
    async with engine.connect() as conn:
        records = await conn.execute(text(query))
        return records


def query_id(query: dict, document_id) -> dict:
    query["id"] = document_id
    return query


def query_ids(query: dict, ids) -> dict:
    query["id"] = ids
    return query


def query_property(query: dict, property_id: str, value: str, property_map: Dict[str, str]) -> dict:
    query[property_map[property_id]] = value
    return query


# Helper function for mongo_filter_to_sql: join e.g. ["$and"]["X", "Y", "Z"] -> "X AND Y AND Z"
def _unroll_condition_list(query: dict, param: str, join_text: str) -> str:
    ret_str = ""
    first = True
    for this_param in query[param]:
        if not first:
            ret_str += join_text
        first = False
        ret_str += _mongo_filter_to_sql(query[param][this_param])
    return ret_str


# Convert the MongoDB-esque filter from the apply_filters() call below to something more SQL-esque
def _mongo_filter_to_sql(query: dict) -> str:
    ret_str = ""
    # The kinds of dictionaries we'll be dealing with:
    # One of:
    #   $and
    #   $or
    #   $not
    #   $regex
    # If none of the above, it'll be a simple dict of PARAMETER = VALUE
    if "$and" in query:
        ret_str +=_unroll_condition_list(query, "$and", " AND ")
    elif "$or" in query:
        ret_str +=_unroll_condition_list(query, "$or", " OR ")
    elif "$not" in query:
        ret_str += "NOT(" + _mongo_filter_to_sql(query["$not"]) + ")"
    elif "$regex" in query:
        ret_str += "REGEXP '" + _mongo_filter_to_sql(query["$regex"]) + "'"
    elif "$text" in query:
        # NB: We aren't handling any of the other parameters available in $text,
        # such as $language or $caseSensitive -- I don't see any references to them in the codebase
        ret_str += _mongo_filter_to_sql(query["$text"]["$search"])
    else:
        if len(query) == 0:
            return ""
        # Should be a dict of size 1, throw an error for debugging if it isn't
        if len(query) != 1:
            LOG.error(f"Expected to only see one element, saw {len(query)} in {query}")
        key = next(iter(query))
        ret_str += f"{key} = {query[key]}"
    return ret_str


def format_mongo_query(database: str, query_params: dict):
    query_str = f"FROM {database}"
    if len(query_params) > 1:
        query_str += " WHERE " + _mongo_filter_to_sql(query_params)
    return query_str


# Overload of get_count to deal with the MongoDB-esque params that we seem to be given
async def get_count(database: str, query_params: dict):
    return await get_count_str(format_mongo_query(database, query_params))


async def get_count_str(query: str) -> int:
    LOG.debug("Returning estimated count")
    queryFinal = "Select count(*) " + query
    LOG.debug(f"FINAL QUERY: {queryFinal}")
    # TODO: Is this use of async going to slow things down?
    records = await basic_query(queryFinal)
    records = records.fetchone()
    LOG.debug(records)
    return records[0]

## TODO: Originally this relied on a function `format_query()`, that did not exist
async def get_documents(listVariables: list, query: str, skip: int, limit: int):
    queryFinal = f"Select {",".join([col.name for col in listVariables])} {query} OFFSET :OFFSET ROWS FETCH NEXT :LIMIT ROWS ONLY"
    LOG.debug(f"FINAL QUERY: {queryFinal}")
    async with engine.connect() as conn:
        # NB: To grab page X of the results, given that they want page size Y we need:
        # - skip X*Y rows
        # - return Y rows after that
        records = await conn.execute(text(queryFinal), {"OFFSET": skip * limit, "LIMIT": limit})
        recordsFinal = records.fetchall() # format_query(listVariables, records)
        return recordsFinal

def get_cross_query(ids: dict, cross_type: str, collection_id: str):
    id_list=[]
    dict_in={}
    id_dict={}
    if cross_type == 'biosampleId' or cross_type=='id':
        list_item=ids[cross_type]
        LOG.debug(str(list_item))
        id_list.append(str(list_item))
        dict_in["$in"]=id_list
        LOG.debug(id_list)
        id_dict[collection_id]=dict_in
        query = id_dict
    elif cross_type == 'individualIds' or cross_type=='biosampleIds':
        list_individualIds=ids[cross_type]
        dict_in["$in"]=list_individualIds
        LOG.debug(list_individualIds)
        id_dict[collection_id]=dict_in
        query = id_dict
    else:
        for k, v in ids.items():
            for item in v:
                id_list.append(item[cross_type])
        dict_in["$in"]=id_list
        id_dict[collection_id]=dict_in
        query = id_dict


    LOG.debug(query)
    return query

def get_cross_query_variants(ids: dict, cross_type: str, collection_id: str):
    id_list=[]
    dict_in={}
    id_dict={}
    for k, v in ids.items():
        for item in v:
            id_list.append(item[cross_type])
    dict_in["$in"]=id_list
    id_dict[collection_id]=dict_in
    query = id_dict


    LOG.debug(query)
    return query
