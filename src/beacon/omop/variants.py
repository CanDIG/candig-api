import os
import re
import requests

from connexion import request
from typing import Optional, List
from ...beacon.omop.utils import  basic_query
from .individuals import parseFilters
from .utils import search_htsget, get_samples_from_htsget_response, create_samples_filter
import aiosql
from sqlalchemy import text, bindparam
from ..conf import MAX_LIMIT

from pathlib import Path
from candigv2_logging.logging import CanDIGLogger

logger = CanDIGLogger(__file__)

queries_file = Path(__file__).parent / "sql" / "individuals.sql"
individual_queries = aiosql.from_path(queries_file, "psycopg2", mandatory_parameters=False)

CANDIG_URL = os.getenv("CANDIG_URL", "")
HTSGET_URL = os.getenv("HTSGET_URL", f"{CANDIG_URL}/genomics")


def create_sample_query(filter):
    return  f""" select d.sample_id
        from omop.person p
        left join candig.sample d ON p.person_id = d.person_id
        where true
        {filter['demographic_filters']}
        {filter['condition_filters']}
        {filter['measurement_filters']}
        {filter['procedures_filters']}
        {filter['exposures_filters']}
        {filter['treatments_filters']}
        {filter['datasets_filters']}
        {filter['genomics_filters']}
    """


async def get_variants(qparams: dict):
    # Pass the g_variants part of the request off to HTSGet
    htsget = search_htsget(qparams)

    # If there are no clinical filters, we can just return the HTSGet response here
    filter_params = []
    if qparams.query.filters and len(qparams.query.filters) > 0 and len(qparams.query.filters[0]) > 0:
        filter_params = qparams.query.filters[0]
    if len(filter_params) == 0:
        return htsget

    # Obtain all genomic samples hit
    samples = get_samples_from_htsget_response(htsget)

    # If there's no samples hit, return early
    if len(samples) == 0:
        return htsget

    # Create a genomic filter with a bunch of entries
    genomics_filters, genomic_filters_dict = create_samples_filter(samples, {})
    extra_filters = {}
    extra_filters['genomics_filters'] = genomics_filters

    # Perform a clinical search via the code we have in individuals
    base_filter, filters_dict = await parseFilters(filter_params,
                                                    extra_filters=extra_filters,
                                                    extra_filters_dict=genomic_filters_dict)
    query_get = create_sample_query(base_filter)
    records_get = await basic_query(query_get, filters_dict)

    # Cut down the genomic samples to whatever samples remain in the individuals search
    # Convert the list into a dict for faster lookup O(1) instead of O(n)
    found_samples = {}
    for record in records_get:
        found_samples[str(record[0])] = True
    
    # Remove all entries whose dataset_id~submitter_sample_id does not exist in found_samples
    programs_to_remove = []
    for program, results in htsget.get('estimatedResults', {}).items():
        if not isinstance(results, list):
            continue
        items_to_remove = []
        for item in results:
            if f"{program}~{item['submitter_sample_id']}" not in found_samples:
                items_to_remove.append(item)
        for item in items_to_remove:
            results.remove(item)
        if len(results) == 0:
            programs_to_remove.append(program)
    for program in programs_to_remove:
        del htsget['estimatedResults'][program]

    # Return the HTSGet
    return htsget
