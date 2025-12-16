
import json
import logging
#from aiohttp import web
#from aiohttp.web_request import Request
#from bson import json_util
from ...beacon import conf

from ...beacon.request import ontologies
from ...beacon.request.model import Granularity, RequestParams
from ...beacon.response.build_response import (
    build_beacon_resultset_response,
    build_beacon_collection_response,
    build_beacon_boolean_response,
    build_beacon_count_response,
    build_filtering_terms_response,
)
from ...beacon.utils.stream import json_stream

LOG = logging.getLogger(__name__)


def collection_handler(db_fn, request=None):
    #async def wrapper(request: Request):
    async def wrapper(request):

        # Get params
        json_body = await request.json() if request.method == "POST" and request.has_body and request.can_read_body else {}
        qparams = RequestParams(**json_body).from_request(request)
        entry_id = request.match_info["id"] if "id" in request.match_info else None

        # Get response
        entity_schema, count, records = db_fn(entry_id, qparams)
        response_converted = (
            [r for r in records] if records else []
        )
        response = build_beacon_collection_response(
            response_converted, count, qparams, lambda x, y: x, entity_schema
        )
        return await json_stream(request, response)

    return wrapper


def generic_handler(db_fn, request=None):
    #async def wrapper(request: Request):
    async def wrapper(request):
        # Get params
        json_body = await request.json() if request.method == "POST" and request.has_body and request.can_read_body else {}
        qparams = RequestParams(**json_body).from_request(request)
        entry_id = request.match_info.get('id', None)

        # Get response
        entity_schema, count, records = db_fn(entry_id, qparams)
        response_converted = records

        response = None

        if conf.max_beacon_granularity == Granularity.BOOLEAN:              # BOOLEAN x ( BOOLEAN or COUNT or RECORD ) = BOOLEAN
            response = build_beacon_boolean_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
        elif conf.max_beacon_granularity == Granularity.COUNT:
            if qparams.query.requested_granularity == Granularity.BOOLEAN:  # COUNT x BOOLEAN = BOOLEAN
                response = build_beacon_boolean_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
            else:                                                           # COUNT x ( COUNT or RECORD ) = COUNT
                response = build_beacon_count_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
        elif conf.max_beacon_granularity == Granularity.RECORD:
            if qparams.query.requested_granularity == Granularity.BOOLEAN:  # RECORD x BOOLEAN = BOOLEAN
                response = build_beacon_boolean_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
            elif qparams.query.requested_granularity == Granularity.COUNT:  # RECORD x COUNT = COUNT
                response = build_beacon_count_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
            elif qparams.query.requested_granularity == Granularity.RECORD: # RECORD x RECORD = RECORD
                response = build_beacon_resultset_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
            else:                                                           # DEFAULT = BOOLEAN
                response = build_beacon_boolean_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
        else:                                                               # DEFAULT = BOOLEAN
            response = build_beacon_boolean_response(response_converted, count, qparams, lambda x, y: x, entity_schema)
                
        return await json_stream(request, response)

    return wrapper


def filtering_terms_handler(db_fn, request=None):
    #async def wrapper(request: Request):
    async def wrapper(request):
        # Get params
        json_body = await request.json() if request.method == "POST" and request.has_body and request.can_read_body else {}
        qparams = RequestParams(**json_body).from_request(request)

        entry_id =request.match_info.get('id', None)
        entity_schema, count, records = db_fn(entry_id, qparams)
        # entity_schema, count, records = db_fn
        # Get response
        response = build_filtering_terms_response(records, count, qparams, lambda x, y: x, entity_schema )
        return await json_stream(request, response)

    return wrapper
