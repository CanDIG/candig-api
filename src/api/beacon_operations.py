#from ..beacon.request.handlers import filtering_terms_handler
from ..beacon.omop import datasets, filtering_terms, individuals
from ..beacon.omop.schemas import DefaultSchemas
from ..beacon.response import framework, service_info, build_response
from ..beacon.request import RequestParams
from ..beacon.request.model import Granularity
from ..beacon import conf
from ..beacon.response.build_response import (
    build_beacon_resultset_response,
    #build_beacon_collection_response,
    build_beacon_boolean_response,
    build_beacon_count_response,
    build_filtering_terms_response,
)

import logging

LOG = logging.getLogger(__name__)

API_VERSION = '1.0.0'
BEACON_ID = 'org.candig.api.beacon'

# /datasets/info
async def get_beacon_info_root():
    return service_info.handler

# /datasets/filtering_terms
async def get_filtering_terms(skip: int = 0, limit: int = 0):
    # We have return values from individuals.get_filtering_terms_of_individual
    # and biosamples.get_filtering_terms_of_biosample
    # Unsure what we want to return, per se. There's a datasets.get_filtering_terms_of_dataset but it's a TODO?
    #return filtering_terms_handler(db_fn=filtering_terms.get_filtering_terms), 200
    req_params = {"skip": skip, "limit": limit}
    qparams = RequestParams(**req_params).from_request(req_params)

    entity_schema, count, records = await filtering_terms.get_filtering_terms(None, qparams)
    LOG.info(records)
    # Get response
    response = build_filtering_terms_response(records, count, qparams, lambda x, y: x, entity_schema )
    return response, 200

# /datasets/filtering_terms
async def post_filtering_terms(skip: int = 0, limit: int = 0):
    # ??? The beacon.routes has this as the same thing as the GET, for some reason -- need to investigate
    #return filtering_terms_handler(db_fn=filtering_terms.get_filtering_terms)
    return await get_filtering_terms(skip, limit)

# /datasets/configuration
async def get_beacon_configuration():
    return await framework.configuration()

# /datasets/map
async def get_beacon_map():
    return await framework.beacon_map()

# /datasets/entry_types
async def get_entry_types():
    return framework.entry_types()

# /datasets/
async def post(body: dict):
    retval = {}
    # Figure out what kind of search we should be doing (see beacon/request/routes)
    #LOG.info(body)
    params = RequestParams(**body).from_request(body)

    # Pass out the parsed search parameters to SQL (see beacon/omop/)
    #LOG.info(params)
    schema, count, records = await datasets.get_datasets(None, params)

    # Fill out the return value with all parameters that belong there (see beacon/response/build_response)
    # Start by assuming max granularity, and downgrade as needed
    granularity = Granularity.RECORD
    if conf.max_beacon_granularity != Granularity.RECORD or params.query.requested_granularity != Granularity.RECORD:
        granularity = Granularity.COUNT
        if conf.max_beacon_granularity == Granularity.BOOLEAN or params.query.requested_granularity == Granularity.BOOLEAN:
            granularity = Granularity.BOOLEAN

    # Format proper response
    if (granularity == Granularity.RECORD):
        retval = build_beacon_resultset_response(records, count, params, lambda x, y: x, schema)
    elif granularity == Granularity.COUNT:
        retval = build_beacon_count_response(records, count, params, lambda x, y: x, schema)
    else:
        retval = build_beacon_boolean_response(records, count, params, lambda x, y: x, schema)

    #LOG.info(retval)
    return retval, 200

# /persons/
async def post_person(body: dict):
    retval = {}
    # Figure out what kind of search we should be doing (see beacon/request/routes)
    #LOG.info(body)
    params = RequestParams(**body).from_request(body)

    # Pass out the parsed search parameters to SQL (see beacon/omop/)
    #LOG.info(params)
    schema, count, records = await individuals.get_individuals(None, params)

    # Fill out the return value with all parameters that belong there (see beacon/response/build_response)
    # Start by assuming max granularity, and downgrade as needed
    granularity = Granularity.RECORD
    if conf.max_beacon_granularity != Granularity.RECORD or params.query.requested_granularity != Granularity.RECORD:
        granularity = Granularity.COUNT
        if conf.max_beacon_granularity == Granularity.BOOLEAN or params.query.requested_granularity == Granularity.BOOLEAN:
            granularity = Granularity.BOOLEAN

    # Format proper response
    if (granularity == Granularity.RECORD):
        retval = build_beacon_resultset_response(records, count, params, lambda x, y: x, schema)
    elif granularity == Granularity.COUNT:
        retval = build_beacon_count_response(records, count, params, lambda x, y: x, schema)
    else:
        retval = build_beacon_boolean_response(records, count, params, lambda x, y: x, schema)

    return retval, 200