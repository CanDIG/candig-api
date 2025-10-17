from typing import Dict, Optional

from pymongo.cursor import Cursor
from pymongo.collection import Collection
from beacon.omop import client
from beacon.request.model import RequestParams
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
    records = individual_queries.sql_get_ontology(client,
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
        
        
def basic_query(query):
    cur = client.cursor()
    cur.execute(query)
    records = cur.fetchall()
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


def get_count(query: str) -> int:
    LOG.debug("Returning estimated count")
    queryFinal = "Select count(*) " + query
    LOG.debug("FINAL QUERY: {}".format(queryFinal))
    records = basic_query(queryFinal)
    return records[0][0]

## TODO: check format_query() definition
def get_documents(listVariables: list, query: str, skip: int, limit: int) -> Cursor:
    queryFinal = "Select " + ",".join(listVariables) + " " + query 
    LOG.debug("FINAL QUERY: {}".format(queryFinal))
    with client:
        cur = client.cursor()
        cur.execute(queryFinal)
        records = cur.fetchall()  
        recordsFinal = format_query(listVariables, records)
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
