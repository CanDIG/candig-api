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


async def ingest_genomic(ingest_json, queue_id):
    error_logs = []
    fail_count = 0
    result = {
        "runs": [], "experiments": [], "analyses": []
    }
    url = f"{DRS_URL}/ga4gh/drs/v1/objects"
    # Use service token to authenticate this with htsget
    headers = {
        "X-Service-Token": create_service_token(),
        "Content-Type": "application/json"
    }

    dataset_ids = set()
    to_index = []
    status_code = 200
    for dataset_id in ingest_json:
        for experiment in ingest_json[dataset_id]["experiments"]:
            logger.debug(f"[{queue_id}] Ingesting {experiment['experiment_id']}")
            experiment_drs_obj = {
                "id": experiment["experiment_id"],
                "name": experiment["submitter_sample_id"],
                "description": experiment["metadata"]["library_strategy"].lower(),
                "program": experiment["dataset_id"],
                "version": "v1",
                "metadata": experiment["metadata"],
                "contents": []
            }
            response = requests.post(f"{url}", json=experiment_drs_obj, headers=headers)
            if response.status_code != 200:
                error_logs.append(f"error creating experiment drs object {experiment_drs_obj['id']}: {response.status_code} {response.text}")
                fail_count += 1
            else:
                result["experiments"].append(experiment["experiment_id"])

        if "runs" in ingest_json[dataset_id]:
            for run in ingest_json[dataset_id]["runs"]:
                logger.debug(f"[{queue_id}] Ingesting {run['run_id']}")
                response = create_run(run)
                if "errors" in response and len(response["errors"]) > 0:
                    for err in response["errors"]:
                        if "403" in err:
                            status_code = 403
                            break
                        error_logs.append(f"error processing {response["id"]} {response["name"]} in experiment {run["experiment_id"]}: {err}")
                    fail_count += 1
                else:
                    result["runs"].append(run["run_id"])

        for analysis in ingest_json[dataset_id]["analyses"]:
            logger.debug(f"[{queue_id}] Ingesting {analysis['analysis_id']}")
            dataset_ids.add(analysis["dataset_id"])

            # create the corresponding DRS objects
            if "samples" not in analysis or len(analysis["samples"]) == 0:
                error_logs.append(f"error processing analysis {analysis["analysis_id"]}: No samples were specified")
                break
            response = create_analysis(analysis)
            if "errors" in response and len(response["errors"]) > 0:
                for err in response["errors"]:
                    if "403" in err:
                        status_code = 403
                        break
                    error_logs.append(f"error processing {response["id"]} {response["name"]} in experiment {analysis["analysis_id"]}: {err}")
                fail_count += 1
            else:
                result["analyses"].append(analysis["analysis_id"])

            if "to_index" in response:
                to_index.extend(response.pop("to_index"))

    # send off index calls
    for url in to_index:
        logger.debug(f"[{queue_id}] Indexing {url}")
        response = requests.get(url, headers=headers)

    # update completeness stats for dataset_ids with created biosamples
    statistics = {}
    for dataset_id in dataset_ids:
        logger.debug(f"[{queue_id}] Compiling statistics for {dataset_id}")
        url = f"{HTSGET_URL}/htsget/v1/biosamples"
        response = requests.get(url, headers=headers, params={"program": dataset_id})
        if response.status_code == 200:
            for biosample in response.json():
                if dataset_id not in statistics:
                    statistics[dataset_id] = { 'genomes': 0, 'transcriptomes': 0, 'all': 0 }
                if len(biosample["experiments"]["wgs"]) > 0 and len(biosample["experiments"]["wts"]) > 0:
                    statistics[dataset_id]['all'] += 1
                if len(biosample["experiments"]["wgs"]) > 0:
                    statistics[dataset_id]['genomes'] += 1
                if len(biosample["experiments"]["wts"]) > 0:
                    statistics[dataset_id]['transcriptomes'] += 1
        else:
            error_logs.append(f"Could not collect completeness stats for program: {response.text}")

    for dataset_id in statistics:
        # get the program
        url = f"{DRS_URL}/ga4gh/drs/v1/programs"
        response = requests.get(f"{url}/{dataset_id}", headers=headers)
        if response.status_code == 200:
            program = response.json()
            program["statistics"] = statistics[dataset_id]
            response = requests.post(url, headers=headers, json=program)
            if response.status_code != 200:
                error_logs.append(f"Could not add statistics for program: {response.text}")
        else:
            error_logs.append(f"Could not add statistics for program: {response.text}")

    return result, error_logs, fail_count


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


def create_analysis(analysis):
    url = f"{DRS_URL}/ga4gh/drs/v1/objects"
    result = {
        "errors": []
    }

    # Use service token to authenticate this with htsget
    headers = {
        "X-Service-Token": create_service_token(),
        "Content-Type": "application/json"
    }

    analysis_type = analysis["metadata"]["analysis_type"]

    # get the master analysis object, or create it:
    analysis_drs_obj = {}
    response = requests.get(f"{url}/{analysis['analysis_id']}", headers=headers)
    if response.status_code == 200:
        analysis_drs_obj = response.json()
    analysis_drs_obj["id"] = analysis["analysis_id"]
    analysis_drs_obj["name"] = analysis["analysis_id"]
    analysis_drs_obj["description"] = analysis_type
    analysis_drs_obj["program"] = analysis["dataset_id"]
    analysis_drs_obj["reference_genome"] = analysis["metadata"]["reference"]
    analysis_drs_obj["version"] = "v1"
    analysis_drs_obj["metadata"] = analysis["metadata"]
    if "contents" not in analysis_drs_obj:
        analysis_drs_obj["contents"] = []

    # add AnalysisDataDrsObject to contents
    response = add_file_drs_object(analysis_drs_obj, analysis["main"], "analysis", headers)
    result["name"] = response["name"]
    result["id"] = response["id"]
    if "error" in response:
        result["errors"].append(response["error"])
        return result

    if "index" in analysis:
        # add AnalysisIndexDrsObject to contents
        response = add_file_drs_object(analysis_drs_obj, analysis["index"], "index", headers)
        if "error" in response:
            result["errors"].append(response["error"])
            return result

    for clin_sample in analysis["samples"]:
        # for each analysis in the samples, get the ExperimentDrsObject
        response = requests.get(f"{url}/{clin_sample['experiment_id']}", headers=headers)
        if response.status_code == 200:
            experiment_drs_obj = response.json()
        else:
            result["errors"].append(f"couldn't find experiment drs object {clin_sample['experiment_id']}: {response.status_code} {response.text}")
            return result

        # add the AnalysisDrsObject to its contents, if it's not already there:
        not_found = True
        if len(experiment_drs_obj["contents"]) > 0:
            for obj in experiment_drs_obj["contents"]:
                if obj["name"] == analysis["analysis_id"]:
                    not_found = False
        if not_found:
            contents_obj = {
                "name": analysis["analysis_id"],
                "id": analysis["analysis_id"],
                "drs_uri": [f"{DRS_HOST_URL}/{analysis['analysis_id']}"]
            }
            experiment_drs_obj["contents"].append(contents_obj)

        # update the experiment_drs_object in the database:
        response = requests.post(f"{url}", json=experiment_drs_obj, headers=headers)
        if response.status_code != 200:
            result["errors"].append(f"error updating experiment drs object {experiment_drs_obj['id']}: {response.status_code} {response.text}")
            return result

        # then add the experiment to the AnalysisDrsObject's contents, if it's not already there:
        contents_obj = {
            "name": experiment_drs_obj["name"],
            "id": clin_sample["analysis_sample_id"],
            "drs_uri": [f"{DRS_HOST_URL}/{clin_sample['experiment_id']}"]
        }
        not_found = True
        if len(analysis_drs_obj["contents"]) > 0:
            for i in range(0, len(analysis_drs_obj["contents"])):
                if analysis_drs_obj["contents"][i]["name"] == clin_sample["experiment_id"]:
                    not_found = False
                    analysis_drs_obj["contents"][i] = contents_obj
                    break
        if not_found:
            analysis_drs_obj["contents"].append(contents_obj)

    # finally, post the analysis_drs_object
    response = requests.post(url, json=analysis_drs_obj, headers=headers)
    if response.status_code != 200:
        result["errors"].append(f"error posting analysis drs object {analysis_drs_obj['id']}: {response.status_code} {response.text}")
        return result
    else:
        result["sample"] = f"connected submitter_sample_id {contents_obj["name"]} to analysis_sample_id {contents_obj["id"]}"

    # send the data to the downstream service: either htsget or takuan
    if analysis_drs_obj["metadata"]["analysis_type"] == "sequence_annotation":
        if "analysis_attribute" in analysis_drs_obj["metadata"] and analysis_drs_obj["metadata"]["analysis_attribute"]["subtype"] == "expression_count":
            assembly_id = "GCA_000001405.27"
            if "reference_assembly_id" in analysis_drs_obj["metadata"]:
                assembly_id = analysis_drs_obj["metadata"]["reference_assembly_id"]
            # first, create experiment in Takuan:
            experiment_json = {
                "experiment_result_id": experiment_drs_obj["id"],
                "assembly_id": assembly_id,
                "assembly_name": analysis_drs_obj["metadata"]["reference"],
                "extra_properties": {}
            }
            response = requests.post(f"{TAKUAN_URL}/experiment", json=experiment_json, headers=headers)
            logger.debug(f"[{queue_id}] takuan experiment post {response.status_code}, {response.text}")

            # ingest matrix
            response = requests.get(f"{DRS_URL}/ga4gh/drs/v1/objects/{analysis["main"]["name"]}/download", headers=headers)
            if response.status_code == 200:
                raw_tsv_data = response.text.strip()
                lines = raw_tsv_data.split("\n")
                titles = lines.pop(0).split("\t")

                # verify that all required columns are present:
                if "gene_id_column" not in analysis_drs_obj["metadata"]["analysis_attribute"]:
                    result["errors"].append(f"no gene_id column present")
                    return result
                if "length_column" not in analysis_drs_obj["metadata"]["analysis_attribute"]:
                    result["errors"].append(f"no length column present")
                    return result
                if "count_column" not in analysis_drs_obj["metadata"]["analysis_attribute"]:
                    result["errors"].append(f"no count column present")
                    return result

                norm_method = None
                if "norm_column" in analysis_drs_obj["metadata"]["analysis_attribute"]:
                    if "norm_method" not in analysis_drs_obj["metadata"]["analysis_attribute"]:
                        result["errors"].append(f"norm_column present but no norm_method specified")
                        return result
                    norm_method = analysis_drs_obj["metadata"]["analysis_attribute"]["norm_method"]
                    norm_title = analysis_drs_obj["metadata"]["analysis_attribute"]["norm_column"]

                gene_id_title = analysis_drs_obj["metadata"]["analysis_attribute"]["gene_id_column"]
                count_title = analysis_drs_obj["metadata"]["analysis_attribute"]["count_column"]
                length_title = analysis_drs_obj["metadata"]["analysis_attribute"]["length_column"]
                if gene_id_title not in titles:
                    result["errors"].append(f"column {gene_id_title} not present in ingest file")
                    return result
                if count_title not in titles:
                    result["errors"].append(f"column {count_title} not present in ingest file")
                    return result
                if length_title not in titles:
                    result["errors"].append(f"column {length_title} not present in ingest file")
                    return result

                mapping = {
                    "sample_id": experiment_drs_obj["id"],
                    "file_type": "tsv",
                    "feature_col": gene_id_title,
                    "raw_count_col": count_title,
                    "length_col": length_title
                }
                if norm_method is not None:
                    if norm_title not in titles:
                        result["errors"].append(f"column {norm_title} not present in ingest file")
                        return result
                    mapping[f"{norm_method.lower()}_count_col"] = norm_title

                if "TPM" in titles:
                    mapping["tpm_count_col"] = "TPM"
                if "tpm" in titles:
                    mapping["tpm_count_col"] = "tpm"
                if "FPKM" in titles:
                    mapping["fpkm_count_col"] = "FPKM"
                if "fpkm" in titles:
                    mapping["fpkm_count_col"] = "fpkm"
                if "GETMM" in titles:
                    mapping["getmm_count_col"] = "GETMM"
                if "getmm" in titles:
                    mapping["getmm_count_col"] = "getmm"

                response = requests.post(
                    f"{TAKUAN_URL}/experiment/{experiment_drs_obj["id"]}/ingest/single",
                    files={"data": raw_tsv_data}, data=mapping
                )
                if response.status_code != 200:
                    result["errors"].append(f"takuan ingest error: {response.status_code} {response.text}")
            else:
                result["errors"].append(f"could not load analysis: {response.text}")
    else:
        # send it to htsget
        # verify that the genomic file exists and is readable
        verify_url = f"{HTSGET_URL}/htsget/v1/{analysis_drs_obj['id']}/verify"

        response = requests.get(verify_url, headers=headers)
        if response.status_code != 200:
            result["errors"].append(f"could not verify analysis: {response.text}")
            return result
        elif not response.json()['result']:
            # was an analysis_date specified? if so, it's not an error if the verification fails because it doesn't have one
            if 'does not have any associated analysis date' in response.json()['message']:
                if 'analysis_date' not in analysis_drs_obj['metadata']:
                    result["errors"].append(f"could not verify analysis: {response.text}")
                    return result
            else:
                result["errors"].append(f"could not verify analysis: {response.json()['message']}")
                return result
        # flag the analysis_drs_object for indexing:
        url =f"{HTSGET_URL}/htsget/v1/{analysis_drs_obj['id']}/index"
        result["to_index"] = [url]
    if len(result["errors"]) == 0:
        result.pop("errors")
    return result


def create_run(run):
    url = f"{DRS_URL}/ga4gh/drs/v1/objects"
    result = {
        "errors": []
    }

    # Use service token to authenticate this with htsget
    headers = {
        "X-Service-Token": create_service_token(),
        "Content-Type": "application/json"
    }

    run_drs_obj = {}
    response = requests.get(f"{url}/{run['run_id']}", headers=headers)
    if response.status_code == 200:
        run_drs_obj = response.json()
    run_drs_obj["id"] = run["run_id"]
    run_drs_obj["name"] = run["experiment_id"]
    run_drs_obj["description"] = "raw_reads"
    run_drs_obj["program"] = run["dataset_id"]
    run_drs_obj["version"] = "v1"
    run_drs_obj["metadata"] = run["metadata"]
    if "contents" not in run_drs_obj:
        run_drs_obj["contents"] = []

    # add files to contents
    for file in run["files"]:
        response = add_file_drs_object(run_drs_obj, file, run["metadata"]["filetype"], headers)
        if "error" in response:
            result["errors"].append(response["error"])
            return result

    response = requests.get(f"{url}/{run['experiment_id']}", headers=headers)
    if response.status_code == 200:
        experiment_drs_obj = response.json()
    else:
        result["errors"].append(f"couldn't find experiment drs object {run['experiment_id']}: {response.status_code} {response.text}")
        return result

    # add the RunDrsObject to its contents, if it's not already there:
    not_found = True
    if len(experiment_drs_obj["contents"]) > 0:
        for obj in experiment_drs_obj["contents"]:
            if obj["name"] == run["run_id"]:
                not_found = False
    if not_found:
        contents_obj = {
            "name": run["run_id"],
            "id": run["run_id"],
            "drs_uri": [f"{DRS_HOST_URL}/{run['run_id']}"]
        }
        experiment_drs_obj["contents"].append(contents_obj)

    # update the experiment_drs_object in the database:
    response = requests.post(f"{url}", json=experiment_drs_obj, headers=headers)
    if response.status_code != 200:
        result["errors"].append(f"error updating experiment drs object {experiment_drs_obj['id']}: {response.status_code} {response.text}")
        return result

    # then add the experiment to the RunDrsObject's contents, if it's not already there:
    contents_obj = {
        "name": experiment_drs_obj["name"],
        "id": run["experiment_id"],
        "drs_uri": [f"{DRS_HOST_URL}/{run['experiment_id']}"]
    }
    not_found = True
    if len(run_drs_obj["contents"]) > 0:
        for i in range(0, len(run_drs_obj["contents"])):
            if run_drs_obj["contents"][i]["name"] == run["experiment_id"]:
                not_found = False
                run_drs_obj["contents"][i] = contents_obj
                break
    if not_found:
        run_drs_obj["contents"].append(contents_obj)

    # finally, post the run_drs_object
    response = requests.post(url, json=run_drs_obj, headers=headers)
    if response.status_code != 200:
        result["errors"].append(f"error posting run drs object {run_drs_obj['id']}: {response.status_code} {response.text}")
        return result

    verify_url = f"{HTSGET_URL}/htsget/v1/{run_drs_obj['id']}/verify"

    response = requests.get(verify_url, headers=headers)
    if response.status_code != 200:
        result["errors"].append(f"could not verify run: {response.text}")
        return result

    if len(result["errors"]) == 0:
        result.pop("errors")
    return result


def add_file_drs_object(drs_obj, file, type, headers):
    url = f"{DRS_URL}/ga4gh/drs/v1/objects"
    obj = {
        "access_methods": [],
        "id": file['name'],
        "name": file['name'],
        "description": type,
        "program": drs_obj["program"],
        "version": "v1"
    }
    contents_obj = {
        "name": file["name"],
        "id": type,
        "drs_uri": [f"{DRS_HOST_URL}/{file['name']}"]
    }
    access_method = get_access_method(file["access_method"])
    if access_method is not None:
        if "message" in access_method:
            contents_obj["error"] = access_method["message"]
            return contents_obj
        obj["access_methods"].append(access_method)

    # is this file already in the master object? If so, replace it:
    not_found = True
    if len(drs_obj["contents"]) > 0:
        for i in range(0, len(drs_obj["contents"])):
            if drs_obj["contents"][i]["name"] == file["name"]:
                drs_obj["contents"][i] = contents_obj
                not_found = False
                break
    if not_found:
        drs_obj["contents"].append(contents_obj)
    response = requests.post(url, json=obj, headers=headers)
    if response.status_code > 200:
        contents_obj["error"] =  f"error creating file drs object: {response.status_code} {response.text}"
    return contents_obj


def get_access_method(url):
    if url.startswith("file"):
        return {
            "type": "file",
            "access_url": {
                "url": url
            }
        }
    try:
        result = parse_s3_url(url)
    except Exception as e:
        return {
            "message": str(e)
        }
    return {
        "type": "s3",
        "access_id": url
    }


def parse_s3_url(url):
    """
    Parse a url into s3 components
    """
    s3_url_parse = re.match(r"((https*|s3):\/\/(.+?))\/(.+)", url)
    if s3_url_parse is not None:
        if s3_url_parse.group(2) == "s3":
            raise Exception(f"Incorrect URL format {url}. S3 URLs should be in the form http(s)://endpoint-url/bucket-name/object. If your object is stored at AWS S3, you can find more information about endpoint URLs at https://docs.aws.amazon.com/general/latest/gr/rande.html")
        endpoint = s3_url_parse.group(1)
        bucket_parse = re.match(r"(.+?)\/(.+)", s3_url_parse.group(4))
        if bucket_parse is not None:
            data = {
                "endpoint": endpoint,
                "bucket": bucket_parse.group(1),
                "object": bucket_parse.group(2)
            }
            # check existence of credential for this:
            object = data["object"].split("?public=")
            data["object"] = object[0]
            if len(object) > 1:
                data["object"] = object[0]
                response, status_code = get_s3_url(s3_endpoint=data["endpoint"], bucket=data["bucket"], object_id=data["object"], access_key=None, secret_key=None, region=None, public=True)
            else:
                response, status_code = get_s3_url(s3_endpoint=data["endpoint"], bucket=data["bucket"], object_id=data["object"], access_key=None, secret_key=None, region=None, public=False)

            if status_code == 500:
                    raise Exception(response["error"])
            return data
        raise Exception(f"S3 URI {url} does not contain a bucket name")
    raise Exception(f"URI {url} cannot be parsed as an S3-style URI")


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


def delete_program(dataset_id, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{DRS_URL}/ga4gh/drs/v1/programs/{dataset_id}"

    return requests.delete(url, headers=headers)
