from typing import Optional
from ...beacon.omop.filters import apply_filters
from ...beacon.omop.schemas import DefaultSchemas
from ...beacon.omop.utils import get_count, get_documents, format_mongo_query
from ...beacon.request.model import RequestParams
from ...database.dataset import Dataset

import logging

LOG = logging.getLogger(__name__)


async def get_datasets(entry_id: Optional[str], qparams: RequestParams):
    collection = 'datasets'
    query = apply_filters({}, qparams.query.filters, collection)
    schema = DefaultSchemas.DATASETS
    count = await get_count(f"candig.dataset", query)
    docs = await get_documents(
        Dataset.__table__.columns,
        format_mongo_query(f"candig.dataset", query),
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs


def get_dataset_with_id(entry_id: Optional[str], qparams: RequestParams):
    collection = 'datasets'
    query = apply_filters({}, qparams.query.filters, collection)
    query["id"] = entry_id
    schema = DefaultSchemas.DATASETS
    count = get_count(f"candig.dataset", query)
    docs = get_documents(
        Dataset.__table__.columns,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs

