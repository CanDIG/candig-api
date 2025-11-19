#from ..beacon.request.handlers import filtering_terms_handler
from ..beacon.omop import datasets #filtering_terms
from ..beacon.omop.schemas import DefaultSchemas
from ..beacon.response import framework, service_info, build_response
from ..beacon.request import RequestParams
from ..beacon.request.model import Granularity
from ..beacon.response.build_response import (
    build_beacon_resultset_response,
    build_beacon_collection_response,
    build_beacon_boolean_response,
    build_beacon_count_response,
    build_filtering_terms_response,
)

import logging

LOG = logging.getLogger(__name__)

API_VERSION = '1.0.0'
BEACON_ID = 'org.candig.api.beacon'

async def init_omop():
    init()

# /datasets/info
async def get_beacon_info_root():
    return service_info.handler

# /datasets/filtering_terms
async def get_filtering_terms():
    # We have return values from individuals.get_filtering_terms_of_individual
    # and biosamples.get_filtering_terms_of_biosample
    # Unsure what we want to return, per se. There's a datasets.get_filtering_terms_of_dataset but it's a TODO?
    #return filtering_terms_handler(db_fn=filtering_terms.get_filtering_terms)
    return {}, 200

# /datasets/filtering_terms
async def post_filtering_terms():
    # ??? The beacon.routes has this as the same thing as the GET, for some reason -- need to investigate
    #return filtering_terms_handler(db_fn=filtering_terms.get_filtering_terms)
    return {}, 200

# /datasets/configuration
async def get_beacon_configuration():
    #return framework.configuration
    return {}, 200

# /datasets/map
async def get_beacon_map():
    #return framework.beacon_map
    return {}, 200

# /datasets/entry_types
async def get_entry_types():
    #return framework.entry_types
    return {}, 200

# /datasets/
async def post(body: dict):
    retval = {}
    # Figure out what kind of search we should be doing (see beacon/request/routes)
    LOG.info(body)
    params = RequestParams(**body) #.from_request(body)

    # Pass out the parsed search parameters to SQL (see beacon/omop/)
    LOG.info(params)
    schema, count, records = await datasets.get_datasets(None, params)
    # DEBUG: count/records aren't returning right now with the thing, so to test I'm just gonna use empty responses
    #schema = DefaultSchemas.DATASETS
    #count = 0
    #records = []

    # Fill out the return value with all parameters that belong there (see beacon/response/build_response)
    #response = build_beacon_boolean_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
    retval = build_beacon_boolean_response(records, count, params, lambda x, y: x, schema)
    return retval, 200