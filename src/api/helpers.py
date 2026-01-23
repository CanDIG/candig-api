"""
Helper functions for data ingestion
"""

from candigv2_logging.logging import CanDIGLogger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.database.insert_operations import (
    create_condition_occurrence,
    create_death,
    create_drug_exposure,
    create_episode,
    create_episode_event,
    create_fact_relationship,
    create_measurement,
    create_observation,
    create_procedure_occurrence,
    create_specimen,
    create_visit_occurrence,
)

from typing import Any, Dict

from src.database.db_operations import get_db_session
from src.database.insert_operations import (
    create_dataset,
    create_person,
    create_person_in_dataset,
)
from src.config import settings
from connexion.exceptions import ProblemException
from typing import List, Tuple, Optional
import json
import os

logger = CanDIGLogger(__file__)

# ==============================================================================
# Mapping for each OMOP table
# ==============================================================================
TABLE_FUNCTION_MAPPING = {
    "observation": {
        "pk": "observation_id",
        "fk_map": {
            "observation_event_id": "observation_event_id",
        },
        "create_func": create_observation,
    },
    "death": {
        "pk": None,  # Death table's PK is the person_id FK.
        "create_func": create_death,
    },
    "condition_occurrence": {
        "pk": "condition_occurrence_id",
        "create_func": create_condition_occurrence,
    },
    "episode": {
        "pk": "episode_id",
        "create_func": create_episode,
    },
    "episode_event": {
        "pk": None,
        "fk_map": {"episode_id": "episode_id", "event_id": "event_id"},
        "create_func": create_episode_event,
    },
    "measurement": {
        "pk": "measurement_id",
        "fk_map": {
            "measurement_event_id": "measurement_event_id",
        },
        "create_func": create_measurement,
    },
    "specimen": {
        "pk": "specimen_id",
        "create_func": create_specimen,
    },
    "procedure_occurrence": {
        "pk": "procedure_occurrence_id",
        "create_func": create_procedure_occurrence,
    },
    "drug_exposure": {
        "pk": "drug_exposure_id",
        "create_func": create_drug_exposure,
    },
    "fact_relationship": {
        "pk": None,
        "fk_map": {"fact_id_1": "fact_id_1", "fact_id_2": "fact_id_2"},
        "create_func": create_fact_relationship,
    },
    "visit_occurrence": {
        "pk": "visit_occurrence_id",
        "create_func": create_visit_occurrence,
    },
}


# ==============================================================================
# Create object in OMOP
# ==============================================================================
async def create_record(
    session: AsyncSession,
    ref_id_table: dict,
    record_fields: dict,
    table_name: str,
    person_id: int,
) -> dict:
    """
    Function to process and create a single OMOP record.
    """
    mapping = TABLE_FUNCTION_MAPPING[table_name]

    # 1. Pop the PK from payload since we don't need it for ingest,
    # but make the reference for mapping
    pk_field = mapping.get("pk")
    pk_ref = record_fields.pop(pk_field, None) if pk_field else None

    # 2. Link the FK from existing mapping
    for fk_field_name in mapping.get("fk_map", {}):
        fk_ref = record_fields.get(fk_field_name, None)
        if fk_ref:
            actual_fk_id = ref_id_table.get(fk_ref)
            if actual_fk_id is None:
                raise ProblemException(
                    status=422,
                    title="Missing Foreign Key in Mapping Table",
                    detail=(
                        f"The FK '{fk_ref}' was not found in the mapping table for field '{fk_field_name}' in table '{table_name}'."
                    ),
                )
            record_fields[fk_field_name] = actual_fk_id

    # 3. Call the specific create function for this record
    create_function = mapping["create_func"]
    record_fields["person_id"] = person_id
    new_record = await create_function(session, record_fields)

    # 4. Store the mapping for the new primary key
    if pk_ref:
        new_pk_value = new_record[pk_field]
        ref_id_table[pk_ref] = new_pk_value

    return new_record


# ==============================================================================
# Ingest Helper Functions
# ==============================================================================


async def ingest_dataset(ds_id: str, ds_info: dict) -> Tuple[bool, Optional[str]]:
    """
    Ingest a dataset record
    """
    dataset_fields = {"id": ds_id, "info": ds_info}

    async for session in get_db_session():
        try:
            await create_dataset(session, dataset_fields)
            await session.commit()
            logger.info(f"Successfully created dataset: {ds_id}")
            return True, None

        except Exception as e:
            await session.rollback()
            err_str = str(e)

            if "409" in err_str or "already exists" in err_str.lower():
                logger.warning(f"Dataset '{ds_id}' already exists. Skipping.")
                return False, f"Skipped Dataset '{ds_id}': Already exists."

            logger.error(f"Failed to create dataset '{ds_id}': {e}")
            return False, f"Failed Dataset '{ds_id}': {e}"

    return False, "Failed to acquire database session."


async def check_person_exists(session, person_source_value: str) -> bool:
    """
    Checks database for existing person by source value.
    Returns True if exists, False otherwise.
    """
    if not person_source_value:
        return False

    check_q = text(
        f"SELECT 1 FROM {settings.CDM_SCHEMA}.person WHERE person_source_value = :psv LIMIT 1"
    )
    res = await session.execute(check_q, {"psv": person_source_value})
    return bool(res.scalar())


async def ingest_single_person(
    ds_id: str, person_data: Dict[str, Any], queue_id: str
) -> Tuple[bool, str, Optional[str]]:
    """
    Ingests a single person and their linked clinical records.
    """
    person_fields = person_data.get("person", {})
    clinical_records = person_data.get("linked_records", [])
    person_source_val = person_fields.get("person_source_value", "Unknown_ID")

    async for session in get_db_session():
        try:
            # 1. Duplicate Check
            is_duplicate = await check_person_exists(session, person_source_val)

            if is_duplicate:
                logger.warning(
                    f"Skipping Duplicate Person '{person_source_val}' in job {queue_id}."
                )
                return (
                    False,
                    person_source_val,
                    f"Skipped Person '{person_source_val}': Already exists.",
                )

            # 2. Create Person
            created_person = await create_person(session, person_fields)
            person_id = created_person["person_id"]

            # 3. Create Clinical Records
            ref_id_table = {}
            for linked_record in clinical_records:
                ((table_name, table_fields),) = linked_record.items()
                await create_record(
                    session, ref_id_table, table_fields, table_name, person_id
                )

            # 4. Link Person to Dataset
            await create_person_in_dataset(
                session, {"dataset_id": ds_id, "person_id": person_id}
            )

            # 5. Commit
            await session.commit()
            logger.info(f"Successfully ingested person: {person_id}")
            return True, person_source_val, None

        except ProblemException as pe:
            await session.rollback()
            return False, person_source_val, f"Error Person '{person_source_val}': {pe.title} - {pe.detail}"

        except Exception as e:
            await session.rollback()
            err_str = str(e)
            
            # Log the full detailed error for debug
            logger.error(f"Ingest Error for person '{person_source_val}': {err_str}")

            # Check for Duplicate/Conflict (409)
            if "409" in err_str or "already exists" in err_str.lower():
                return False, person_source_val, f"Skipped Person '{person_source_val}': Already exists."

            # Shorten error message
            if "[SQL:" in err_str:
                err_str = err_str.split("[SQL:")[0]
            if "Error'>:" in err_str:
                err_str = err_str.split("Error'>:")[-1]
            
            return False, person_source_val, f"Error Person '{person_source_val}': {err_str.strip()}"

    return False, person_source_val, "Failed to acquire database session."


async def ingest_persons(
    ds_id: str, linked_records: List[dict], queue_id: str
) -> Tuple[List[str], List[str], int]:
    """
    Iterates through a list of persons and ingests them.
    """
    ingested = []
    errors = []
    fails = 0

    for person_data in linked_records:
        success, pid, err_msg = await ingest_single_person(ds_id, person_data, queue_id)

        if success:
            ingested.append(pid)
        else:
            fails += 1
            if err_msg:
                errors.append(err_msg)

    return ingested, errors, fails


async def ingest_data(data: dict, queue_id: str) -> Tuple[List[str], List[str], int]:
    """
    Parses the JSON structure and ingests datasets and persons.
    """
    all_ingested = []
    all_errors = []
    total_fails = 0

    dataset_list = data.get("datasets", [])

    for ds_data in dataset_list:
        ds_id = ds_data.get("id")
        ds_info = ds_data.get("info", {})
        ds_persons = ds_data.get("linked_records", [])

        if not ds_id:
            all_errors.append("Found dataset without ID. Skipping.")
            total_fails += 1
            continue

        # 1. Ingest Dataset
        ds_success, ds_err = await ingest_dataset(ds_id, ds_info)

        if not ds_success:
            total_fails += 1
            if ds_err:
                all_errors.append(ds_err)
            continue

        # 2. Ingest Persons within this Dataset
        p_ingested, p_errors, p_fails = await ingest_persons(
            ds_id, ds_persons, queue_id
        )

        all_ingested.extend(p_ingested)
        all_errors.extend(p_errors)
        total_fails += p_fails

    return all_ingested, all_errors, total_fails


def calculate_status(success_count: int, fail_count: int) -> str:
    if success_count > 0 and fail_count > 0:
        return "Partial Success"
    elif fail_count > 0 and success_count == 0:
        return "Failed"
    return "Success"


def write_results(results_path: str, result_data: dict, source_file_path: str):
    """Writes the result to file and removes the source file."""
    try:
        with open(results_path, "w") as f:
            json.dump(result_data, f, indent=4)
    except IOError as e:
        logger.error(f"Could not write results: {e}")

    try:
        if os.path.exists(source_file_path):
            os.remove(source_file_path)
    except OSError as e:
        logger.error(f"Could not remove source file: {e}")