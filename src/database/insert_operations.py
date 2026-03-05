"""
Database insert operations for OMOP tables.
"""

from decimal import Decimal
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ..config import settings

logger = CanDIGLogger(__file__)


# ==============================================================================
# Helper Functions
# ==============================================================================


def safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_decimal(value: Any) -> Optional[Decimal]:
    """
    Converts a value to Decimal
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return None


def row_to_dict(row: Optional[Row]) -> Dict[str, Any]:
    if row is None:
        raise ProblemException(
            status=500,
            title="Database Error",
            detail="No data returned from database insert operation.",
        )
    return {key: getattr(row, key) for key in row._fields}


def parse_dates(
    record_data: dict, date_fields: List[str], datetime_fields: List[str]
) -> None:
    """
    Conversion of date/datetime strings to objects.
    """
    # 1. Handle Datetimes (ISO 8601)
    for field in datetime_fields:
        val = record_data.get(field)
        if val and isinstance(val, str):
            try:
                record_data[field] = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format for '{field}': {val}. Expected format: '2023-12-09T14:30:00' or '2023-12-09T14:30:00Z'.",
                )

    # 2. Handle Dates (YYYY-MM-DD)
    for field in date_fields:
        val = record_data.get(field)
        if val and isinstance(val, str):
            try:
                record_data[field] = date.fromisoformat(val)
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid date format for '{field}': {val}. Expected format: 'YYYY-MM-DD' (e.g., '2023-12-09').",
                )


async def handle_insert(
    session: AsyncSession,
    schema: str,
    table_name: str,
    pk_field: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generates and executes an INSERT statement.
    """
    if not params:
        raise ProblemException(
            status=500, title="Internal Error", detail="Cannot insert empty record."
        )

    columns = list(params.keys())

    cols_str = ", ".join(columns)
    binds_str = ", ".join([f":{c}" for c in columns])

    returning_clause = pk_field if pk_field else "*"

    sql_text = f"""
        INSERT INTO {schema}.{table_name} ({cols_str}) 
        VALUES ({binds_str}) 
        RETURNING {returning_clause}
    """

    result = await session.execute(text(sql_text), params)
    row = result.fetchone()
    return row_to_dict(row)


# ==============================================================================
# Specific Table Implementations
# ==============================================================================


async def create_person(session: AsyncSession, record_data: dict) -> Dict[str, Any]:
    parse_dates(record_data, [], ["birth_datetime"])

    params = {
        "gender_concept_id": safe_int(record_data.get("gender_concept_id")),
        "year_of_birth": safe_int(record_data.get("year_of_birth")),
        "month_of_birth": safe_int(record_data.get("month_of_birth")),
        "day_of_birth": safe_int(record_data.get("day_of_birth")),
        "birth_datetime": record_data.get("birth_datetime"),
        "race_concept_id": safe_int(record_data.get("race_concept_id")),
        "ethnicity_concept_id": safe_int(record_data.get("ethnicity_concept_id")),
        "location_id": safe_int(record_data.get("location_id")),
        "provider_id": safe_int(record_data.get("provider_id")),
        "care_site_id": safe_int(record_data.get("care_site_id")),
        "person_source_value": record_data.get("person_source_value"),
        "gender_source_value": record_data.get("gender_source_value"),
        "gender_source_concept_id": safe_int(
            record_data.get("gender_source_concept_id")
        ),
        "race_source_value": record_data.get("race_source_value"),
        "race_source_concept_id": safe_int(record_data.get("race_source_concept_id")),
        "ethnicity_source_value": record_data.get("ethnicity_source_value"),
        "ethnicity_source_concept_id": safe_int(
            record_data.get("ethnicity_source_concept_id")
        ),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "person", "person_id", params
    )


async def create_observation(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    parse_dates(record_data, ["observation_date"], ["observation_datetime"])

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "observation_concept_id": safe_int(record_data.get("observation_concept_id")),
        "observation_date": record_data.get("observation_date"),
        "observation_datetime": record_data.get("observation_datetime"),
        "observation_type_concept_id": safe_int(
            record_data.get("observation_type_concept_id")
        ),
        "value_as_number": safe_decimal(record_data.get("value_as_number")),
        "value_as_string": record_data.get("value_as_string"),
        "value_as_concept_id": safe_int(record_data.get("value_as_concept_id")),
        "qualifier_concept_id": safe_int(record_data.get("qualifier_concept_id")),
        "unit_concept_id": safe_int(record_data.get("unit_concept_id")),
        "provider_id": safe_int(record_data.get("provider_id")),
        "visit_occurrence_id": safe_int(record_data.get("visit_occurrence_id")),
        "visit_detail_id": safe_int(record_data.get("visit_detail_id")),
        "observation_source_value": record_data.get("observation_source_value"),
        "observation_source_concept_id": safe_int(
            record_data.get("observation_source_concept_id")
        ),
        "unit_source_value": record_data.get("unit_source_value"),
        "qualifier_source_value": record_data.get("qualifier_source_value"),
        "value_source_value": record_data.get("value_source_value"),
        "observation_event_id": safe_int(record_data.get("observation_event_id")),
        "obs_event_field_concept_id": safe_int(
            record_data.get("obs_event_field_concept_id")
        ),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "observation", "observation_id", params
    )


async def create_condition_occurrence(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    parse_dates(
        record_data,
        ["condition_start_date", "condition_end_date"],
        ["condition_start_datetime", "condition_end_datetime"],
    )

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "condition_concept_id": safe_int(record_data.get("condition_concept_id")),
        "condition_start_date": record_data.get("condition_start_date"),
        "condition_start_datetime": record_data.get("condition_start_datetime"),
        "condition_end_date": record_data.get("condition_end_date"),
        "condition_end_datetime": record_data.get("condition_end_datetime"),
        "condition_type_concept_id": safe_int(
            record_data.get("condition_type_concept_id")
        ),
        "condition_status_concept_id": safe_int(
            record_data.get("condition_status_concept_id")
        ),
        "stop_reason": record_data.get("stop_reason"),
        "provider_id": safe_int(record_data.get("provider_id")),
        "visit_occurrence_id": safe_int(record_data.get("visit_occurrence_id")),
        "visit_detail_id": safe_int(record_data.get("visit_detail_id")),
        "condition_source_value": record_data.get("condition_source_value"),
        "condition_source_concept_id": safe_int(
            record_data.get("condition_source_concept_id")
        ),
        "condition_status_source_value": record_data.get(
            "condition_status_source_value"
        ),
    }

    return await handle_insert(
        session,
        settings.CDM_SCHEMA,
        "condition_occurrence",
        "condition_occurrence_id",
        params,
    )


async def create_episode(session: AsyncSession, record_data: dict) -> Dict[str, Any]:
    parse_dates(
        record_data,
        ["episode_start_date", "episode_end_date"],
        ["episode_start_datetime", "episode_end_datetime"],
    )

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "episode_concept_id": safe_int(record_data.get("episode_concept_id")),
        "episode_start_date": record_data.get("episode_start_date"),
        "episode_start_datetime": record_data.get("episode_start_datetime"),
        "episode_end_date": record_data.get("episode_end_date"),
        "episode_end_datetime": record_data.get("episode_end_datetime"),
        "episode_parent_id": safe_int(record_data.get("episode_parent_id")),
        "episode_number": safe_int(record_data.get("episode_number")),
        "episode_object_concept_id": safe_int(
            record_data.get("episode_object_concept_id")
        ),
        "episode_type_concept_id": safe_int(record_data.get("episode_type_concept_id")),
        "episode_source_value": record_data.get("episode_source_value"),
        "episode_source_concept_id": safe_int(
            record_data.get("episode_source_concept_id")
        ),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "episode", "episode_id", params
    )


async def create_episode_event(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    params = {
        "episode_id": safe_int(record_data.get("episode_id")),
        "event_id": safe_int(record_data.get("event_id")),
        "episode_event_field_concept_id": safe_int(
            record_data.get("episode_event_field_concept_id")
        ),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "episode_event", None, params
    )


async def create_measurement(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    parse_dates(record_data, ["measurement_date"], ["measurement_datetime"])

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "measurement_concept_id": safe_int(record_data.get("measurement_concept_id")),
        "measurement_date": record_data.get("measurement_date"),
        "measurement_datetime": record_data.get("measurement_datetime"),
        "measurement_time": record_data.get("measurement_time"),
        "measurement_type_concept_id": safe_int(
            record_data.get("measurement_type_concept_id")
        ),
        "operator_concept_id": safe_int(record_data.get("operator_concept_id")),
        "value_as_number": safe_decimal(record_data.get("value_as_number")),
        "value_as_concept_id": safe_int(record_data.get("value_as_concept_id")),
        "unit_concept_id": safe_int(record_data.get("unit_concept_id")),
        "range_low": safe_decimal(record_data.get("range_low")),
        "range_high": safe_decimal(record_data.get("range_high")),
        "provider_id": safe_int(record_data.get("provider_id")),
        "visit_occurrence_id": safe_int(record_data.get("visit_occurrence_id")),
        "visit_detail_id": safe_int(record_data.get("visit_detail_id")),
        "measurement_source_value": record_data.get("measurement_source_value"),
        "measurement_source_concept_id": safe_int(
            record_data.get("measurement_source_concept_id")
        ),
        "unit_source_value": record_data.get("unit_source_value"),
        "unit_source_concept_id": safe_int(record_data.get("unit_source_concept_id")),
        "value_source_value": record_data.get("value_source_value"),
        "measurement_event_id": safe_int(record_data.get("measurement_event_id")),
        "meas_event_field_concept_id": safe_int(
            record_data.get("meas_event_field_concept_id")
        ),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "measurement", "measurement_id", params
    )


async def create_specimen(session: AsyncSession, record_data: dict) -> Dict[str, Any]:
    parse_dates(record_data, ["specimen_date"], ["specimen_datetime"])

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "specimen_concept_id": safe_int(record_data.get("specimen_concept_id")),
        "specimen_type_concept_id": safe_int(
            record_data.get("specimen_type_concept_id")
        ),
        "specimen_date": record_data.get("specimen_date"),
        "specimen_datetime": record_data.get("specimen_datetime"),
        "quantity": safe_decimal(record_data.get("quantity")),
        "unit_concept_id": safe_int(record_data.get("unit_concept_id")),
        "anatomic_site_concept_id": safe_int(
            record_data.get("anatomic_site_concept_id")
        ),
        "disease_status_concept_id": safe_int(
            record_data.get("disease_status_concept_id")
        ),
        "specimen_source_id": record_data.get("specimen_source_id"),
        "specimen_source_value": record_data.get("specimen_source_value"),
        "unit_source_value": record_data.get("unit_source_value"),
        "anatomic_site_source_value": record_data.get("anatomic_site_source_value"),
        "disease_status_source_value": record_data.get("disease_status_source_value"),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "specimen", "specimen_id", params
    )


async def create_procedure_occurrence(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    parse_dates(
        record_data,
        ["procedure_date", "procedure_end_date"],
        ["procedure_datetime", "procedure_end_datetime"],
    )

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "procedure_concept_id": safe_int(record_data.get("procedure_concept_id")),
        "procedure_date": record_data.get("procedure_date"),
        "procedure_datetime": record_data.get("procedure_datetime"),
        "procedure_end_date": record_data.get("procedure_end_date"),
        "procedure_end_datetime": record_data.get("procedure_end_datetime"),
        "procedure_type_concept_id": safe_int(
            record_data.get("procedure_type_concept_id")
        ),
        "modifier_concept_id": safe_int(record_data.get("modifier_concept_id")),
        "quantity": safe_int(
            record_data.get("quantity")
        ),
        "provider_id": safe_int(record_data.get("provider_id")),
        "visit_occurrence_id": safe_int(record_data.get("visit_occurrence_id")),
        "visit_detail_id": safe_int(record_data.get("visit_detail_id")),
        "procedure_source_value": record_data.get("procedure_source_value"),
        "procedure_source_concept_id": safe_int(
            record_data.get("procedure_source_concept_id")
        ),
        "modifier_source_value": record_data.get("modifier_source_value"),
    }

    return await handle_insert(
        session,
        settings.CDM_SCHEMA,
        "procedure_occurrence",
        "procedure_occurrence_id",
        params,
    )


async def create_drug_exposure(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    parse_dates(
        record_data,
        ["drug_exposure_start_date", "drug_exposure_end_date", "verbatim_end_date"],
        ["drug_exposure_start_datetime", "drug_exposure_end_datetime"],
    )

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "drug_concept_id": safe_int(record_data.get("drug_concept_id")),
        "drug_exposure_start_date": record_data.get("drug_exposure_start_date"),
        "drug_exposure_start_datetime": record_data.get("drug_exposure_start_datetime"),
        "drug_exposure_end_date": record_data.get("drug_exposure_end_date"),
        "drug_exposure_end_datetime": record_data.get("drug_exposure_end_datetime"),
        "verbatim_end_date": record_data.get("verbatim_end_date"),
        "drug_type_concept_id": safe_int(record_data.get("drug_type_concept_id")),
        "stop_reason": record_data.get("stop_reason"),
        "refills": safe_int(record_data.get("refills")),
        "quantity": safe_decimal(record_data.get("quantity")),
        "days_supply": safe_int(record_data.get("days_supply")),
        "sig": record_data.get("sig"),
        "route_concept_id": safe_int(record_data.get("route_concept_id")),
        "lot_number": record_data.get("lot_number"),
        "provider_id": safe_int(record_data.get("provider_id")),
        "visit_occurrence_id": safe_int(record_data.get("visit_occurrence_id")),
        "visit_detail_id": safe_int(record_data.get("visit_detail_id")),
        "drug_source_value": record_data.get("drug_source_value"),
        "drug_source_concept_id": safe_int(record_data.get("drug_source_concept_id")),
        "route_source_value": record_data.get("route_source_value"),
        "dose_unit_source_value": record_data.get("dose_unit_source_value"),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "drug_exposure", "drug_exposure_id", params
    )


async def create_fact_relationship(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    params = {
        "domain_concept_id_1": safe_int(record_data.get("domain_concept_id_1")),
        "fact_id_1": safe_int(record_data.get("fact_id_1")),
        "domain_concept_id_2": safe_int(record_data.get("domain_concept_id_2")),
        "fact_id_2": safe_int(record_data.get("fact_id_2")),
        "relationship_concept_id": safe_int(record_data.get("relationship_concept_id")),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "fact_relationship", None, params
    )


async def create_death(session: AsyncSession, record_data: dict) -> Dict[str, Any]:
    parse_dates(record_data, ["death_date"], ["death_datetime"])

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "death_date": record_data.get("death_date"),
        "death_datetime": record_data.get("death_datetime"),
        "death_type_concept_id": safe_int(record_data.get("death_type_concept_id")),
        "cause_concept_id": safe_int(record_data.get("cause_concept_id")),
        "cause_source_value": record_data.get("cause_source_value"),
        "cause_source_concept_id": safe_int(record_data.get("cause_source_concept_id")),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "death", "person_id", params
    )


async def create_dataset(session: AsyncSession, record_data: dict) -> Dict[str, Any]:
    params = {
        "id": str(record_data.get("id")),
        "info": record_data.get("info") if record_data.get("info") else None,
    }

    return await handle_insert(session, settings.CANDIG_SCHEMA, "dataset", "id", params)


async def create_person_in_dataset(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    params = {
        "dataset_id": record_data.get("dataset_id"),
        "person_id": record_data.get("person_id"),
    }

    return await handle_insert(
        session, settings.CANDIG_SCHEMA, "person_in_dataset", None, params
    )


async def create_visit_occurrence(
    session: AsyncSession, record_data: dict
) -> Dict[str, Any]:
    parse_dates(
        record_data,
        ["visit_start_date", "visit_end_date"],
        ["visit_start_datetime", "visit_end_datetime"],
    )

    params = {
        "person_id": safe_int(record_data.get("person_id")),
        "visit_concept_id": safe_int(record_data.get("visit_concept_id")),
        "visit_start_date": record_data.get("visit_start_date"),
        "visit_start_datetime": record_data.get("visit_start_datetime"),
        "visit_end_date": record_data.get("visit_end_date"),
        "visit_end_datetime": record_data.get("visit_end_datetime"),
        "visit_type_concept_id": safe_int(record_data.get("visit_type_concept_id")),
        "provider_id": safe_int(record_data.get("provider_id")),
        "care_site_id": safe_int(record_data.get("care_site_id")),
        "visit_source_value": record_data.get("visit_source_value"),
        "visit_source_concept_id": safe_int(record_data.get("visit_source_concept_id")),
        "admitted_from_concept_id": safe_int(
            record_data.get("admitted_from_concept_id")
        ),
        "admitted_from_source_value": record_data.get("admitted_from_source_value"),
        "discharged_to_concept_id": safe_int(
            record_data.get("discharged_to_concept_id")
        ),
        "discharged_to_source_value": record_data.get("discharged_to_source_value"),
        "preceding_visit_occurrence_id": safe_int(
            record_data.get("preceding_visit_occurrence_id")
        ),
    }

    return await handle_insert(
        session, settings.CDM_SCHEMA, "visit_occurrence", "visit_occurrence_id", params
    )

async def create_sample(session: AsyncSession, record_data: dict) -> Dict[str, Any]:
    sample_info = record_data.get("sample_info")
    params = {
        "sample_id": str(record_data.get("sample_id")),
        "sample_info": json.dumps(sample_info) if sample_info is not None else None,
        "dataset_id": str(record_data.get("dataset_id")),
        "person_id": safe_int(record_data.get("person_id")),
        "specimen_id": safe_int(record_data.get("specimen_id")),
    }

    return await handle_insert(
        session, settings.CANDIG_SCHEMA, "sample", "sample_id", params
    )