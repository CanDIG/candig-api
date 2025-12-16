from typing import Optional
from ...beacon.omop.filters import apply_filters
from ...beacon.omop.schemas import DefaultSchemas
from ...beacon.omop.utils import query_id, get_count, get_documents, get_cross_query, format_mongo_query
from ...beacon.request.model import RequestParams
from ...beacon.omop import engine # client
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
    query = query_id(query, entry_id)
    schema = DefaultSchemas.DATASETS
    count = get_count(f"candig.dataset", query)
    docs = get_documents(
        Dataset.__table__.columns,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs


def get_variants_of_dataset(entry_id: Optional[str], qparams: RequestParams):
    collection = 'datasets'
    query = {"_info.datasetId": entry_id}
    query = apply_filters(query, qparams.query.filters, collection)
    schema = DefaultSchemas.GENOMICVARIATIONS
    count = get_count(engine.beacon.genomicVariations, query)
    docs = get_documents(
        engine.beacon.genomicVariations,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs


def get_biosamples_of_dataset(entry_id: Optional[str], qparams: RequestParams):
    collection = 'datasets'
    query = apply_filters({}, qparams.query.filters, collection)
    query = query_id(query, entry_id)
    count = get_count(engine.beacon.datasets, query)
    biosample_ids = engine.beacon.datasets \
        .find_one(query, {"ids.biosampleIds": 1, "_id": 0})
    biosample_ids=get_cross_query(biosample_ids['ids'],'biosampleIds','id')
    query = apply_filters(biosample_ids, qparams.query.filters, collection)

    schema = DefaultSchemas.BIOSAMPLES
    count = get_count(engine.beacon.biosamples, query)
    docs = get_documents(
        engine.beacon.biosamples,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs


def get_individuals_of_dataset(entry_id: Optional[str], qparams: RequestParams):
    collection = 'datasets'
    query = apply_filters({}, qparams.query.filters, collection)
    query = query_id(query, entry_id)
    count = get_count(engine.beacon.datasets, query)
    individual_ids = engine.beacon.datasets \
        .find_one(query, {"ids.individualIds": 1, "_id": 0})
    individual_ids=get_cross_query(individual_ids['ids'],'individualIds','id')
    query = apply_filters(individual_ids, qparams.query.filters, collection)

    schema = DefaultSchemas.INDIVIDUALS
    count = get_count(engine.beacon.individuals, query)
    docs = get_documents(
        engine.beacon.individuals,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs


def filter_public_datasets(requested_datasets_ids):
    query = {"dataUseConditions.duoDataUse.modifiers.id": "DUO:0000004"}
    return engine.beacon.datasets \
        .find(query)


def get_filtering_terms_of_dataset(entry_id: Optional[str], qparams: RequestParams):
    # TODO
    pass


def get_runs_of_dataset(entry_id: Optional[str], qparams: RequestParams):
    collection = 'datasets'
    query = apply_filters({}, qparams.query.filters, collection)
    query = query_id(query, entry_id)
    count = get_count(engine.beacon.datasets, query)
    biosample_ids = engine.beacon.datasets \
        .find_one(query, {"ids.biosampleIds": 1, "_id": 0})
    biosample_ids=get_cross_query(biosample_ids['ids'],'biosampleIds','biosampleId')
    query = apply_filters(biosample_ids, qparams.query.filters, collection)

    schema = DefaultSchemas.RUNS
    count = get_count(engine.beacon.runs, query)
    docs = get_documents(
        engine.beacon.runs,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs


def get_analyses_of_dataset(entry_id: Optional[str], qparams: RequestParams):
    collection = 'datasets'
    query = apply_filters({}, qparams.query.filters, collection)
    query = query_id(query, entry_id)
    count = get_count(engine.beacon.datasets, query)
    biosample_ids = engine.beacon.datasets \
        .find_one(query, {"ids.biosampleIds": 1, "_id": 0})
    biosample_ids=get_cross_query(biosample_ids['ids'],'biosampleIds','biosampleId')
    query = apply_filters(biosample_ids, qparams.query.filters, collection)

    schema = DefaultSchemas.ANALYSES
    count = get_count(engine.beacon.analyses, query)
    docs = get_documents(
        engine.beacon.analyses,
        query,
        qparams.query.pagination.skip,
        qparams.query.pagination.limit
    )
    return schema, count, docs
