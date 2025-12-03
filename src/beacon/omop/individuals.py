import logging
from typing import Dict, List, Optional
# from beacon.omop.filters import apply_alphanumeric_filter, apply_filters
# from beacon.omop.utils import  get_count, get_cross_query, get_documents, search_ontologies, basic_query
from ...beacon.omop.utils import  search_ontologies, basic_query, peek
from ...beacon.omop import engine, mappings
# from beacon.request.model import AlphanumericFilter, Operator, RequestParams
from ...beacon.request.model import RequestParams
from ...beacon.omop.schemas import DefaultSchemas
import re
import aiosql
import itertools
from sqlalchemy import text
from ..conf import MAX_LIMIT

LOG = logging.getLogger(__name__)


from ...beacon.omop.utils import CDM_SCHEMA, VOCABULARIES_SCHEMA
from ...beacon.omop.biosamples import get_biosamples_with_person_id
from pathlib import Path
queries_file = Path(__file__).parent / "sql" / "individuals.sql"
individual_queries = aiosql.from_path(queries_file, "psycopg2")

async def get_individual_id(offset=0, limit=10, person_id=None):
    async with engine.connect() as conn:
        if person_id == None:
            # aiosql likes to swap params like :limit and :offset to %(limit)s and %(offset)s, which is unsafe
            # we swap it back before continuing
            transformed_sql = individual_queries.sql_get_individuals.sql \
                .replace("%(limit)s", ":limit") \
                .replace("%(offset)s", ":offset")
            records = await conn.execute(text(transformed_sql), {"limit": limit, "offset": offset})
            # records = individual_queries.sql_get_individuals(engine, offset=offset, limit=limit)
            listId = [str(record[0]) for record in records]
        else:
            transformed_sql = individual_queries.sql_get_individual_id.sql.replace("%(person_id)s", ":person_id")
            records = await conn.execute(text(transformed_sql), {"person_id": person_id})
            # records = individual_queries.sql_get_individual_id(engine, person_id=person_id)
            listId = [str(records[0])]
    return listId

async def get_individuals_person(listIds):
    dict_person = {}
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_person.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            records = await conn.execute(transformed_sql, {"person_id": int(person_id)})
            # records = individual_queries.sql_get_person(engine, person_id=person_id)
            listValues = []
            for record in records:
                listValues.append({"gender_concept_id" : record[0],
                                    "race_concept_id" : record[1]})
            dict_person[person_id] = listValues
    return dict_person


async def get_individuals_condition(listIds):
    dict_condition = {}
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_condition.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            records = await conn.execute(transformed_sql, {"person_id": int(person_id)})
            # records = individual_queries.sql_get_condition(engine, person_id=person_id)
            listValues = []
            for record in records:
                if record[1] == None:
                    ageOfOnset = "Not Available"
                else:
                    ageOfOnset = f"P{record[1]}Y"
                listValues.append({"condition_concept_id" : record[0],
                                "condition_ageOfOnset" : ageOfOnset})
            dict_condition[person_id] = listValues

    return dict_condition

async def get_individuals_procedure(listIds):
    dict_procedure = {}
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_procedure.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            records = await conn.execute(transformed_sql, {"person_id": int(person_id)})
            # records = individual_queries.sql_get_procedure(engine, person_id=person_id)
            listValues = []
            for record in records:
                if record[1] == "None":
                    ageOfOnset = "Not Available"
                else:
                    ageOfOnset = f"P{record[1]}Y"            
                listValues.append({"procedure_concept_id" : record[0],
                                    "procedure_ageOfOnset" : ageOfOnset,
                                    "procedure_date" : record[2]})
            dict_procedure[person_id] = listValues
    return dict_procedure        


async def get_individuals_measures(listIds):
    dict_measures = {}
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_measure.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            records = await conn.execute(transformed_sql, {"person_id": int(person_id)})
            # records = individual_queries.sql_get_measure(engine, person_id=person_id)
            listValues = []
            for record in records:
                if record[1] == "None":
                    ageOfOnset = "Not Available"
                else:
                    ageOfOnset = f"P{record[1]}Y"
                listValues.append({"measurement_concept_id" : record[0],
                                    "measurement_ageOfOnset" : ageOfOnset,
                                    "measurement_date" : record[2],
                                    "unit_concept_id" : record[3],
                                    "value_source_value" : record[4]})
            dict_measures[person_id] = listValues
    return dict_measures


async def get_individuals_exposures(listIds):
    dict_exposures = {}
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_exposure.sql.replace("%(person_id)s", ":person_id"))
        transformed_sql_duration = text(individual_queries.sql_get_exposure_period.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            records = (await conn.execute(transformed_sql, {"person_id": int(person_id)})).fetchall()
            records_duration = (await conn.execute(transformed_sql_duration, {"person_id": int(person_id)})).fetchall()
            # records = individual_queries.sql_get_exposure(engine, person_id=person_id)
            # records_duration = individual_queries.sql_get_exposure_period(engine, person_id=person_id)
            listValues = []
            for record in records:
                if record[1] == "None":
                    ageOfOnset = "Not Available"
                else:
                    ageOfOnset = f"P{record[1]}Y"
                if records_duration:
                    records_duration = str(records_duration[0])
                else:
                    records_duration = "Not Available"
                listValues.append({"observation_concept_id" : record[0],
                                    "observation_ageOfOnset" : ageOfOnset,
                                    "observation_date" : record[2],
                                    "unit_concept_id" : record[3],
                                    "duration": records_duration})
            dict_exposures[person_id] = listValues
    return dict_exposures

async def get_individuals_treatments(listIds):
    dict_treatments = {}
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_treatment.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            records = await conn.execute(transformed_sql, {"person_id": int(person_id)})
            # records = individual_queries.sql_get_treatment(engine, person_id=person_id)
            listValues = []
            for record in records:
                if record[1] == "None":
                    ageOfOnset = "Not Available"
                else:
                    ageOfOnset = f"P{record[1]}Y"
                listValues.append({"drugExposure_concept_id" : record[0],
                                    "drugExposure_ageOfOnset" : ageOfOnset})
            dict_treatments[person_id] = listValues
    return dict_treatments 


def format_query(listIds, dictPerson, dictCondition, dictProcedures, dictMeasures, dictExposures, dictTreatments):
    list_format = []
    for person_id in listIds:
        dictId = {"id":person_id}
        if any("gender_concept_id" in d for d in dictPerson[person_id]):
            dictId["sex"] = dictPerson[person_id][0]["gender_concept_id"]
        if any("race_concept_id" in d for d in dictPerson[person_id]):
            dictId["ethnicity"] = dictPerson[person_id][0]["race_concept_id"]
        if any("condition_concept_id" in d for d in dictCondition[person_id]):
            dictId["diseases"] = list(map(mappings.diseases_table_map, dictCondition[person_id]))
        if any("procedure_concept_id" in d for d in dictProcedures[person_id]):
            dictId["interventionsOrProcedures"] = list(map(mappings.procedures_table_map, dictProcedures[person_id]))
        if any("measurement_concept_id" in d for d in dictMeasures[person_id]):
            dictId["measures"] = list(map(mappings.measures_table_map, dictMeasures[person_id]))
        if any("observation_concept_id" in d for d in dictExposures[person_id]):
            dictId["exposures"] = list(map(mappings.exposures_table_map, dictExposures[person_id]))
        if any("drugExposure_concept_id" in d for d in dictTreatments[person_id]):
            dictId["treatments"] = list(map(mappings.treatments_table_map, dictTreatments[person_id]))
        list_format.append(dictId)
    return list_format

def map_domains(domain_id):
    # Domain_id : Table in OMOP
    # Maybe there is more than one mapping in the condition domain
    dictMapping = {
        'Gender':{'person':'gender_concept_id'},
        'Race':{'person':'race_concept_id'},
        'Condition':{'condition_occurrence':'condition_concept_id'},
        'Measurement':{'measurement':'measurement_concept_id'},
        'Procedure':{'procedure_occurrence':'procedure_concept_id'},
        'Observation':{'observation':'observation_concept_id'},
        'Drug':{'drug_exposure':'drug_concept_id'}

    }
    return dictMapping[domain_id]

def search_descendants(concept_id):
    records = individual_queries.sql_get_descendants(engine, concept_id=concept_id)

    l_descendants = set()
    for descendant in records:
        l_descendants.add(descendant[0])
    return l_descendants

def create_dynamic_filter(filters):
    base_filter = {
        'demografic_filters': '',
        'condition_filters': '',
        'measurement_filters': '',
        'procedures_filters': '',
        'exposures_filters': '',
        'treatments_filters': '',
    }

    list_person = []
    n_open_condition = 0
    query_condition = ""
    n_open_measurement = 0
    query_measurement = ""
    n_open_procedure = 0
    query_procedure = ""
    n_open_exposure = 0
    query_exposure = ""
    n_open_treatment = 0
    query_treatment = ""
    for filter in filters:
        # Default type of filter is ontology
        filterType = 'Ontology'
        if filter[2]:       # If filter has an operator (operator!=None) it is an Alphanumeric filter
            filterType = 'Alphanumeric'
        if "person" in filter[0]:
            variable_name = filter[0]['person']
            list_concept_id = []
            for concept_id in filter[1]:
                list_concept_id.append(variable_name + ' = ' + str(concept_id))
            query_person_id =  ' or '.join(list_concept_id)
            list_person.append(' ( ' + query_person_id + ' ) ')
        if "condition_occurrence" in filter[0]:
            n_open_condition += 1 
            variable_name = filter[0]['condition_occurrence']
            list_concept_id = []
            for concept_id in filter[1]:
                if variable_name == 'Age':
                    operator = filter[2]
                    value = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(condition_start_date, birth_datetime)) {operator} {value} 
                            ELSE (extract(Year from condition_start_date) - year_of_birth)  {operator} {value}
                        END
                        """)
                else:
                    list_concept_id.append(variable_name + ' = ' + str(concept_id))
            query_person_id =  ' or '.join(list_concept_id)
            # This can be a function to no repeat always the same -> filter[0]
            query_condition += f"""
                and exists (
                    select 1
                    from cdm.condition_occurrence co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'measurement' in filter[0]:
            n_open_measurement += 1 
            variable_name = filter[0]['measurement']
            list_concept_id = []
            for concept_id in filter[1]:
                if variable_name == 'Age':
                    operator = filter[2]
                    value = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(measurement_date, birth_datetime)) {operator} {value} 
                            ELSE (extract(Year from measurement_date) - year_of_birth)  {operator} {value}
                        END
                        """)
                elif filterType == 'Alphanumeric':
                    value = filter[3]
                    list_concept_id.append(variable_name + ' = ' + str(concept_id) +
                                           ' and value_as_number ' + filter[2] + " " + value)
                else:
                    list_concept_id.append(variable_name + ' = ' + str(concept_id))
            query_person_id =  ' or '.join(list_concept_id)
            query_measurement += f"""
                and exists (
                    select 1
                    from cdm.measurement co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'procedure_occurrence' in filter[0]:
            n_open_procedure += 1 
            variable_name = filter[0]['procedure_occurrence']
            list_concept_id = []
            for concept_id in filter[1]:
                if variable_name == 'Age':
                    operator = filter[2]
                    value = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(procedure_date, birth_datetime)) {operator} {value} 
                            ELSE (extract(Year from procedure_date) - year_of_birth)  {operator} {value}
                        END
                        """)
                else:
                    list_concept_id.append(variable_name + ' = ' + str(concept_id))
            query_person_id =  ' or '.join(list_concept_id)
            query_procedure += f"""
                and exists (
                    select 1
                    from cdm.procedure_occurrence co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'observation' in filter[0]:
            n_open_exposure += 1 
            variable_name = filter[0]['observation']
            list_concept_id = []
            for concept_id in filter[1]:
                if variable_name == 'Age':
                    operator = filter[2]
                    value = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(observation_date, birth_datetime)) {operator} {value} 
                            ELSE (extract(Year from observation_date) - year_of_birth)  {operator} {value}
                        END
                        """)
                else:
                    list_concept_id.append(variable_name + ' = ' + str(concept_id))
            query_person_id =  ' or '.join(list_concept_id)
            query_exposure += f"""
                and exists (
                    select 1
                    from cdm.observation co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'drug_exposure' in filter[0]:
            n_open_treatment += 1
            variable_name = filter[0]['drug_exposure']
            list_concept_id = []
            for concept_id in filter[1]:
                if variable_name == 'Age':
                    operator = filter[2]
                    value = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(drug_exposure_start_date, birth_datetime)) {operator} {value} 
                            ELSE (extract(Year from drug_exposure_start_date) - year_of_birth)  {operator} {value}
                        END
                        """)
                else:
                    list_concept_id.append(variable_name + ' = ' + str(concept_id))
            query_person_id =  ' or '.join(list_concept_id)
            query_treatment += f"""
                and exists (
                    select 1
                    from cdm.drug_exposure co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """         
        
    query_condition += ')'* n_open_condition
    query_measurement += ')'* n_open_measurement
    query_procedure += ')'* n_open_procedure
    query_exposure += ')'* n_open_exposure
    query_treatment += ')'* n_open_treatment

    if list_person:
        base_filter['demografic_filters'] += ' and ( ' + " and ".join(list_person) + ' ) '

    base_filter['condition_filters'] += query_condition
    base_filter['measurement_filters'] += query_measurement
    base_filter['procedures_filters'] += query_procedure
    base_filter['exposures_filters'] += query_exposure
    base_filter['treatments_filters'] += query_treatment

    return base_filter

def super_query_count(filter):
    return  f""" select count(distinct person_id)
        from cdm.person p
        where true
        {filter['demografic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}

    """

def super_query_get(filter, offset, limit):
    return  f""" select person_id
        from cdm.person p
        where true
        {filter['demografic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}

        limit {limit}
        offset {offset}
    """

def mapBeaconScopeToOMOP(scope):
    mappingDict = {'ageAtDisease':'condition_occurrence',
     'ageAtProcedure':'procedure_occurrence',
     'observationMoment':'measurement',
     'ageAtExposure':'observation',
     'ageAtTreatment':'drug_exposure'
     }
    scopeMapping = {mappingDict[scope]:'Age'}
    return scopeMapping

def checkFilters(filtersDict, offset, limit, typeQuery):
    listOfList = []
    dictTableMap = []
    for filter in filtersDict:
        listConcept_id = set()
        operator = None
        value = None
        includeDescendantTerms = True
        typeFilter = 'Ontology'     # Default filter option
        # Check query
        # Parse query depend on POST/GET query
        if typeQuery == 'POST':
            if 'includeDescendantTerms' in filter:
                if filter['includeDescendantTerms'] == False:
                    includeDescendantTerms = False
            if 'operator' in filter:
                typeFilter = 'Alphanumeric'
                operator = filter['operator']
                value = filter['value']
                includeDescendantTerms = False
            if 'id' in filter:
                filterId = filter['id']
            else:
                return [], 0
            if (filterId == 'ageOfOnset' or
                filterId == 'ageAtProcedure' or
                filterId == 'observationMoment' or
                filterId == 'ageAtExposure'):
                    # Convert scope to tableMap
                    # listConcept_id empty
                    typeFilter = "Age"
                    listConcept_id = ['None']
                    if filterId == 'ageOfOnset':
                        try:
                            scope = filter['scope']
                        except:
                            print("You need an scope if you are using 'ageOfOnset'") 
                        if "disease" in scope:
                            filterId = 'ageAtDisease'
                        elif "treatments" in scope:
                            filterId = 'ageAtTreatment'
                    tableMap = mapBeaconScopeToOMOP(filterId)
                    dictTableMap.append([tableMap, listConcept_id, operator, value])
                    continue

        else: # If GET
            filterId = filter

        if typeFilter=="Ontology" or  typeFilter=="Alphanumeric":
            vocabulary_id, concept_code = filterId.split(':')
            records = individual_queries.sql_get_concept_domain(engine,
                                                                vocabulary_id=vocabulary_id,
                                                                concept_code=concept_code)
            # Check if records is empty
            res = peek(records)
            if res is None:
                return [], 0
            _, records = res
            for record in records:
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
    print(dictTableMap)
    base_filter = create_dynamic_filter(dictTableMap)
    query_count = super_query_count(base_filter)
    count_records = basic_query(query_count)
    query_get = super_query_get(base_filter, offset, limit)
    print(query_get)
    records_get = basic_query(query_get)
    listOfList = [str(record[0]) for record in records_get]

    return listOfList, count_records[0][0]

# /individuals/?filters=SNOMED:0&filters=OMOP:23
def filters(filtersDict, offset, limit):
    if type(filtersDict[0]) is dict:         # If filter is from Post
        print(filtersDict)
        print("post")
        listFilters, count = checkFilters(filtersDict, offset, limit, 'POST')
    else:
        print("get")
        listFilters, count = checkFilters(filtersDict, offset, limit, 'GET')

    return listFilters, count
                                                      
async def get_individuals(entry_id: Optional[str]=None, qparams: RequestParams=RequestParams()):

    schema = DefaultSchemas.INDIVIDUALS
    count_ids = 0
    if qparams.query.pagination.limit == 0:
        qparams.query.pagination.limit = MAX_LIMIT
    if qparams.query.filters:
        listIds, count_ids = filters(qparams.query.filters,
                        offset=qparams.query.pagination.skip,
                        limit=qparams.query.pagination.limit)
        if count_ids == 0:
            return schema, count_ids, []
    else:
        listIds = await get_individual_id(offset=qparams.query.pagination.skip,
                                            limit=qparams.query.pagination.limit,
                                            person_id=entry_id)                 # List with all Ids
        async with engine.connect() as conn:
            count_ids = await conn.execute(text(individual_queries.count_individuals.sql)) # Count individuals
            count_ids = count_ids.first()[0]
        print('Number of ids',count_ids)

    dictPerson = await get_individuals_person(listIds)        # List with Id, sex, ethnicity
    dictCondition = await get_individuals_condition(listIds)  # List with al the diseases per Id
    dictProcedures = await get_individuals_procedure(listIds)
    dictMeasures = await get_individuals_measures(listIds)
    dictExposures = await get_individuals_exposures(listIds)
    dictTreatments = await get_individuals_treatments(listIds)

    dictPerson = await search_ontologies(dictPerson)
    dictCondition = await search_ontologies(dictCondition)
    dictProcedures = await search_ontologies(dictProcedures)
    dictMeasures = await search_ontologies(dictMeasures)
    dictExposures = await search_ontologies(dictExposures)
    dictTreatments = await search_ontologies(dictTreatments)

    docs = format_query(listIds, dictPerson, dictCondition, dictProcedures, dictMeasures, dictExposures, dictTreatments)

    return schema, count_ids, docs



def get_individual_with_id(entry_id: Optional[str], qparams: RequestParams):
    
    schema = DefaultSchemas.INDIVIDUALS

    if qparams.query.filters:
        originalListIds = filters(qparams.query.filters)
        if not entry_id in listIds:
            return schema, 0, []
    
    # Search Id
    listIds = get_individual_id(person_id=entry_id)

    dictPerson = get_individuals_person(listIds)
    dictCondition = get_individuals_condition(listIds)
    dictProcedures = get_individuals_procedure(listIds)
    dictMeasures = get_individuals_measures(listIds)
    dictExposures = get_individuals_exposures(listIds)
    dictTreatments = get_individuals_treatments(listIds)


    dictPerson = search_ontologies(dictPerson)
    dictCondition = search_ontologies(dictCondition)
    dictProcedures = search_ontologies(dictProcedures)
    dictMeasures = search_ontologies(dictMeasures)
    dictExposures = search_ontologies(dictExposures)
    dictTreatments = search_ontologies(dictTreatments)

    docs = format_query(listIds, dictPerson, dictCondition, dictProcedures, dictMeasures, dictExposures, dictTreatments)

    return schema, 1, docs

def get_biosamples_of_individual(entry_id: Optional[str], qparams: RequestParams):
    collection = 'individuals'
    schema = DefaultSchemas.BIOSAMPLES
    schema, count, docs = get_biosamples_with_person_id(entry_id, qparams)
    return schema, count, docs

async def get_filtering_terms_of_individual(entry_id: Optional[str], qparams: RequestParams):
    schema = DefaultSchemas.FILTERINGTERMS

    l_sql_filters = [individual_queries.sql_filtering_terms_race_gender.sql,
                    individual_queries.sql_filtering_terms_condition.sql,
                    individual_queries.sql_filtering_terms_measurement.sql,
                    individual_queries.sql_filtering_terms_procedure.sql,
                    individual_queries.sql_filtering_terms_observation.sql,
                individual_queries.sql_filtering_terms_drug_exposure.sql]
    l_indFilters = []
    async with engine.connect() as conn:
        for ind_filters in l_sql_filters:
            results = await conn.execute(text(ind_filters))
            # NB: Hopefully the filtering terms doesn't get long enough that this fetchall stalls?
            for filters in results.fetchall():
                # Unknown what the following is for:
                if filters[0].endswith("OMOP generated"):
                    continue
                dict_filter = {"id":filters[0],"label":filters[1],"scopes":["individual"],"type":"ontology"}
                l_indFilters.append(dict_filter)
    LOG.info(l_indFilters)
    return schema, len(l_indFilters), l_indFilters

def get_cohort_individuals(cohort_id, offset=0, limit=10):

    schema = DefaultSchemas.INDIVIDUALS
    count_ids = 0


    listIds = individual_queries.cohort_individuals(engine,
                                offset=offset,
                                limit=limit,
                                cohort_id=cohort_id)                 # List with all Ids
    count_ids = individual_queries.count_cohort_individuals(engine, cohort_id=cohort_id)   # Count individuals

    dictPerson = get_individuals_person(listIds)        # List with Id, sex, ethnicity
    dictCondition = get_individuals_condition(listIds)  # List with al the diseases per Id
    dictProcedures = get_individuals_procedure(listIds)      # List with all the procedures per Id
    dictMeasures = get_individuals_measures(listIds)
    dictExposures = get_individuals_exposures(listIds)
    dictTreatments = get_individuals_treatments(listIds)

    dictPerson = search_ontologies(dictPerson)
    dictCondition = search_ontologies(dictCondition)
    dictProcedures = search_ontologies(dictProcedures)
    dictMeasures = search_ontologies(dictMeasures)
    dictExposures = search_ontologies(dictExposures)
    dictTreatments = search_ontologies(dictTreatments)

    docs = format_query(listIds, dictPerson, dictCondition, dictProcedures, dictMeasures, dictExposures, dictTreatments)

    return schema, count_ids, docs

# def build_filters(filtersDict):
#     CURIE_REGEX = r'^([a-zA-Z0-9]*):\/?[a-zA-Z0-9]*$'
#     print(filtersDict)
#     listOfList = []
#     dictTableMap = []
#     for value in filtersDict:
#         listConcept_id = set()
#         if re.match(CURIE_REGEX, value):
#             vocabulary_id, concept_code = value.split(':')
#             # Get OMOP Id from the vocabulary:concept_code (SNOMED:1234)
#             records = individual_queries.sql_get_concept_domain(engine,
#                                                                 vocabulary_id=vocabulary_id,
#                                                                 concept_code=concept_code)
#             # Check if records is empty
#             res = peek(records)
#             if res is None:
#                 return [], 0
#             _, records = res
#             for record in records:
#                 original_concept_id = record[0]
#                 domain_id = record[1]
#             listConcept_id.add(original_concept_id)
#             # Look in which domains the concept_id belongs
#             tableMap=map_domains(domain_id)
#             # Import descendants of the concept_id
#             concept_ids= search_descendants(original_concept_id)
#             # Concept_id and descendants in same set()
#             listConcept_id = listConcept_id.union(concept_ids)
#             dictTableMap.append([tableMap, listConcept_id])
#         else:
#             # If not CURIE
#             return [], 0
#     print(dictTableMap)


###### All these functions below are from the RI-Mongo implementation
###### They do not work
def get_variants_of_individual(entry_id: Optional[str], qparams: RequestParams):
    # collection = 'individuals'
    # query = {"$and": [{"id": entry_id}]}
    # query = apply_request_parameters(query, qparams)
    # query = apply_filters(query, qparams.query.filters, collection)
    # count = get_count(engine.beacon.individuals, query)
    # individual_ids = engine.beacon.individuals \
    #     .find_one(query, {"id": 1, "_id": 0})
    # LOG.debug(individual_ids)
    # individual_ids=get_cross_query(individual_ids,'id','caseLevelData.biosampleId')
    # LOG.debug(individual_ids)
    # query = apply_filters(individual_ids, qparams.query.filters, collection)

    # schema = DefaultSchemas.GENOMICVARIATIONS
    # count = get_count(engine.beacon.genomicVariations, query)
    # docs = get_documents(
    #     engine.beacon.genomicVariations,
    #     query,
    #     qparams.query.pagination.skip,
    #     qparams.query.pagination.limit
    # )
    schema = DefaultSchemas.GENOMICVARIATIONS
    count = 0
    docs = {}
    return schema, count, docs

def get_runs_of_individual(entry_id: Optional[str], qparams: RequestParams):
    # collection = 'individuals'
    # query = {"individualId": entry_id}
    # query = apply_request_parameters(query, qparams)
    # query = apply_filters(query, qparams.query.filters, collection)
    # schema = DefaultSchemas.RUNS
    # count = get_count(engine.beacon.runs, query)
    # docs = get_documents(
    #     engine.beacon.runs,
    #     query,
    #     qparams.query.pagination.skip,
    #     qparams.query.pagination.limit
    # )
    schema = DefaultSchemas.RUNS
    count = 0
    docs = {}
    return schema, count, docs


def get_analyses_of_individual(entry_id: Optional[str], qparams: RequestParams):
    # collection = 'individuals'
    # query = {"individualId": entry_id}
    # query = apply_request_parameters(query, qparams)
    # query = apply_filters(query, qparams.query.filters, collection)
    # schema = DefaultSchemas.ANALYSES
    # count = get_count(engine.beacon.analyses, query)
    # docs = get_documents(
    #     engine.beacon.analyses,
    #     query,
    #     qparams.query.pagination.skip,
    #     qparams.query.pagination.limit
    # )
    schema = DefaultSchemas.ANALYSES
    count = 0
    docs = {}
    return schema, count, docs
