import logging
from typing import Dict, List, Optional
# from beacon.omop.filters import apply_alphanumeric_filter, apply_filters
from ...beacon.omop.utils import query_id, query_ids, get_count, get_documents, get_cross_query
from ...beacon.omop.utils import  search_ontologies, basic_query, peek
from ...beacon.omop import engine
# from beacon.request.model import AlphanumericFilter, Operator, RequestParams
# from beacon.omop.filters import *
from ...beacon.omop.schemas import DefaultSchemas
from ...beacon.request.model import RequestParams
import re
import aiosql
import itertools

import random
from pathlib import Path
queries_file = Path(__file__).parent / "sql" / "biosamples.sql"
biosamples_queries = aiosql.from_path(queries_file, "psycopg2", mandatory_parameters=False)

LOG = logging.getLogger(__name__)

# def apply_request_parameters(query: Dict[str, List[dict]], qparams: RequestParams):
#     LOG.debug("Request parameters len = {}".format(len(qparams.query.request_parameters)))
#     for k, v in qparams.query.request_parameters.items():
#         query["$text"] = {}
#         if ',' in v:
#             v_list = v.split(',')
#             v_string=''
#             for val in v_list:
#                 v_string += f'"{val}"'
#             query["$text"]["$search"]=v_string
#         else:
#             query["$text"]["$search"]=v
#     return query

def get_biosample_id(offset=0, limit=10, biosample_id=None):
    if biosample_id == None:
        records = biosamples_queries.sql_get_biosamples(engine, offset=offset, limit=limit)
        listId = [str(record[0]) for record in records]
    else:
        records = biosamples_queries.sql_get_biosample_id(engine, specimen_id=biosample_id)
        listId = [str(records[0])]
    return listId


def get_specimens(listIds):
    dict_specimens = {}
    for biosample_id in listIds:
        records = biosamples_queries.sql_get_specimen(engine, specimen_id = biosample_id)
        listValues = []
        for record in records:
            listValues.append({'person_id': record[0],
                               'disease_status_concept_id': record[1],
                               'anatomic_site_concept_id': record[2],
                               'specimen_date': record[3],
                               'specimen_moment': record[4]})
        dict_specimens[biosample_id] = listValues
    return dict_specimens

def format_query(listIds, specimens):

    list_format = []
    for biosample_id in listIds:
        dict_biosample_id =  { 
            "id": str(biosample_id),
            "individualId": str(specimens[biosample_id][0]["person_id"]),
            "biosampleStatus": {
                "id":  specimens[biosample_id][0]["disease_status_concept_id"]["id"],
                "label": specimens[biosample_id][0]["disease_status_concept_id"]["label"]
            },
            "sampleOriginType": {
                "id" : specimens[biosample_id][0]["anatomic_site_concept_id"]["id"],
                "label" : specimens[biosample_id][0]["anatomic_site_concept_id"]["label"]
            },
            "collectionMoment": specimens[biosample_id][0]["specimen_date"],
            "collectionDate": specimens[biosample_id][0]["specimen_moment"],
            "info": {}
            }
        list_format.append(dict_biosample_id)
    return list_format


def map_domains(domain_id):
    # Domain_id : Table in OMOP
    # Maybe there is more than one mapping in the condition domain
    dictMapping = {
        'Spec Disease Status':'disease_status_concept_id',
        'Spec Anatomic Site':'"anatomic_site_concept_id"'
    }
    return dictMapping[domain_id]

def search_descendants(concept_id):
    records = biosamples_queries.sql_get_descendants(engine, concept_id=concept_id)

    l_descendants = set()
    for descendant in records:
        l_descendants.add(descendant[0])
    return l_descendants

def create_dynamic_filter(filters):

    list_person = []
    for filter in filters:
        # Default type of filter is ontology
        filterType = 'Ontology'
        # For now there is no Alphanumeric available option
        if filter[2]:       # If filter has an operator (operator!=None) it is an Alphanumeric filter
            filterType = 'Alphanumeric'

        if "disease_status_concept_id" in filter[0] or "anatomic_site_concept_id" in filter[0]:
            variable_name = filter[0]
            list_concept_id = []
            for concept_id in filter[1]:
                list_concept_id.append(variable_name + ' = ' + str(concept_id))
            query_person_id =  ' or '.join(list_concept_id)
            list_person.append(' ( ' + query_person_id + ' ) ')

    return list_person

def super_query_count(filter):
    return  f""" select count(distinct specimen_id)
        from cdm.specimen p
        where true and
        {filter[0]}
    """

def super_query_get(filter, offset, limit):
    return  f""" select specimen_id
        from cdm.specimen p
        where true and
        {filter[0]}
        limit {limit}
        offset {offset}
    """

def checkFilters(filtersDict, offset, limit, typeQuery):
    listOfList = []
    dictTableMap = []
    for filter in filtersDict:
        listConcept_id = set()
        operator = None
        value = None
        includeDescendantTerms = True

        # Check query
        # Parse query depend on POST/GET query
        if typeQuery == 'POST':
            if 'includeDescendantTerms' in filter:
                if filter['includeDescendantTerms'] == False:
                    includeDescendantTerms = False
            if 'operator' in filter:
                operator = filter['operator']
                value = filter['value']
                includeDescendantTerms = False
            if 'id' in filter:
                filterId = filter['id']
                print(filterId)
            else:
                return [], 0
        else: # If GET
            filterId = filter

        vocabulary_id, concept_code = filterId.split(':')
        print(vocabulary_id, concept_code)
        records = biosamples_queries.sql_get_concept_domain(engine,
                                                            vocabulary_id=vocabulary_id,
                                                            concept_code=concept_code)
        # Check if records is empty
        res = peek(records)
        if res is None:
            return [], 0
        _, records = res
        for record in records:
            print(record)
            original_concept_id = record[0]
            domain_id = record[1]
        listConcept_id.add(original_concept_id)
        # Look in which domains the concept_id belongs
        tableMap=map_domains(domain_id)
        if includeDescendantTerms:
            # Import descendants of the concept_id
            concept_ids= search_descendants(original_concept_id)
            # Concept_id and descendants in same set()
            listConcept_id = listConcept_id.union(concept_ids)
        dictTableMap.append([tableMap, listConcept_id, operator, value])
    base_filter = create_dynamic_filter(dictTableMap)
    query_count = super_query_count(base_filter)
    count_records = basic_query(query_count)
    query_get = super_query_get(base_filter, offset, limit)
    records_get = basic_query(query_get)
    listOfList = [str(record[0]) for record in records_get]

    return listOfList, count_records[0][0]

# /individuals/?filters=SNOMED:0&filters=OMOP:23
def filters(filtersDict, offset, limit):
    if type(filtersDict[0]) is dict:         # If filter is from Post
        listFilters, count = checkFilters(filtersDict, offset, limit, 'POST')
    else:
        listFilters, count = checkFilters(filtersDict, offset, limit, 'GET')

    return listFilters, count

def get_biosamples(entry_id: Optional[str], qparams: RequestParams):

    collection = 'biosamples'
    schema = DefaultSchemas.BIOSAMPLES

    count_ids = 0
    if qparams.query.filters:
        listIds, count_ids = filters(qparams.query.filters,
                        offset=qparams.query.pagination.skip,
                        limit=qparams.query.pagination.limit)
        print(listIds, count_ids)
        if count_ids == 0:
            return schema, count_ids, []
    else:
        listIds = get_biosample_id(offset=qparams.query.pagination.skip,
                                            limit=qparams.query.pagination.limit,
                                            biosample_id=entry_id)                 # List with all Ids
        count_ids = biosamples_queries.get_count_specimen(engine)   # Count specimen

    specimens = get_specimens(listIds)
    specimens = search_ontologies(specimens)
    print(specimens)

    docs = format_query(listIds, specimens)

    return schema, count_ids, docs


def get_biosample_with_id(entry_id: Optional[str], qparams: RequestParams):

    listIds = get_biosample_id(biosample_id=entry_id)

    schema = DefaultSchemas.BIOSAMPLES
    count = 1 # biosamples_queries.get_count_specimen(engine)
    specimens = get_specimens(listIds)
    specimens = search_ontologies(specimens)

    docs = format_query(listIds, specimens)
    return schema, count, docs


def specimen_to_biosample(listSpecimens):
    schema = DefaultSchemas.BIOSAMPLES
    count = len(listSpecimens) # biosamples_queries.get_count_specimen(engine)
    specimens = get_specimens(listSpecimens)
    specimens = search_ontologies(specimens)
    print(listSpecimens)
    docs = format_query(listSpecimens, specimens)
    return schema, count, docs


# TO DO
def get_biosamples_with_person_id(person_id: Optional[str], qparams: RequestParams):

    collection = 'biosamples'
    schema = DefaultSchemas.BIOSAMPLES
    specimens = biosamples_queries.get_specimen_by_person_id(engine, person_id=person_id)
    listSpecimens = [specimen[0] for specimen in specimens ]
    schema, count, docs  = specimen_to_biosample(listSpecimens)
    return schema, count, docs

def get_filtering_terms_of_biosample(entry_id: Optional[str], qparams: RequestParams):
    schema = DefaultSchemas.FILTERINGTERMS
    bio_filters = biosamples_queries.sql_filtering_terms_biosample(engine)
    l_bioFilters = []
    for filters in bio_filters:
        dict_filter = {"id":filters[0],"label":filters[1],"scopes":["biosample"],"type":"ontology"}
        l_bioFilters.append(dict_filter)
    return schema, len(l_bioFilters), l_bioFilters

# TO DO
def get_variants_of_biosample(entry_id: Optional[str], qparams: RequestParams):
    raise NotImplementedError("Still need to port: biosamples.get_variants_of_biosample")
    collection = 'biosamples'
    query = {"$and": [{"id": entry_id}]}
    query = apply_request_parameters(query, qparams)
    query = apply_filters(query, qparams.query.filters, collection)
    count = get_count(client.beacon.biosamples, query)
    biosamples_ids = client.beacon.biosamples \
        .find_one(query, {"id": 1, "_id": 0})
    LOG.debug(biosamples_ids)
    biosamples_ids=get_cross_query(biosamples_ids,'id','caseLevelData.biosampleId')
    LOG.debug(biosamples_ids)
    query = apply_filters(biosamples_ids, qparams.query.filters, collection)

    schema = DefaultSchemas.GENOMICVARIATIONS
    count = get_count('omop.genomic_variations', query)
    docs = get_documents(
        'omop.genomic_variations',
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs

# TO DO
def get_analyses_of_biosample(entry_id: Optional[str], qparams: RequestParams):
    raise NotImplementedError("Still need to port: biosamples.get_analyses_of_biosample")
    collection = 'biosamples'
    query = {"biosampleId": entry_id}
    query = apply_request_parameters(query, qparams)
    query = apply_filters(query, qparams.query.filters, collection)
    schema = DefaultSchemas.ANALYSES
    count = get_count(client.beacon.analyses, query)
    docs = get_documents(
        client.beacon.analyses,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs

# TO DO
def get_runs_of_biosample(entry_id: Optional[str], qparams: RequestParams):
    raise NotImplementedError("Still need to port: biosamples.get_runs_of_biosample")
    collection = 'biosamples'
    query = {"biosampleId": entry_id}
    query = apply_request_parameters(query, qparams)
    query = apply_filters(query, qparams.query.filters, collection)
    schema = DefaultSchemas.RUNS
    count = get_count(client.beacon.runs, query)
    docs = get_documents(
        client.beacon.runs,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs
