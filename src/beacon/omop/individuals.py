import re

from connexion import request
from typing import Optional
from ...beacon.omop.utils import  search_ontologies, basic_query, peek
from ...beacon.omop import engine, mappings
from ...beacon.request.model import RequestParams
from ...beacon.omop.schemas import DefaultSchemas
import aiosql
from sqlalchemy import text, bindparam
from ..conf import MAX_LIMIT

import authx.auth
from ...beacon.omop.biosamples import get_biosamples_with_person_id
from pathlib import Path
from candigv2_logging.logging import CanDIGLogger

logger = CanDIGLogger(__file__)

queries_file = Path(__file__).parent / "sql" / "individuals.sql"
individual_queries = aiosql.from_path(queries_file, "psycopg2", mandatory_parameters=False)

def get_basic_discovery_response():
    return {
        'primary_site_count': {},
        'treatment_type_count': {},
        'patients_per_program': {},
        'drug_type_count': {}
    }

async def get_individual_id(offset=0, limit=10, person_id=None):
    datasets = authx.auth.get_opa_datasets(request)
    if len(datasets) == 0:
        return []

    async with engine.connect() as conn:
        if person_id == None:
            # aiosql likes to swap params like :limit and :offset to %(limit)s and %(offset)s, which is unsafe
            # we swap it back before continuing
            transformed_sql = individual_queries.sql_get_individuals.sql \
                .replace("%(limit)s", ":limit") \
                .replace("%(offset)s", ":offset") \
                .replace("%(dataset_ids)s", ":dataset_ids")
            transformed_sql_text = text(transformed_sql).bindparams(bindparam('dataset_ids', expanding=True))
            records = (await conn.execute(transformed_sql_text, {"limit": limit, "offset": offset, "dataset_ids": datasets})).all()
            listId = [str(record[0]) for record in records]
        else:
            transformed_sql = individual_queries.sql_get_individual_id.sql.replace("%(person_id)s", ":person_id") \
                .replace("%(dataset_ids)s", ":dataset_ids")
            transformed_sql_text = text(transformed_sql).bindparams(bindparam('dataset_ids', expanding=True))
            records = (await conn.execute(transformed_sql, {"person_id": person_id, "dataset_ids": datasets})).fetchone()
            listId = [str(records[0])]
    return listId

async def get_individuals_person(listIds, filters_dict):
    dict_person = {}
    these_filters = filters_dict.copy()
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_person.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            these_filters["person_id"] = int(person_id)
            records = await conn.execute(transformed_sql, these_filters)
            # records = individual_queries.sql_get_person(engine, person_id=person_id)
            listValues = []
            for record in records:
                listValues.append({"gender_concept_id" : record[0],
                                    "race_concept_id" : record[1]})
            dict_person[person_id] = listValues
    return dict_person

async def get_individuals_dataset(listIds, filters_dict):
    dict_dataset = {}
    these_filters = filters_dict.copy()
    # Could maybe speedup by batching a few listIds?
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_dataset.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            these_filters["person_id"] = int(person_id)
            record = await conn.execute(transformed_sql, these_filters)
            db_id = record.fetchone()
            if db_id is not None:
                dict_dataset[person_id] = db_id[0]

    return dict_dataset

def get_datasets_allowed_filter(filters_dict, request_datasets=[], discovery=False):
    # Create a filter on allowed datasets for this user
    datasets = authx.auth.get_opa_datasets(request)

    if discovery:
        if len(request_datasets) > 0:
            # Discovery queries bypass authorization
            datasets = request_datasets
        else:
            return "and true", filters_dict
    else:
        # If the user has requested specific datasets, we filter down to only the ones they have permissions for
        if len(request_datasets) > 0:
            datasets = list(set(datasets) & set(request_datasets))

    if len(datasets) == 0:
        return "and false", filters_dict # No allowed datasets

    ret_filter = 'and exists (SELECT 1 FROM candig.person_in_dataset d where p.person_id = d.person_id and ('
    first = True
    for i, dataset in enumerate(datasets):
        if not first:
            ret_filter += ' or '
        first = False
        ret_filter += f' dataset_id = :dataset{i}'
        filters_dict[f'dataset{i}'] = dataset
    # Close both the exists clause and also the chain of dataset_id conditionals
    ret_filter += '))'
    return ret_filter, filters_dict

async def get_individuals_condition(listIds, filters_dict):
    dict_condition = {}
    these_filters = filters_dict.copy()
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_condition.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            these_filters["person_id"] = int(person_id)
            records = await conn.execute(transformed_sql, these_filters)
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

async def get_individuals_procedure(listIds, filters_dict):
    dict_procedure = {}
    these_filters = filters_dict.copy()
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_procedure.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            these_filters["person_id"] = int(person_id)
            records = await conn.execute(transformed_sql, these_filters)
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


async def get_individuals_measures(listIds, filters_dict):
    dict_measures = {}
    these_filters = filters_dict.copy()
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_measure.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            these_filters["person_id"] = int(person_id)
            records = await conn.execute(transformed_sql, these_filters)
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


async def get_individuals_exposures(listIds, filters_dict):
    dict_exposures = {}
    these_filters = filters_dict.copy()
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_exposure.sql.replace("%(person_id)s", ":person_id"))
        transformed_sql_duration = text(individual_queries.sql_get_exposure_period.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            these_filters["person_id"] = int(person_id)
            records = (await conn.execute(transformed_sql, these_filters)).fetchall()
            records_duration = (await conn.execute(transformed_sql_duration, these_filters)).fetchall()
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

async def get_individuals_treatments(listIds, filters_dict):
    dict_treatments = {}
    these_filters = filters_dict.copy()
    async with engine.connect() as conn:
        transformed_sql = text(individual_queries.sql_get_treatment.sql.replace("%(person_id)s", ":person_id"))
        for person_id in listIds:
            these_filters["person_id"] = int(person_id)
            records = await conn.execute(transformed_sql, these_filters)
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


def format_query(listIds, dictPerson, dictCondition, dictProcedures, dictMeasures, dictExposures, dictTreatments, dictDatasets):
    list_format = []
    for person_id in listIds:
        dictId = {"id":person_id, "dataset_id": dictDatasets[person_id]}
        if any("gender_concept_id" in d for d in dictPerson[person_id]):
            dictId["sex"] = dictPerson[person_id][0]["gender_concept_id"]
        if any("race_concept_id" in d for d in dictPerson[person_id]):
            dictId["ethnicity"] = dictPerson[person_id][0]["race_concept_id"]
        if any("condition_concept_id" in d for d in dictCondition[person_id]):
            diseases = list(map(mappings.diseases_table_map, dictCondition[person_id]))
            dictId["diseases"] = [disease for disease in diseases if disease['diseaseCode'] is not None]
        if any("procedure_concept_id" in d for d in dictProcedures[person_id]):
            procedures = list(map(mappings.procedures_table_map, dictProcedures[person_id]))
            # clean up any concept_id == 0 responses
            dictId["interventionsOrProcedures"] = [procedure for procedure in procedures if procedure['procedureCode'] is not None]
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

async def search_descendants(concept_id):
    async with engine.connect() as conn:
        get_descendants = individual_queries.sql_get_descendants.sql.replace("%(concept_id)s", ":concept_id")
        records = (await conn.execute(text(get_descendants), {"concept_id": concept_id})).fetchall()

    l_descendants = set()
    for descendant in records:
        l_descendants.add(descendant[0])
    return l_descendants

def safe_operator(operator):
    # We only support a small subset of operators (see beacon-schema.yml:components/schemas/AlphanumericFilter/properties/operator)
    # - '='
    # - <
    # - '>'
    # - '!'
    # - '>='
    # - <=
    if operator in ['=', '<', '>', '>=', '<=']:
        return operator
    if operator == '!':
        return '!='
    return '='

def safe_column_name(name):
    # https://www.postgresql.org/docs/7.0/syntax525.htm
    # Names in SQL must begin with a letter (a-z) or underscore (_). Subsequent characters in a name can be letters, digits (0-9), or underscores
    # Since none of the omop table column names involve quotation marks, I'm disallowing them here
    # We can revisit this later if the above is not a valid assumption
    return re.sub(r'[^a-zA-Z0-9_]', '', name)

def create_dynamic_filter(filters):
    base_filter = {
        'demographic_filters': '',
        'condition_filters': '',
        'measurement_filters': '',
        'procedures_filters': '',
        'exposures_filters': '',
        'treatments_filters': '',
    }
    filters_dict = {}
    request_datasets = []

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
    i = 0
    for filter in filters:
        # Default type of filter is ontology
        filterType = 'Ontology'
        if filter[2]:       # If filter has an operator (operator!=None) it is an Alphanumeric filter
            filterType = 'Alphanumeric'
        if "person" in filter[0]:
            variable_name = filter[0]['person']
            list_concept_id = []
            safe_var_name = safe_column_name(variable_name)
            for concept_id in filter[1]:
                filters_dict[f'value{i}'] = concept_id
                list_concept_id.append(f'{safe_var_name} = :value{i}')
                i += 1
            query_person_id =  ' or '.join(list_concept_id)
            list_person.append(' ( ' + query_person_id + ' ) ')
        if "condition_occurrence" in filter[0]:
            n_open_condition += 1
            variable_name = filter[0]['condition_occurrence']
            safe_var_name = safe_column_name(variable_name)
            list_concept_id = []
            for concept_id in filter[1]:
                if variable_name == 'Age':
                    operator = safe_operator(filter[2])
                    filters_dict[f'value{i}'] = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(condition_start_date, birth_datetime)) {operator} :value{i}
                            ELSE (extract(Year from condition_start_date) - year_of_birth)  {operator} :value{i}
                        END
                        """)
                else:
                    filters_dict[f'value{i}'] = concept_id
                    list_concept_id.append(f'{safe_var_name} = :value{i}')
                i += 1
            query_person_id =  ' or '.join(list_concept_id)
            # This can be a function to no repeat always the same -> filter[0]
            query_condition += f"""
                and exists (
                    select 1
                    from omop.condition_occurrence co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'measurement' in filter[0]:
            n_open_measurement += 1
            variable_name = filter[0]['measurement']
            list_concept_id = []
            for concept_id in filter[1]:
                safe_var_name = safe_column_name(variable_name)
                if variable_name == 'Age':
                    operator = safe_operator(filter[2])
                    filters_dict[f'value{i}'] = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(measurement_date, birth_datetime)) {operator} :value{i}
                            ELSE (extract(Year from measurement_date) - year_of_birth)  {operator} :value{i}
                        END
                        """)
                elif filterType == 'Alphanumeric':
                    operator = safe_operator(filter[2])
                    filters_dict[f'value{i}'] = filter[3]
                    filters_dict[f'concept{i}'] = str(concept_id)
                    list_concept_id.append(f'{safe_var_name} = :concept{i} and value_as_number {operator} :value{i}')
                else:
                    filters_dict[f'concept{i}'] = str(concept_id)
                    list_concept_id.append(f'{safe_var_name} = :concept{i}')
                i += 1
            query_person_id =  ' or '.join(list_concept_id)
            query_measurement += f"""
                and exists (
                    select 1
                    from omop.measurement co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'procedure_occurrence' in filter[0]:
            n_open_procedure += 1
            variable_name = filter[0]['procedure_occurrence']
            list_concept_id = []
            for concept_id in filter[1]:
                safe_var_name = safe_column_name(variable_name)
                if variable_name == 'Age':
                    operator = safe_operator(filter[2])
                    filters_dict[f'value{i}'] = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(procedure_date, birth_datetime)) {operator} :value{i}
                            ELSE (extract(Year from procedure_date) - year_of_birth)  {operator} :value{i}
                        END
                        """)
                else:
                    filters_dict[f'value{i}'] = concept_id
                    list_concept_id.append(f'{safe_var_name} = :value{i}')
                i += 1
            query_person_id =  ' or '.join(list_concept_id)
            query_procedure += f"""
                and exists (
                    select 1
                    from omop.procedure_occurrence co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'observation' in filter[0]:
            n_open_exposure += 1
            variable_name = filter[0]['observation']
            list_concept_id = []
            for concept_id in filter[1]:
                safe_var_name = safe_column_name(variable_name)
                if variable_name == 'Age':
                    operator = safe_operator(filter[2])
                    filters_dict[f'value{i}'] = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(observation_date, birth_datetime)) {operator} :value{i}
                            ELSE (extract(Year from observation_date) - year_of_birth)  {operator} :value{i}
                        END
                        """)
                else:
                    filters_dict[f'value{i}'] = concept_id
                    list_concept_id.append(f'{safe_var_name} = :value{i}')
                i += 1
            query_person_id =  ' or '.join(list_concept_id)
            query_exposure += f"""
                and exists (
                    select 1
                    from omop.observation co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'drug_exposure' in filter[0]:
            n_open_treatment += 1
            variable_name = filter[0]['drug_exposure']
            list_concept_id = []
            for concept_id in filter[1]:
                safe_var_name = safe_column_name(variable_name)
                if variable_name == 'Age':
                    operator = safe_operator(filter[2])
                    filters_dict[f'value{i}'] = filter[3]
                    list_concept_id.append(f"""
                        CASE
                            WHEN birth_datetime IS NOT NULL THEN extract(Year from age(drug_exposure_start_date, birth_datetime)) {operator} :value{i}
                            ELSE (extract(Year from drug_exposure_start_date) - year_of_birth)  {operator} :value{i}
                        END
                        """)
                else:
                    filters_dict[f'value{i}'] = concept_id
                    list_concept_id.append(f'{safe_var_name} = :value{i}')
                i += 1
            query_person_id =  ' or '.join(list_concept_id)
            query_treatment += f"""
                and exists (
                    select 1
                    from omop.drug_exposure co
                    where p.person_id = co.person_id
                    and ({query_person_id})
            """
        if 'dataset_ids' in filter[0]:
            # Are we dealing with a string or a list?
            if isinstance(filter[3], list):
                request_datasets.extend(filter[3])
            elif isinstance(filter[3], str):
                request_datasets.append(filter[3])
            else:
                logger.warning(f"Unknown dataset_ids data type: {type(filter[1])}")


    query_condition += ')'* n_open_condition
    query_measurement += ')'* n_open_measurement
    query_procedure += ')'* n_open_procedure
    query_exposure += ')'* n_open_exposure
    query_treatment += ')'* n_open_treatment

    if list_person:
        base_filter['demographic_filters'] += ' and ( ' + " and ".join(list_person) + ' ) '

    base_filter['condition_filters'] += query_condition
    base_filter['measurement_filters'] += query_measurement
    base_filter['procedures_filters'] += query_procedure
    base_filter['exposures_filters'] += query_exposure
    base_filter['treatments_filters'] += query_treatment
    base_filter['datasets_filters'], filters_dict = get_datasets_allowed_filter(filters_dict, request_datasets)
    base_filter['datasets_discovery_filters'], filters_dict = get_datasets_allowed_filter(filters_dict, request_datasets, discovery=True)

    return base_filter, filters_dict

def super_query_count(filter):
    return  f""" select count(distinct person_id)
        from omop.person p
        where true
        {filter['demographic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}
        {filter['datasets_filters']}

    """

def discovery_query_primary_site(filter):
    return  f""" SELECT c.concept_name, count(c.concept_name)
        FROM omop.condition_occurrence AS co
        LEFT JOIN omop.concept AS c ON c.concept_id = co.condition_concept_id
        LEFT JOIN omop.person AS p ON p.person_id = co.person_id
        WHERE c.concept_id != 0
        {filter['demographic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}
        {filter['datasets_discovery_filters']}
        GROUP BY c.concept_name
    """

def discovery_query_treatment_type(filter):
    return  f""" SELECT c.concept_name, count(c.concept_name)
        FROM omop.procedure_occurrence AS d
        LEFT JOIN omop.concept AS c ON c.concept_id = d.procedure_concept_id
        LEFT JOIN omop.person AS p ON p.person_id = d.person_id
        WHERE c.concept_id != 0
        {filter['demographic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}
        {filter['datasets_discovery_filters']}
        GROUP BY c.concept_name
    """

def discovery_query_drug_type(filter):
    return  f""" SELECT c.concept_name, count(c.concept_name)
        FROM omop.drug_exposure AS d
        LEFT JOIN omop.concept AS c ON c.concept_id = d.drug_concept_id
        LEFT JOIN omop.person AS p ON p.person_id = d.person_id
        WHERE c.concept_id != 0
        {filter['demographic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}
        {filter['datasets_discovery_filters']}
        GROUP BY c.concept_name
    """

def discovery_query_program(filter):
    return  f""" SELECT d.dataset_id, count(d.dataset_id)
        FROM candig.person_in_dataset AS d
        LEFT JOIN omop.person AS p ON p.person_id = d.person_id
        WHERE TRUE
        {filter['demographic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}
        {filter['datasets_discovery_filters']}
        GROUP BY d.dataset_id
    """

def super_query_get(filter, offset, limit):
    return  f""" select person_id
        from omop.person p
        where true
        {filter['demographic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}
        {filter['datasets_filters']}

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

async def format_filtered_discovery(discovery_query, filters_dict):
    retval = {}
    discovery_results = (await basic_query(discovery_query, filters_dict)).fetchall()
    for value, count in discovery_results:
        retval[value] = count
    return retval

async def get_discovery(base_filter, filters_dict):
    """
    Obtain the discovery query portion of the "info" response

    :param dictTableMap: dictionary of filters from create_dynamic_filter()
    """
    discovery = get_basic_discovery_response()
    discovery['primary_site_count'] = await format_filtered_discovery(discovery_query_primary_site(base_filter), filters_dict)
    discovery['treatment_type_count'] = await format_filtered_discovery(discovery_query_treatment_type(base_filter), filters_dict)
    discovery['patients_per_program'] = await format_filtered_discovery(discovery_query_program(base_filter), filters_dict)
    discovery['drug_type_count'] = await format_filtered_discovery(discovery_query_drug_type(base_filter), filters_dict)
    return discovery

async def checkFilters(filtersDict, offset, limit):
    listOfList = []
    dictTableMap = []
    typeQuery = request.method
    async with engine.connect() as conn:
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
                    return [], 0, get_basic_discovery_response(), {}
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
                                logger.info("You need a scope if you are using 'ageOfOnset'")
                            if "disease" in scope:
                                filterId = 'ageAtDisease'
                            elif "treatments" in scope:
                                filterId = 'ageAtTreatment'
                        tableMap = mapBeaconScopeToOMOP(filterId)
                        dictTableMap.append([tableMap, listConcept_id, operator, value])
                        continue

            else: # If GET
                filterId = filter

            if typeFilter=="Ontology" or typeFilter=="Alphanumeric":
                vocabulary_id, concept_code = filterId.split(':')

                # In most cases, we'll be looking through the concept domain to figure it out
                # However, there's a special exception: datasets don't exist in the concept domain
                # Instead, we'll pull them out here
                if vocabulary_id == 'dataset_id':
                    # This is a very weird adaptation to get create_dynamic_filter() to work
                    tableMap = {'dataset_ids': []}
                    listConcept_id = []
                    value = concept_code.split('|')
                else:
                    concept_domain_sql = text(individual_queries.sql_get_concept_domain.sql
                        .replace("%(vocabulary_id)s", ":vocabulary_id")
                        .replace("%(concept_code)s", ":concept_code"))
                    records = await conn.execute(concept_domain_sql,
                                                {
                                                    "vocabulary_id": vocabulary_id,
                                                    "concept_code": concept_code
                                                })
                    #records = individual_queries.sql_get_concept_domain(engine,
                    #                                                    vocabulary_id=vocabulary_id,
                    #                                                    concept_code=concept_code)
                    # Check if records is empty
                    if records.rowcount <= 0:
                        return [], 0, get_basic_discovery_response(), {}
                    records = records.fetchall()
                    for record in records:
                        original_concept_id = record[0]
                        domain_id = record[1]
                    listConcept_id.add(original_concept_id)
                    # Look in which domains the concept_id belongs
                    tableMap = map_domains(domain_id)
                    if includeDescendantTerms:
                        # Import descendants of the concept_id
                        concept_ids = await search_descendants(original_concept_id)
                        # Concept_id and descendants in same set()
                        listConcept_id = listConcept_id.union(concept_ids)
                dictTableMap.append([tableMap, listConcept_id, operator, value])
    # logger.info(dictTableMap)
    base_filter, filters_dict = create_dynamic_filter(dictTableMap)
    query_count = super_query_count(base_filter)
    count_records = (await basic_query(query_count, filters_dict)).fetchone()[0]

    # We also need the discovery query
    discovery = await get_discovery(base_filter, filters_dict)

    query_get = super_query_get(base_filter, offset, limit)
    # logger.info(query_get)
    records_get = await basic_query(query_get, filters_dict)
    listOfList = [str(record[0]) for record in records_get]

    return listOfList, count_records, discovery, filters_dict

# /individuals/?filters=SNOMED:0&filters=OMOP:23
async def filters(filtersDict, offset, limit):
    # There used to be a lot of code here, but now that we pass the connexion request it's all unnecessary
    return await checkFilters(filtersDict, offset, limit)

async def get_individuals(entry_id: Optional[str]=None, qparams: RequestParams=RequestParams()):

    schema = DefaultSchemas.INDIVIDUALS
    count_ids = 0
    discovery_data = {}
    if qparams.query.pagination.limit == 0:
        qparams.query.pagination.limit = MAX_LIMIT
    if qparams.query.filters and len(qparams.query.filters) > 0 and len(qparams.query.filters[0]) > 0:
        # NB: qparams.query.filters is a list, whereas we need it to be a dict?
        listIds, count_ids, discovery_data, filters_dict = await filters(qparams.query.filters[0],
                                                                        offset=qparams.query.pagination.skip,
                                                                        limit=qparams.query.pagination.limit)
        if count_ids == 0:
            return schema, count_ids, [], discovery_data
    else:
        datasets = authx.auth.get_opa_datasets(request)
        if len(datasets) == 0:
            listIds = []
            count_ids = 0
        else:
            listIds = await get_individual_id(offset=qparams.query.pagination.skip,
                                                limit=qparams.query.pagination.limit,
                                                person_id=entry_id)                 # List with all Ids
            async with engine.connect() as conn:
                count_sql_text = text(individual_queries.count_individuals.sql \
                    .replace("%(dataset_ids)s", ":dataset_ids"))
                count_sql_text = count_sql_text.bindparams(bindparam("dataset_ids", expanding=True))
                count_ids = await conn.execute(count_sql_text, {"dataset_ids": datasets})
                count_ids = count_ids.first()[0]

        base_filter, filters_dict = create_dynamic_filter([])
        discovery_data = await get_discovery(base_filter, filters_dict)

    # logger.info(f"Number of ids: ${count_ids}")

    # NB: I'm concerned about the memory usage of the following

    dictPerson = await get_individuals_person(listIds, filters_dict)        # List with Id, sex, ethnicity
    dictCondition = await get_individuals_condition(listIds, filters_dict)  # List with al the diseases per Id
    dictProcedures = await get_individuals_procedure(listIds, filters_dict)
    dictMeasures = await get_individuals_measures(listIds, filters_dict)
    dictExposures = await get_individuals_exposures(listIds, filters_dict)
    dictTreatments = await get_individuals_treatments(listIds, filters_dict)
    dictDatasets = await get_individuals_dataset(listIds, filters_dict)

    dictPerson = await search_ontologies(dictPerson)
    dictCondition = await search_ontologies(dictCondition)
    dictProcedures = await search_ontologies(dictProcedures)
    dictMeasures = await search_ontologies(dictMeasures)
    dictExposures = await search_ontologies(dictExposures)
    dictTreatments = await search_ontologies(dictTreatments)

    # Join the persons with the datasets table, to figure out who is from where

    docs = format_query(listIds, dictPerson, dictCondition, dictProcedures, dictMeasures, dictExposures, dictTreatments, dictDatasets)

    return schema, count_ids, docs, discovery_data



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
    # logger.info(l_indFilters)
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
    # logger.debug(individual_ids)
    # individual_ids=get_cross_query(individual_ids,'id','caseLevelData.biosampleId')
    # logger.debug(individual_ids)
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
