import logging
import aiosql
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from ...beacon.omop.filters import apply_filters
from ...beacon.omop.schemas import DefaultSchemas
from ...beacon.request.model import RequestParams
from ...beacon.omop import client as conn
from ...beacon.omop.utils import  search_ontologies, basic_query
from ...beacon.omop.individuals import get_individuals, get_cohort_individuals # build_filters
import pandas as pd

LOG = logging.getLogger(__name__)

queries_file = Path(__file__).parent / "sql" / "cohorts.sql"
queries = aiosql.from_path(queries_file, "psycopg2")

cohort_type = 'beacon-defined'

# Need location data to test
def disease_criteria(cohortBasicInfo):
    if cohortBasicInfo['individuals']:
        diseases = queries.get_condition_per_person(conn, person_ids = cohortBasicInfo['individuals'])
    else:
        diseases = queries.get_condition(conn)

    list_diseases = []
    for disease in diseases:
        dict_disease = {"diseaseCode": {"label": disease[0],
                       "id": disease[1]}}
        list_diseases.append(dict_disease)

    return list_diseases

# Need location data to test
def location_criteria(cohortBasicInfo):
    if cohortBasicInfo['individuals']:
        locations = queries.get_location_per_person(conn, person_ids = cohortBasicInfo['individuals'])
    else:
        locations = queries.get_location(conn)

    list_locations = []
    for location in locations:
        dict_location = {"label": location[0],
                       "id": location[1]}
        list_locations.append(dict_location)

    return list_locations

def gender_criteria(cohortBasicInfo):
    if cohortBasicInfo['individuals']:
        genders = queries.get_gender_per_person(conn, person_ids = cohortBasicInfo['individuals'])
    else:
        genders = queries.get_gender(conn)
    list_genders = []

    for gender in genders:
        dict_gender = {"label": gender[0],
                       "id": gender[1]}
        list_genders.append(dict_gender)
    
    return list_genders

def cohort_data_types():
    return [{
            "id": "OGMS:0000015",
            "label": "clinical history"
        }]

def dataAvailabilityAndDistributionFunction(eventData):
    
    dict_distribution = {}
    count_ind = 0
    for event in eventData:
        count_ind += int(event[1])
        dict_distribution[str(event[0])] = event[1]

    if not dict_distribution:
        return {"availability": False}

    return {
        "availability": True,
        "availabilityCount":count_ind,
        "distribution":dict_distribution
    }

def createEvent(cohortBasicInfo):
    if cohortBasicInfo['individuals']:
        year_per_person = queries.get_year_of_birth_count_per_person(conn, person_ids = cohortBasicInfo['individuals'])
        sex_per_person = queries.get_gender_count_per_person(conn, person_ids = cohortBasicInfo['individuals'])
        disease_per_person = queries.get_condition_count_person(conn, person_ids = cohortBasicInfo['individuals'])
        eventSize = len(cohortBasicInfo['individuals'])

    else:   # For all individuals
        year_per_person = queries.get_year_of_birth_count(conn)
        sex_per_person = queries.get_gender_count(conn)
        disease_per_person = queries.get_condition_count(conn)
        eventSize = queries.get_cohort_count(conn)

    distributionAge = dataAvailabilityAndDistributionFunction(year_per_person)
    distributionSex = dataAvailabilityAndDistributionFunction(sex_per_person)
    distributionDiseases = dataAvailabilityAndDistributionFunction(disease_per_person)


    return {
        "eventAgeRange": {
            "availability": distributionAge['availability'],
            "availabilityCount": distributionAge['availabilityCount'],
            "distribution": {
                "year": distributionAge['distribution']
            }
        },
        "eventNum": 1,
        "eventDate": cohortBasicInfo['cohort']['date'],
        "eventGenders": {
            "availability": distributionSex['availability'],
            "availabilityCount": distributionSex['availabilityCount'],
            "distribution": {
                "genders": distributionSex['distribution']
            }
        },
        "eventDiseases": {
            "availability": distributionDiseases['availability'],
            "availabilityCount": distributionDiseases['availabilityCount'],
            "distribution": {
                "diseases": distributionDiseases['distribution']
            }
        },
        
        "eventSize": eventSize
        }

def create_cohort_model(cohortBasicInfo):

    if not cohortBasicInfo['individuals']:      # All database
        cohortSize = queries.get_cohort_count(conn)
        min_age, max_age = queries.get_age_range(conn)

    else:
        cohortSize = len(cohortBasicInfo['individuals'])
        min_age, max_age = queries.get_age_range_person(conn, person_ids=cohortBasicInfo['individuals'])


    cohort = {
        'id': str(cohortBasicInfo['cohort']['id']),
        'name': cohortBasicInfo['cohort']['name'],
        'cohortDataTypes': cohort_data_types(),
        'cohortSize': cohortSize,
        'cohortType': cohort_type,
        'collectionEvents': [createEvent(cohortBasicInfo)],
        "inclusionCriteria": {
            'ageRange' : {
                "end": {
                    "iso8601duration": f"P{max_age}Y"
                },
                "start": {
                    "iso8601duration": f"P{min_age}Y"
                }
            },
            'genders': gender_criteria(cohortBasicInfo),
            'locations': location_criteria(cohortBasicInfo),
            'diseaseConditions':disease_criteria(cohortBasicInfo)
        }
    }
    return cohort

# def create_cohort(entry_id: Optional[str]=None, qparams: RequestParams=None):
#     # collection = 'cohorts'
#     # query = apply_filters({}, qparams.query.filters, collection)
#     # schema = DefaultSchemas.COHORTS
#     # count = get_count(client.beacon.cohorts, query)
#     # docs = get_documents(
#     #     client.beacon.cohorts,
#     #     query,
#     #     qparams.query.pagination.skip,
#     #     qparams.query.pagination.limit
#     # )

#     print(qparams)
#     filters = []
#     filter = build_filters(filters)

#     query = f""" select count(distinct person_id)
#         from cdm.person p
#         where true
#         {filter['demografic_filters']}
#         {filter['condition_filters']}
#         {filter['measurement_filters']}
#         {filter['procedures_filters']}
#         {filter['exposures_filters']}

#     """
#     entry_id = basic_query(query)

#     collection = 'cohorts'    
#     schema = DefaultSchemas.COHORTS
#     count = 1
#     docs = [cohort] 
#     return schema, count, docs

def search_cohorts(isAll):
    list_cohorts = []
    if isAll:
        dict_cohort = {'id': '0', 'date': date.today().isoformat(),
                       'name':"All patients"}
        individuals=[]
        list_cohorts.append({'cohort':dict_cohort, 'individuals': individuals})

    cohorts=queries.get_all_cohorts(conn)
    for cohort in cohorts:
        dict_cohort = {'id': cohort[0], 'date': cohort[1],
                       'name':cohort[2]}
        individuals=[ind[0] for ind in queries.get_cohort_individuals(conn, cohort_id=cohort[0])]

        list_cohorts.append({'cohort':dict_cohort, 'individuals': individuals})
    return list_cohorts

def search_single_cohort(cohort_id):
    if int(cohort_id)==0:
        dict_cohort = {'id': '0', 'date': date.today().isoformat(),
                       'name':"All patients"}
        individuals=[]
        return {'cohort':dict_cohort, 'individuals': individuals}
    
    print(cohort_id, type(cohort_id))
    cohorts=queries.get_single_cohort(conn, cohort_id=cohort_id)
    for cohort in cohorts:
        dict_cohort = {'id': str(cohort[0]), 'date': cohort[1],
                       'name':cohort[2]}
        individuals=[ind[0] for ind in queries.get_cohort_individuals(conn, cohort_id=cohort[0])]

    return {'cohort':dict_cohort, 'individuals': individuals}

def get_cohorts(entry_id: Optional[str]=None, qparams: RequestParams=None):
    
    collection = 'cohorts'    
    schema = DefaultSchemas.COHORTS
    list_cohorts = search_cohorts(isAll=True)
    count = len(list_cohorts)
    docs = []
    for cohort in list_cohorts:
        docs.append(create_cohort_model(cohort))
    return schema, count, docs


def get_cohort_with_id(entry_id: Optional[str], qparams: RequestParams):
    collection = 'cohorts'
    schema = DefaultSchemas.COHORTS
    count = 1
    cohortBasicInfo = search_single_cohort(entry_id)
    print(cohortBasicInfo)
    docs = [create_cohort_model(cohortBasicInfo)]
    return schema, count, docs


def get_individuals_of_cohort(entry_id: Optional[str], qparams: RequestParams):
    # collection = 'cohorts'
    # query = apply_filters({}, qparams.query.filters, collection)
    # query = query_id(query, entry_id)
    # count = get_count(client.beacon.cohorts, query)
    # cohort_ids = client.beacon.cohorts \
    #     .find_one(query, {"ids.individualIds": 1, "_id": 0})
    # cohort_ids=get_cross_query(cohort_ids['ids'],'individualIds','id')
    # query = apply_filters(cohort_ids, qparams.query.filters)

    # schema = DefaultSchemas.INDIVIDUALS
    # count = get_count(client.beacon.individuals, query)
    # docs = get_documents(
    #     client.beacon.individuals,
    #     query,
    #     qparams.query.pagination.skip,
    #     qparams.query.pagination.limit
    # )

    print(entry_id)
    if entry_id == '1':
        print('all individuals')
        return get_individuals(qparams=qparams)
    else:
        return get_cohort_individuals(entry_id, 
                                  offset=qparams.query.pagination.skip,
                                  limit=qparams.query.pagination.limit)


def get_filtering_terms_of_cohort(entry_id: Optional[str], qparams: RequestParams):
    # TODO
    pass
