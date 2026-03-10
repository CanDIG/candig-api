"""
Helper functions for clinical data ingestion
"""

import json
import os
import re
import requests
from typing import Any, Dict, List, Optional, Tuple

from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from jsonschema import Draft202012Validator
from urllib.parse import urlparse
from clinical_etl.schema import openapi_to_jsonschema

from src.config import settings
from src.database.db_operations import get_db_session
from src.database.insert_operations import (
    create_condition_occurrence,
    create_dataset,
    create_death,
    create_drug_exposure,
    create_episode,
    create_episode_event,
    create_fact_relationship,
    create_measurement,
    create_observation,
    create_person,
    create_person_in_dataset,
    create_procedure_occurrence,
    create_sample,
    create_specimen,
    create_visit_occurrence,
)

from authx.auth import create_service_token, get_s3_url
from src.api.auth import get_dataset, is_action_allowed
from src.api.dataset_operations import list_samples


logger = CanDIGLogger(__file__)


CANDIG_URL = os.getenv("CANDIG_URL", "")
HTSGET_URL = os.getenv("HTSGET_URL", f"{CANDIG_URL}/genomics")
DRS_URL = os.getenv("DRS_URL", f"{CANDIG_URL}/drs")
TAKUAN_URL = os.getenv("RNAGET_URL", f"{CANDIG_URL}/rnaget")
DRS_HOST_URL = "drs://" + CANDIG_URL.replace(f"{urlparse(CANDIG_URL).scheme}://","") + "/drs"
KATSU_URL = os.environ.get("KATSU_URL")
IS_TESTING = os.getenv("IS_TESTING", False)


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
            return (
                False,
                person_source_val,
                f"Error Person '{person_source_val}': {pe.title} - {pe.detail}",
            )

        except Exception as e:
            await session.rollback()
            err_str = str(e)

            # Log the full detailed error for debug
            logger.error(f"Ingest Error for person '{person_source_val}': {err_str}")

            # Check for Duplicate/Conflict (409)
            if "409" in err_str or "already exists" in err_str.lower():
                return (
                    False,
                    person_source_val,
                    f"Skipped Person '{person_source_val}': Already exists.",
                )

            # Shorten error message
            if "[SQL:" in err_str:
                err_str = err_str.split("[SQL:")[0]
            if "Error'>:" in err_str:
                err_str = err_str.split("Error'>:")[-1]

            return (
                False,
                person_source_val,
                f"Error Person '{person_source_val}': {err_str.strip()}",
            )

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


async def ingest_samples(
    data: dict, queue_id: str, site_id: str
) -> Tuple[List[str], List[str], int]:
    """
    Extracts sample data from json
    """
    all_ingested = []
    all_errors = []
    total_fails = 0

    logger.info(f"[{queue_id}] Starting samples data ingestion")

    donors = data.get("donors", [])

    for donor in donors:
        donor_id = donor.get("submitter_donor_id")
        raw_program_id = donor.get("program_id", "")
        dataset_id = f"{site_id}~{raw_program_id}"
        person_source_value = f"{site_id}~{raw_program_id}~{donor_id}"
        primary_diagnoses = donor.get("primary_diagnoses", [])

        for diagnosis in primary_diagnoses:
            specimens = diagnosis.get("specimens", [])

            for specimen in specimens:
                specimen_source_id = specimen.get("submitter_specimen_id")
                sample_registrations = specimen.get("sample_registrations", [])
                for sample in sample_registrations:
                    submitter_sample_id = sample.get("submitter_sample_id")
                    sample_id = f"{site_id}~{raw_program_id}~{submitter_sample_id}"

                    async for session in get_db_session():
                        try:
                            # 1. Look up person_id by person_source_value
                            person_q = text(
                                f"SELECT person_id FROM {settings.CDM_SCHEMA}.person "
                                f"WHERE person_source_value = :psv LIMIT 1"
                            )
                            person_res = await session.execute(
                                person_q, {"psv": person_source_value}
                            )
                            person_row = person_res.fetchone()

                            if not person_row:
                                raise ProblemException(
                                    status=422,
                                    title="Person Not Found",
                                    detail=f"No person found with person_source_value='{person_source_value}'.",
                                )
                            person_id = person_row[0]

                            # 2. Look up specimen_id by specimen_source_id
                            specimen_q = text(
                                f"SELECT specimen_id FROM {settings.CDM_SCHEMA}.specimen "
                                f"WHERE specimen_source_id = :ssid AND person_id = :pid LIMIT 1"
                            )
                            specimen_res = await session.execute(
                                specimen_q,
                                {"ssid": specimen_source_id, "pid": person_id},
                            )
                            specimen_row = specimen_res.fetchone()

                            if not specimen_row:
                                raise ProblemException(
                                    status=422,
                                    title="Specimen Not Found",
                                    detail=f"No specimen found with specimen_source_id='{specimen_source_id}' for donor '{person_source_value}'.",
                                )
                            specimen_id = specimen_row[0]

                            # 3. Build and insert sample record
                            sample_record = {
                                "sample_id": sample_id,
                                "sample_info": {
                                    **sample,
                                    "submitter_donor_id": donor_id,
                                    "submitter_specimen_id": specimen_source_id,
                                },
                                "dataset_id": dataset_id,
                                "person_id": person_id,
                                "specimen_id": specimen_id,
                            }

                            await create_sample(session, sample_record)
                            await session.commit()

                            logger.info(
                                f"[{queue_id}] Successfully ingested sample: {sample_id}"
                            )
                            all_ingested.append(sample_id)

                        except ProblemException as pe:
                            await session.rollback()
                            err_msg = (
                                f"Error Sample '{sample_id}': {pe.title} - {pe.detail}"
                            )
                            logger.error(f"[{queue_id}] {err_msg}")
                            all_errors.append(err_msg)
                            total_fails += 1

                        except Exception as e:
                            await session.rollback()
                            err_str = str(e)
                            logger.error(
                                f"[{queue_id}] Ingest error for sample '{sample_id}': {err_str}"
                            )

                            if "409" in err_str or "already exists" in err_str.lower():
                                all_errors.append(
                                    f"Skipped Sample '{sample_id}': Already exists."
                                )
                            else:
                                if "[SQL:" in err_str:
                                    err_str = err_str.split("[SQL:")[0]
                                if "Error'>:" in err_str:
                                    err_str = err_str.split("Error'>:")[-1]
                                all_errors.append(
                                    f"Error Sample '{sample_id}': {err_str.strip()}"
                                )

                            total_fails += 1

    logger.info(
        f"[{queue_id}] Samples ingestion completed: {len(all_ingested)} ingested, {total_fails} failed"
    )

    return all_ingested, all_errors, total_fails


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


async def check_genomic_data(jsoncontent, site_id, token):
    with open("ingest-schema.yml") as f:
        openapi_text = f.read()
        experiment_schema = openapi_to_jsonschema(openapi_text, "Experiment")
        analysis_schema = openapi_to_jsonschema(openapi_text, "Analysis")
        run_schema = openapi_to_jsonschema(openapi_text, "Run")
    result = {
        "errors": {},
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # sort by dataset
    by_dataset = {}

    for type in jsoncontent.keys():
        for item in jsoncontent[type]:
            if item["dataset_id"] not in by_dataset:
                by_dataset[item["dataset_id"]] = {"experiments": [], "runs": [], "analyses": []}
            by_dataset[item["dataset_id"]][type].append(item)

    for dataset_id in by_dataset.keys():
        if dataset_id not in result["errors"]:
            result["errors"][dataset_id] = []
        response, status_code = get_dataset(dataset_id)
        if status_code > 300:
            result["errors"][dataset_id].append({"not found": "No dataset authorization exists"})
        elif not is_action_allowed(dataset_id):
            result["errors"][dataset_id].append({"unauthorized": "user is not allowed to ingest to dataset"})
            continue

        # get all sample_registrations for this dataset
        samples_in_dataset, status_code = await list_samples(dataset_id)
        samples_in_dataset = list(map(lambda x: x["sample_id"], samples_in_dataset))
        if "experiments" in by_dataset[dataset_id]:
            for experiment in by_dataset[dataset_id]["experiments"]:
                sample_errors = []
                # validate the json
                for error in Draft202012Validator(experiment_schema).iter_errors(experiment):
                    sample_errors.extend(f"{' > '.join(error.path)}: {error.message}")
                if len(sample_errors) > 0:
                    continue
                # check to see if the samples exist in katsu
                if experiment["submitter_sample_id"] not in samples_in_dataset:
                    sample_errors.append({"no such sample": f"sample {experiment['submitter_sample_id']} does not exist in clinical data {samples_in_dataset}"})
                if len(sample_errors) > 0:
                    result["errors"][dataset_id].append({experiment["experiment_id"]: sample_errors})
        if "analyses" in by_dataset[dataset_id]:
            for analysis in by_dataset[dataset_id]["analyses"]:
                sample_errors = []
                # validate the json
                if analysis["analysis_id"] == analysis["main"]["name"]:
                    sample_errors = f"Experiment {analysis['analysis_id']} cannot have the same name as one of its files."
                if "index" in analysis and analysis["analysis_id"] == analysis["index"]["name"]:
                    sample_errors = f"Experiment {analysis['analysis_id']} cannot have the same name as one of its files."
                else:
                    for error in Draft202012Validator(analysis_schema).iter_errors(analysis):
                        sample_errors.extend(f"{' > '.join(error.path)}: {error.message}")
                if len(sample_errors) > 0:
                    result["errors"][dataset_id].append({analysis["analysis_id"]: sample_errors})
        if "runs" in by_dataset[dataset_id]:
            for run in by_dataset[dataset_id]["runs"]:
                sample_errors = []
                for file in run["files"]:
                    if run["run_id"] == file["name"]:
                        sample_errors = f"Experiment {run["run_id"]} cannot have the same name as one of its files."
                # validate the json
                for error in Draft202012Validator(run_schema).iter_errors(run):
                    sample_errors.extend(f"{' > '.join(error.path)}: {error.message}")
                if len(sample_errors) > 0:
                    result["errors"][dataset_id].append({run["run_id"]: sample_errors})
        if len(result["errors"][dataset_id]) == 0:
            result["errors"].pop(dataset_id)
    if len(result["errors"]) == 0:
        return by_dataset, 200
    return result, 400


def delete_program(program_id, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{DRS_URL}/ga4gh/drs/v1/programs/{program_id}"

    return requests.delete(url, headers=headers)
