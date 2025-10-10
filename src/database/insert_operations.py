from candigv2_logging.logging import CanDIGLogger
from typing import Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import re
from connexion.exceptions import ProblemException
from datetime import datetime, date
from ..config import settings
from sqlalchemy import select, text

logger = CanDIGLogger(__file__)

async def create_person(
    session: AsyncSession,
    record_data: dict,
):
    # Handle birth_datetime conversion
    if 'birth_datetime' in record_data and record_data['birth_datetime'] is not None:
        if isinstance(record_data['birth_datetime'], str):
            try:
                record_data['birth_datetime'] = datetime.fromisoformat(
                    record_data['birth_datetime'].replace('Z', '+00:00')
                )
            except ValueError as e:
                raise ProblemException(
                status=400,
                title="Bad Request",
                detail=f"Invalid datetime format: {record_data['birth_datetime']}. Expected ISO 8601 format."
            )


    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.person (
            gender_concept_id, year_of_birth, month_of_birth, 
            day_of_birth, birth_datetime, race_concept_id, ethnicity_concept_id,
            location_id, provider_id, care_site_id, person_source_value,
            gender_source_value, gender_source_concept_id, race_source_value,
            race_source_concept_id, ethnicity_source_value, ethnicity_source_concept_id
        ) VALUES (
            :gender_concept_id, :year_of_birth, :month_of_birth,
            :day_of_birth, :birth_datetime, :race_concept_id, :ethnicity_concept_id,
            :location_id, :provider_id, :care_site_id, :person_source_value,
            :gender_source_value, :gender_source_concept_id, :race_source_value,
            :race_source_concept_id, :ethnicity_source_value, :ethnicity_source_concept_id
        ) RETURNING person_id, gender_concept_id, year_of_birth, month_of_birth, 
            day_of_birth, birth_datetime, race_concept_id, ethnicity_concept_id,
            location_id, provider_id, care_site_id, person_source_value,
            gender_source_value, gender_source_concept_id, race_source_value,
            race_source_concept_id, ethnicity_source_value, ethnicity_source_concept_id
    """)

    # Prepare parameters with values from record_data
    person_params = {
        "gender_concept_id": int(record_data.get('gender_concept_id')) if record_data.get('gender_concept_id') else None,
        "year_of_birth": int(record_data.get('year_of_birth')) if record_data.get('year_of_birth') else None,
        "month_of_birth": int(record_data.get('month_of_birth')) if record_data.get('month_of_birth') else None,
        "day_of_birth": int(record_data.get('day_of_birth')) if record_data.get('day_of_birth') else None,
        "birth_datetime": record_data.get('birth_datetime'),
        "race_concept_id": int(record_data.get('race_concept_id')) if record_data.get('race_concept_id') else None,
        "ethnicity_concept_id": int(record_data.get('ethnicity_concept_id')) if record_data.get('ethnicity_concept_id') else None,
        "location_id": int(record_data.get('location_id')) if record_data.get('location_id') else None,
        "provider_id": int(record_data.get('provider_id')) if record_data.get('provider_id') else None,
        "care_site_id": int(record_data.get('care_site_id')) if record_data.get('care_site_id') else None,
        "person_source_value": record_data.get('person_source_value'),
        "gender_source_value": record_data.get('gender_source_value'),
        "gender_source_concept_id": int(record_data.get('gender_source_concept_id')) if record_data.get('gender_source_concept_id') else None,
        "race_source_value": record_data.get('race_source_value'),
        "race_source_concept_id": int(record_data.get('race_source_concept_id')) if record_data.get('race_source_concept_id') else None,
        "ethnicity_source_value": record_data.get('ethnicity_source_value'),
        "ethnicity_source_concept_id": int(record_data.get('ethnicity_source_concept_id')) if record_data.get('ethnicity_source_concept_id') else None
    }

    # Execute sql
    result = await session.execute(insert_sql, person_params)
    row = result.fetchone()

    # Convert row to dictionary
    person_dict = {
        "person_id": row.person_id,
        "gender_concept_id": row.gender_concept_id,
        "year_of_birth": row.year_of_birth,
        "month_of_birth": row.month_of_birth,
        "day_of_birth": row.day_of_birth,
        "birth_datetime": row.birth_datetime,
        "race_concept_id": row.race_concept_id,
        "ethnicity_concept_id": row.ethnicity_concept_id,
        "location_id": row.location_id,
        "provider_id": row.provider_id,
        "care_site_id": row.care_site_id,
        "person_source_value": row.person_source_value,
        "gender_source_value": row.gender_source_value,
        "gender_source_concept_id": row.gender_source_concept_id,
        "race_source_value": row.race_source_value,
        "race_source_concept_id": row.race_source_concept_id,
        "ethnicity_source_value": row.ethnicity_source_value,
        "ethnicity_source_concept_id": row.ethnicity_source_concept_id
    }

    return person_dict


async def create_observation(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new observation record into the database.
    """
    # Handle observation_datetime conversion
    if 'observation_datetime' in record_data and record_data['observation_datetime'] is not None:
        if isinstance(record_data['observation_datetime'], str):
            try:
                record_data['observation_datetime'] = datetime.fromisoformat(
                    record_data['observation_datetime'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data['observation_datetime']}. Expected ISO 8601 format."
                )


    # Handle observation_date conversion
    if 'observation_date' in record_data and record_data['observation_date'] is not None:
        if isinstance(record_data['observation_date'], str):
            try:
                record_data['observation_date'] = date.fromisoformat(record_data['observation_date'])
            except ValueError:
                raise ProblemException(
                status=400,
                title="Bad Request",
                detail=f"Invalid datetime format: {record_data['observation_date']}. Expected ISO 8601 format."
            )


    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.observation (
            person_id, observation_concept_id, observation_date, observation_datetime,
            observation_type_concept_id, value_as_number, value_as_string, value_as_concept_id,
            qualifier_concept_id, unit_concept_id, provider_id, visit_occurrence_id,
            visit_detail_id, observation_source_value, observation_source_concept_id,
            unit_source_value, qualifier_source_value, value_source_value,
            observation_event_id, obs_event_field_concept_id
        ) VALUES (
            :person_id, :observation_concept_id, :observation_date, :observation_datetime,
            :observation_type_concept_id, :value_as_number, :value_as_string, :value_as_concept_id,
            :qualifier_concept_id, :unit_concept_id, :provider_id, :visit_occurrence_id,
            :visit_detail_id, :observation_source_value, :observation_source_concept_id,
            :unit_source_value, :qualifier_source_value, :value_source_value,
            :observation_event_id, :obs_event_field_concept_id
        ) RETURNING observation_id, person_id, observation_concept_id, observation_date, observation_datetime,
            observation_type_concept_id, value_as_number, value_as_string, value_as_concept_id,
            qualifier_concept_id, unit_concept_id, provider_id, visit_occurrence_id,
            visit_detail_id, observation_source_value, observation_source_concept_id,
            unit_source_value, qualifier_source_value, value_source_value,
            observation_event_id, obs_event_field_concept_id
    """)

    observation_params = {
        "person_id": int(record_data.get('person_id')) if record_data.get('person_id') else None,
        "observation_concept_id": int(record_data.get('observation_concept_id')) if record_data.get('observation_concept_id') else None,
        "observation_date": record_data.get('observation_date'),
        "observation_datetime": record_data.get('observation_datetime'),
        "observation_type_concept_id": int(record_data.get('observation_type_concept_id')) if record_data.get('observation_type_concept_id') else None,
        "value_as_number": record_data.get('value_as_number'),
        "value_as_string": record_data.get('value_as_string'),
        "value_as_concept_id": int(record_data.get('value_as_concept_id')) if record_data.get('value_as_concept_id') else None,
        "qualifier_concept_id": int(record_data.get('qualifier_concept_id')) if record_data.get('qualifier_concept_id') else None,
        "unit_concept_id": int(record_data.get('unit_concept_id')) if record_data.get('unit_concept_id') else None,
        "provider_id": int(record_data.get('provider_id')) if record_data.get('provider_id') else None,
        "visit_occurrence_id": int(record_data.get('visit_occurrence_id')) if record_data.get('visit_occurrence_id') else None,
        "visit_detail_id": int(record_data.get('visit_detail_id')) if record_data.get('visit_detail_id') else None,
        "observation_source_value": record_data.get('observation_source_value'),
        "observation_source_concept_id": int(record_data.get('observation_source_concept_id')) if record_data.get('observation_source_concept_id') else None,
        "unit_source_value": record_data.get('unit_source_value'),
        "qualifier_source_value": record_data.get('qualifier_source_value'),
        "value_source_value": record_data.get('value_source_value'),
        "observation_event_id": int(record_data.get('observation_event_id')) if record_data.get('observation_event_id') else None,
        "obs_event_field_concept_id": int(record_data.get('obs_event_field_concept_id')) if record_data.get('obs_event_field_concept_id') else None
    }

    result = await session.execute(insert_sql, observation_params)
    row = result.fetchone()

    # Convert row to dictionary
    observation_dict = {
        "observation_id": row.observation_id,
        "person_id": row.person_id,
        "observation_concept_id": row.observation_concept_id,
        "observation_date": row.observation_date,
        "observation_datetime": row.observation_datetime,
        "observation_type_concept_id": row.observation_type_concept_id,
        "value_as_number": row.value_as_number,
        "value_as_string": row.value_as_string,
        "value_as_concept_id": row.value_as_concept_id,
        "qualifier_concept_id": row.qualifier_concept_id,
        "unit_concept_id": row.unit_concept_id,
        "provider_id": row.provider_id,
        "visit_occurrence_id": row.visit_occurrence_id,
        "visit_detail_id": row.visit_detail_id,
        "observation_source_value": row.observation_source_value,
        "observation_source_concept_id": row.observation_source_concept_id,
        "unit_source_value": row.unit_source_value,
        "qualifier_source_value": row.qualifier_source_value,
        "value_source_value": row.value_source_value,
        "observation_event_id": row.observation_event_id,
        "obs_event_field_concept_id": row.obs_event_field_concept_id
    }

    return observation_dict

async def create_condition_occurrence(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new condition_occurrence record into the database.
    """
    # Handle datetime conversions
    for field in ['condition_start_datetime', 'condition_end_datetime']:
        if field in record_data and record_data[field] is not None and isinstance(record_data[field], str):
            try:
                record_data[field] = datetime.fromisoformat(record_data[field].replace('Z', '+00:00'))
            except ValueError:
                raise ProblemException(
                status=400,
                title="Bad Request",
                detail=f"Invalid datetime format: {record_data[field]}. Expected ISO 8601 format."
            )


    # Handle date conversions
    for field in ['condition_start_date', 'condition_end_date']:
         if field in record_data and record_data[field] is not None and isinstance(record_data[field], str):
            try:
                record_data[field] = date.fromisoformat(record_data[field])
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid birth_datetime format: {record_data[field]}. Expected ISO 8601 format."
                )

    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.condition_occurrence (
            person_id, condition_concept_id, condition_start_date, condition_start_datetime,
            condition_end_date, condition_end_datetime, condition_type_concept_id,
            condition_status_concept_id, stop_reason, provider_id, visit_occurrence_id,
            visit_detail_id, condition_source_value, condition_source_concept_id,
            condition_status_source_value
        ) VALUES (
            :person_id, :condition_concept_id, :condition_start_date, :condition_start_datetime,
            :condition_end_date, :condition_end_datetime, :condition_type_concept_id,
            :condition_status_concept_id, :stop_reason, :provider_id, :visit_occurrence_id,
            :visit_detail_id, :condition_source_value, :condition_source_concept_id,
            :condition_status_source_value
        ) RETURNING condition_occurrence_id, person_id, condition_concept_id, condition_start_date, 
            condition_start_datetime, condition_end_date, condition_end_datetime, 
            condition_type_concept_id, condition_status_concept_id, stop_reason, 
            provider_id, visit_occurrence_id, visit_detail_id, condition_source_value, 
            condition_source_concept_id, condition_status_source_value
    """)

    condition_occurrence_params = {
        "person_id": int(record_data.get('person_id')) if record_data.get('person_id') else None,
        "condition_concept_id": int(record_data.get('condition_concept_id')) if record_data.get('condition_concept_id') else None,
        "condition_start_date": record_data.get('condition_start_date'),
        "condition_start_datetime": record_data.get('condition_start_datetime'),
        "condition_end_date": record_data.get('condition_end_date'),
        "condition_end_datetime": record_data.get('condition_end_datetime'),
        "condition_type_concept_id": int(record_data.get('condition_type_concept_id')) if record_data.get('condition_type_concept_id') else None,
        "condition_status_concept_id": int(record_data.get('condition_status_concept_id')) if record_data.get('condition_status_concept_id') else None,
        "stop_reason": record_data.get('stop_reason'),
        "provider_id": int(record_data.get('provider_id')) if record_data.get('provider_id') else None,
        "visit_occurrence_id": int(record_data.get('visit_occurrence_id')) if record_data.get('visit_occurrence_id') else None,
        "visit_detail_id": int(record_data.get('visit_detail_id')) if record_data.get('visit_detail_id') else None,
        "condition_source_value": record_data.get('condition_source_value'),
        "condition_source_concept_id": int(record_data.get('condition_source_concept_id')) if record_data.get('condition_source_concept_id') else None,
        "condition_status_source_value": record_data.get('condition_status_source_value')
    }

    result = await session.execute(insert_sql, condition_occurrence_params)
    row = result.fetchone()

    # Convert row to dictionary
    condition_occurrence_dict = {
        "condition_occurrence_id": row.condition_occurrence_id,
        "person_id": row.person_id,
        "condition_concept_id": row.condition_concept_id,
        "condition_start_date": row.condition_start_date,
        "condition_start_datetime": row.condition_start_datetime,
        "condition_end_date": row.condition_end_date,
        "condition_end_datetime": row.condition_end_datetime,
        "condition_type_concept_id": row.condition_type_concept_id,
        "condition_status_concept_id": row.condition_status_concept_id,
        "stop_reason": row.stop_reason,
        "provider_id": row.provider_id,
        "visit_occurrence_id": row.visit_occurrence_id,
        "visit_detail_id": row.visit_detail_id,
        "condition_source_value": row.condition_source_value,
        "condition_source_concept_id": row.condition_source_concept_id,
        "condition_status_source_value": row.condition_status_source_value
    }

    return condition_occurrence_dict

async def create_episode(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new episode record into the database.
    """
    # Handle datetime conversions
    for field in ['episode_start_datetime', 'episode_end_datetime']:
        if field in record_data and record_data[field] is not None and isinstance(record_data[field], str):
            try:
                record_data[field] = datetime.fromisoformat(record_data[field].replace('Z', '+00:00'))
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid birth_datetime format: {record_data[field]}. Expected ISO 8601 format."
                )

    # Handle date conversions
    for field in ['episode_start_date', 'episode_end_date']:
        if field in record_data and record_data[field] is not None and isinstance(record_data[field], str):
            try:
                record_data[field] = date.fromisoformat(record_data[field])
            except ValueError:
                raise ProblemException(
                status=400,
                title="Bad Request",
                detail=f"Invalid birth_datetime format: {record_data[field]}. Expected ISO 8601 format."
            )

    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.episode (
            person_id, episode_concept_id, episode_start_date, episode_start_datetime,
            episode_end_date, episode_end_datetime, episode_parent_id, episode_number,
            episode_object_concept_id, episode_type_concept_id, episode_source_value,
            episode_source_concept_id
        ) VALUES (
            :person_id, :episode_concept_id, :episode_start_date, :episode_start_datetime,
            :episode_end_date, :episode_end_datetime, :episode_parent_id, :episode_number,
            :episode_object_concept_id, :episode_type_concept_id, :episode_source_value,
            :episode_source_concept_id
        ) RETURNING episode_id, person_id, episode_concept_id, episode_start_date, episode_start_datetime,
            episode_end_date, episode_end_datetime, episode_parent_id, episode_number,
            episode_object_concept_id, episode_type_concept_id, episode_source_value,
            episode_source_concept_id
    """)

    episode_params = {
        "person_id": int(record_data.get('person_id')) if record_data.get('person_id') else None,
        "episode_concept_id": int(record_data.get('episode_concept_id')) if record_data.get('episode_concept_id') else None,
        "episode_start_date": record_data.get('episode_start_date'),
        "episode_start_datetime": record_data.get('episode_start_datetime'),
        "episode_end_date": record_data.get('episode_end_date'),
        "episode_end_datetime": record_data.get('episode_end_datetime'),
        "episode_parent_id": int(record_data.get('episode_parent_id')) if record_data.get('episode_parent_id') else None,
        "episode_number": int(record_data.get('episode_number')) if record_data.get('episode_number') else None,
        "episode_object_concept_id": int(record_data.get('episode_object_concept_id')) if record_data.get('episode_object_concept_id') else None,
        "episode_type_concept_id": int(record_data.get('episode_type_concept_id')) if record_data.get('episode_type_concept_id') else None,
        "episode_source_value": record_data.get('episode_source_value'),
        "episode_source_concept_id": int(record_data.get('episode_source_concept_id')) if record_data.get('episode_source_concept_id') else None
    }

    result = await session.execute(insert_sql, episode_params)
    row = result.fetchone()

    # Convert row to dictionary
    episode_dict = {
        "episode_id": row.episode_id,
        "person_id": row.person_id,
        "episode_concept_id": row.episode_concept_id,
        "episode_start_date": row.episode_start_date,
        "episode_start_datetime": row.episode_start_datetime,
        "episode_end_date": row.episode_end_date,
        "episode_end_datetime": row.episode_end_datetime,
        "episode_parent_id": row.episode_parent_id,
        "episode_number": row.episode_number,
        "episode_object_concept_id": row.episode_object_concept_id,
        "episode_type_concept_id": row.episode_type_concept_id,
        "episode_source_value": row.episode_source_value,
        "episode_source_concept_id": row.episode_source_concept_id
    }

    return episode_dict

async def create_episode_event(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new episode_event record into the database.
    """
    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.episode_event (
            episode_id, event_id, episode_event_field_concept_id
        ) VALUES (
            :episode_id, :event_id, :episode_event_field_concept_id
        ) RETURNING episode_id, event_id, episode_event_field_concept_id
    """)

    episode_event_params = {
        "episode_id": int(record_data.get('episode_id')),
        "event_id": int(record_data.get('event_id')),
        "episode_event_field_concept_id": int(record_data.get('episode_event_field_concept_id')),
    }

    # Execute
    result = await session.execute(insert_sql, episode_event_params)
    row = result.fetchone()

    # Convert row to dictionary
    episode_event_dict = {
        "episode_id": row.episode_id,
        "event_id": row.event_id,
        "episode_event_field_concept_id": row.episode_event_field_concept_id
    }

    return episode_event_dict

async def create_measurement(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new measurement record into the database.
    """
    # Handle measurement_datetime conversion
    if 'measurement_datetime' in record_data and record_data['measurement_datetime'] is not None:
        if isinstance(record_data['measurement_datetime'], str):
            try:
                record_data['measurement_datetime'] = datetime.fromisoformat(
                    record_data['measurement_datetime'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data['measurement_datetime']}. Expected ISO 8601 format."
                )
    
    # Handle measurement_date conversion
    if 'measurement_date' in record_data and record_data['measurement_date'] is not None:
        if isinstance(record_data['measurement_date'], str):
            try:
                record_data['measurement_date'] = date.fromisoformat(record_data['measurement_date'])
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid birth_datetime format: {record_data['measurement_date']}. Expected ISO 8601 format."
                )

    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.measurement (
            person_id, measurement_concept_id, measurement_date, measurement_datetime,
            measurement_time, measurement_type_concept_id, operator_concept_id,
            value_as_number, value_as_concept_id, unit_concept_id, range_low,
            range_high, provider_id, visit_occurrence_id, visit_detail_id,
            measurement_source_value, measurement_source_concept_id, unit_source_value,
            unit_source_concept_id, value_source_value, measurement_event_id,
            meas_event_field_concept_id
        ) VALUES (
            :person_id, :measurement_concept_id, :measurement_date, :measurement_datetime,
            :measurement_time, :measurement_type_concept_id, :operator_concept_id,
            :value_as_number, :value_as_concept_id, :unit_concept_id, :range_low,
            :range_high, :provider_id, :visit_occurrence_id, :visit_detail_id,
            :measurement_source_value, :measurement_source_concept_id, :unit_source_value,
            :unit_source_concept_id, :value_source_value, :measurement_event_id,
            :meas_event_field_concept_id
        ) RETURNING measurement_id, person_id, measurement_concept_id, measurement_date, measurement_datetime,
            measurement_time, measurement_type_concept_id, operator_concept_id,
            value_as_number, value_as_concept_id, unit_concept_id, range_low,
            range_high, provider_id, visit_occurrence_id, visit_detail_id,
            measurement_source_value, measurement_source_concept_id, unit_source_value,
            unit_source_concept_id, value_source_value, measurement_event_id,
            meas_event_field_concept_id
    """)

    measurement_params = {
        "person_id": int(record_data.get('person_id')) if record_data.get('person_id') else None,
        "measurement_concept_id": int(record_data.get('measurement_concept_id')) if record_data.get('measurement_concept_id') else None,
        "measurement_date": record_data.get('measurement_date'),
        "measurement_datetime": record_data.get('measurement_datetime'),
        "measurement_time": record_data.get('measurement_time'),
        "measurement_type_concept_id": int(record_data.get('measurement_type_concept_id')) if record_data.get('measurement_type_concept_id') else None,
        "operator_concept_id": int(record_data.get('operator_concept_id')) if record_data.get('operator_concept_id') else None,
        "value_as_number": record_data.get('value_as_number'),
        "value_as_concept_id": int(record_data.get('value_as_concept_id')) if record_data.get('value_as_concept_id') else None,
        "unit_concept_id": int(record_data.get('unit_concept_id')) if record_data.get('unit_concept_id') else None,
        "range_low": record_data.get('range_low'),
        "range_high": record_data.get('range_high'),
        "provider_id": int(record_data.get('provider_id')) if record_data.get('provider_id') else None,
        "visit_occurrence_id": int(record_data.get('visit_occurrence_id')) if record_data.get('visit_occurrence_id') else None,
        "visit_detail_id": int(record_data.get('visit_detail_id')) if record_data.get('visit_detail_id') else None,
        "measurement_source_value": record_data.get('measurement_source_value'),
        "measurement_source_concept_id": int(record_data.get('measurement_source_concept_id')) if record_data.get('measurement_source_concept_id') else None,
        "unit_source_value": record_data.get('unit_source_value'),
        "unit_source_concept_id": int(record_data.get('unit_source_concept_id')) if record_data.get('unit_source_concept_id') else None,
        "value_source_value": record_data.get('value_source_value'),
        "measurement_event_id": int(record_data.get('measurement_event_id')) if record_data.get('measurement_event_id') else None,
        "meas_event_field_concept_id": int(record_data.get('meas_event_field_concept_id')) if record_data.get('meas_event_field_concept_id') else None
    }

    result = await session.execute(insert_sql, measurement_params)
    row = result.fetchone()

    # Convert row to dictionary
    measurement_dict = {
        "measurement_id": row.measurement_id,
        "person_id": row.person_id,
        "measurement_concept_id": row.measurement_concept_id,
        "measurement_date": row.measurement_date,
        "measurement_datetime": row.measurement_datetime,
        "measurement_time": row.measurement_time,
        "measurement_type_concept_id": row.measurement_type_concept_id,
        "operator_concept_id": row.operator_concept_id,
        "value_as_number": row.value_as_number,
        "value_as_concept_id": row.value_as_concept_id,
        "unit_concept_id": row.unit_concept_id,
        "range_low": row.range_low,
        "range_high": row.range_high,
        "provider_id": row.provider_id,
        "visit_occurrence_id": row.visit_occurrence_id,
        "visit_detail_id": row.visit_detail_id,
        "measurement_source_value": row.measurement_source_value,
        "measurement_source_concept_id": row.measurement_source_concept_id,
        "unit_source_value": row.unit_source_value,
        "unit_source_concept_id": row.unit_source_concept_id,
        "value_source_value": row.value_source_value,
        "measurement_event_id": row.measurement_event_id,
        "meas_event_field_concept_id": row.meas_event_field_concept_id
    }

    return measurement_dict

async def create_specimen(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new specimen record into the database.
    """
    # Handle specimen_datetime conversion
    if 'specimen_datetime' in record_data and record_data['specimen_datetime'] is not None:
        if isinstance(record_data['specimen_datetime'], str):
            try:
                record_data['specimen_datetime'] = datetime.fromisoformat(
                    record_data['specimen_datetime'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data['specimen_datetime']}. Expected ISO 8601 format."
                )

    # Handle specimen_date conversion
    if 'specimen_date' in record_data and record_data['specimen_date'] is not None:
        if isinstance(record_data['specimen_date'], str):
            try:
                record_data['specimen_date'] = date.fromisoformat(record_data['specimen_date'])
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data['specimen_date']}. Expected ISO 8601 format."
                )

    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.specimen (
            person_id, specimen_concept_id, specimen_type_concept_id, specimen_date,
            specimen_datetime, quantity, unit_concept_id, anatomic_site_concept_id,
            disease_status_concept_id, specimen_source_id, specimen_source_value,
            unit_source_value, anatomic_site_source_value, disease_status_source_value
        ) VALUES (
            :person_id, :specimen_concept_id, :specimen_type_concept_id, :specimen_date,
            :specimen_datetime, :quantity, :unit_concept_id, :anatomic_site_concept_id,
            :disease_status_concept_id, :specimen_source_id, :specimen_source_value,
            :unit_source_value, :anatomic_site_source_value, :disease_status_source_value
        ) RETURNING specimen_id, person_id, specimen_concept_id, specimen_type_concept_id, specimen_date,
            specimen_datetime, quantity, unit_concept_id, anatomic_site_concept_id,
            disease_status_concept_id, specimen_source_id, specimen_source_value,
            unit_source_value, anatomic_site_source_value, disease_status_source_value
    """)

    specimen_params = {
        "person_id": int(record_data.get('person_id')) if record_data.get('person_id') else None,
        "specimen_concept_id": int(record_data.get('specimen_concept_id')) if record_data.get('specimen_concept_id') else None,
        "specimen_type_concept_id": int(record_data.get('specimen_type_concept_id')) if record_data.get('specimen_type_concept_id') else None,
        "specimen_date": record_data.get('specimen_date'),
        "specimen_datetime": record_data.get('specimen_datetime'),
        "quantity": record_data.get('quantity'),
        "unit_concept_id": int(record_data.get('unit_concept_id')) if record_data.get('unit_concept_id') else None,
        "anatomic_site_concept_id": int(record_data.get('anatomic_site_concept_id')) if record_data.get('anatomic_site_concept_id') else None,
        "disease_status_concept_id": int(record_data.get('disease_status_concept_id')) if record_data.get('disease_status_concept_id') else None,
        "specimen_source_id": record_data.get('specimen_source_id'),
        "specimen_source_value": record_data.get('specimen_source_value'),
        "unit_source_value": record_data.get('unit_source_value'),
        "anatomic_site_source_value": record_data.get('anatomic_site_source_value'),
        "disease_status_source_value": record_data.get('disease_status_source_value')
    }

    result = await session.execute(insert_sql, specimen_params)
    row = result.fetchone()

    # Convert row to dictionary
    specimen_dict = {
        "specimen_id": row.specimen_id,
        "person_id": row.person_id,
        "specimen_concept_id": row.specimen_concept_id,
        "specimen_type_concept_id": row.specimen_type_concept_id,
        "specimen_date": row.specimen_date,
        "specimen_datetime": row.specimen_datetime,
        "quantity": row.quantity,
        "unit_concept_id": row.unit_concept_id,
        "anatomic_site_concept_id": row.anatomic_site_concept_id,
        "disease_status_concept_id": row.disease_status_concept_id,
        "specimen_source_id": row.specimen_source_id,
        "specimen_source_value": row.specimen_source_value,
        "unit_source_value": row.unit_source_value,
        "anatomic_site_source_value": row.anatomic_site_source_value,
        "disease_status_source_value": row.disease_status_source_value
    }

    return specimen_dict

async def create_procedure_occurrence(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new procedure_occurrence record into the database.
    """
    # Handle datetime conversions from ISO format string to datetime object
    for field in ['procedure_datetime', 'procedure_end_datetime']:
        if field in record_data and record_data[field] is not None and isinstance(record_data[field], str):
            try:
                record_data[field] = datetime.fromisoformat(record_data[field].replace('Z', '+00:00'))
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data[field]}. Expected ISO 8601 format."
                )
    # Handle date conversions from ISO format string to date object
    for field in ['procedure_date', 'procedure_end_date']:
        if field in record_data and record_data[field] is not None and isinstance(record_data[field], str):
            try:
                record_data[field] = date.fromisoformat(record_data[field])
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data[field]}. Expected ISO 8601 format."
                )

    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.procedure_occurrence (
            person_id, procedure_concept_id, procedure_date, procedure_datetime,
            procedure_end_date, procedure_end_datetime, procedure_type_concept_id,
            modifier_concept_id, quantity, provider_id, visit_occurrence_id,
            visit_detail_id, procedure_source_value, procedure_source_concept_id,
            modifier_source_value
        ) VALUES (
            :person_id, :procedure_concept_id, :procedure_date, :procedure_datetime,
            :procedure_end_date, :procedure_end_datetime, :procedure_type_concept_id,
            :modifier_concept_id, :quantity, :provider_id, :visit_occurrence_id,
            :visit_detail_id, :procedure_source_value, :procedure_source_concept_id,
            :modifier_source_value
        ) RETURNING procedure_occurrence_id, person_id, procedure_concept_id, procedure_date, procedure_datetime,
            procedure_end_date, procedure_end_datetime, procedure_type_concept_id,
            modifier_concept_id, quantity, provider_id, visit_occurrence_id,
            visit_detail_id, procedure_source_value, procedure_source_concept_id,
            modifier_source_value
    """)

    # Prepare parameters with values from record_data, ensuring type consistency
    procedure_params = {
        "person_id": int(record_data.get('person_id')) if record_data.get('person_id') else None,
        "procedure_concept_id": int(record_data.get('procedure_concept_id')) if record_data.get('procedure_concept_id') else None,
        "procedure_date": record_data.get('procedure_date'),
        "procedure_datetime": record_data.get('procedure_datetime'),
        "procedure_end_date": record_data.get('procedure_end_date'),
        "procedure_end_datetime": record_data.get('procedure_end_datetime'),
        "procedure_type_concept_id": int(record_data.get('procedure_type_concept_id')) if record_data.get('procedure_type_concept_id') else None,
        "modifier_concept_id": int(record_data.get('modifier_concept_id')) if record_data.get('modifier_concept_id') else None,
        "quantity": int(record_data.get('quantity')) if record_data.get('quantity') is not None else None,
        "provider_id": int(record_data.get('provider_id')) if record_data.get('provider_id') else None,
        "visit_occurrence_id": int(record_data.get('visit_occurrence_id')) if record_data.get('visit_occurrence_id') else None,
        "visit_detail_id": int(record_data.get('visit_detail_id')) if record_data.get('visit_detail_id') else None,
        "procedure_source_value": record_data.get('procedure_source_value'),
        "procedure_source_concept_id": int(record_data.get('procedure_source_concept_id')) if record_data.get('procedure_source_concept_id') else None,
        "modifier_source_value": record_data.get('modifier_source_value')
    }

    # Execute sql
    result = await session.execute(insert_sql, procedure_params)
    row = result.fetchone()

    # Convert row to dictionary
    procedure_occurrence_dict = {
        "procedure_occurrence_id": row.procedure_occurrence_id,
        "person_id": row.person_id,
        "procedure_concept_id": row.procedure_concept_id,
        "procedure_date": row.procedure_date,
        "procedure_datetime": row.procedure_datetime,
        "procedure_end_date": row.procedure_end_date,
        "procedure_end_datetime": row.procedure_end_datetime,
        "procedure_type_concept_id": row.procedure_type_concept_id,
        "modifier_concept_id": row.modifier_concept_id,
        "quantity": row.quantity,
        "provider_id": row.provider_id,
        "visit_occurrence_id": row.visit_occurrence_id,
        "visit_detail_id": row.visit_detail_id,
        "procedure_source_value": row.procedure_source_value,
        "procedure_source_concept_id": row.procedure_source_concept_id,
        "modifier_source_value": row.modifier_source_value
    }

    return procedure_occurrence_dict

async def create_drug_exposure(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new drug_exposure record into the database.
    """
    # Handle datetime conversions from ISO format string to datetime object
    for field in ['drug_exposure_start_datetime', 'drug_exposure_end_datetime']:
        if field in record_data and record_data[field] is not None and isinstance(record_data[field], str):
            try:
                record_data[field] = datetime.fromisoformat(record_data[field].replace('Z', '+00:00'))
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data[field]}. Expected ISO 8601 format."
                )

    # Handle date conversions from ISO format string to date object
    for field in ['drug_exposure_start_date', 'drug_exposure_end_date', 'verbatim_end_date']:
        if field in record_data and record_data[field] is not None and isinstance(record_data[field], str):
            try:
                record_data[field] = date.fromisoformat(record_data[field])
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data[field]}. Expected ISO 8601 format."
                )

    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.drug_exposure (
            person_id, drug_concept_id, drug_exposure_start_date, drug_exposure_start_datetime,
            drug_exposure_end_date, drug_exposure_end_datetime, verbatim_end_date,
            drug_type_concept_id, stop_reason, refills, quantity, days_supply, sig,
            route_concept_id, lot_number, provider_id, visit_occurrence_id, visit_detail_id,
            drug_source_value, drug_source_concept_id, route_source_value, dose_unit_source_value
        ) VALUES (
            :person_id, :drug_concept_id, :drug_exposure_start_date, :drug_exposure_start_datetime,
            :drug_exposure_end_date, :drug_exposure_end_datetime, :verbatim_end_date,
            :drug_type_concept_id, :stop_reason, :refills, :quantity, :days_supply, :sig,
            :route_concept_id, :lot_number, :provider_id, :visit_occurrence_id, :visit_detail_id,
            :drug_source_value, :drug_source_concept_id, :route_source_value, :dose_unit_source_value
        ) RETURNING drug_exposure_id, person_id, drug_concept_id, drug_exposure_start_date, drug_exposure_start_datetime,
            drug_exposure_end_date, drug_exposure_end_datetime, verbatim_end_date,
            drug_type_concept_id, stop_reason, refills, quantity, days_supply, sig,
            route_concept_id, lot_number, provider_id, visit_occurrence_id, visit_detail_id,
            drug_source_value, drug_source_concept_id, route_source_value, dose_unit_source_value
    """)

    # Prepare parameters with values from record_data, ensuring type consistency
    drug_exposure_params = {
        "person_id": int(record_data.get('person_id')) if record_data.get('person_id') else None,
        "drug_concept_id": int(record_data.get('drug_concept_id')) if record_data.get('drug_concept_id') else None,
        "drug_exposure_start_date": record_data.get('drug_exposure_start_date'),
        "drug_exposure_start_datetime": record_data.get('drug_exposure_start_datetime'),
        "drug_exposure_end_date": record_data.get('drug_exposure_end_date'),
        "drug_exposure_end_datetime": record_data.get('drug_exposure_end_datetime'),
        "verbatim_end_date": record_data.get('verbatim_end_date'),
        "drug_type_concept_id": int(record_data.get('drug_type_concept_id')) if record_data.get('drug_type_concept_id') else None,
        "stop_reason": record_data.get('stop_reason'),
        "refills": int(record_data.get('refills')) if record_data.get('refills') is not None else None,
        "quantity": record_data.get('quantity'), # NUMERIC type
        "days_supply": int(record_data.get('days_supply')) if record_data.get('days_supply') is not None else None,
        "sig": record_data.get('sig'),
        "route_concept_id": int(record_data.get('route_concept_id')) if record_data.get('route_concept_id') else None,
        "lot_number": record_data.get('lot_number'),
        "provider_id": int(record_data.get('provider_id')) if record_data.get('provider_id') else None,
        "visit_occurrence_id": int(record_data.get('visit_occurrence_id')) if record_data.get('visit_occurrence_id') else None,
        "visit_detail_id": int(record_data.get('visit_detail_id')) if record_data.get('visit_detail_id') else None,
        "drug_source_value": record_data.get('drug_source_value'),
        "drug_source_concept_id": int(record_data.get('drug_source_concept_id')) if record_data.get('drug_source_concept_id') else None,
        "route_source_value": record_data.get('route_source_value'),
        "dose_unit_source_value": record_data.get('dose_unit_source_value')
    }

    # Execute sql
    result = await session.execute(insert_sql, drug_exposure_params)
    row = result.fetchone()

    # Convert row to dictionary
    drug_exposure_dict = {
        "drug_exposure_id": row.drug_exposure_id,
        "person_id": row.person_id,
        "drug_concept_id": row.drug_concept_id,
        "drug_exposure_start_date": row.drug_exposure_start_date,
        "drug_exposure_start_datetime": row.drug_exposure_start_datetime,
        "drug_exposure_end_date": row.drug_exposure_end_date,
        "drug_exposure_end_datetime": row.drug_exposure_end_datetime,
        "verbatim_end_date": row.verbatim_end_date,
        "drug_type_concept_id": row.drug_type_concept_id,
        "stop_reason": row.stop_reason,
        "refills": row.refills,
        "quantity": row.quantity,
        "days_supply": row.days_supply,
        "sig": row.sig,
        "route_concept_id": row.route_concept_id,
        "lot_number": row.lot_number,
        "provider_id": row.provider_id,
        "visit_occurrence_id": row.visit_occurrence_id,
        "visit_detail_id": row.visit_detail_id,
        "drug_source_value": row.drug_source_value,
        "drug_source_concept_id": row.drug_source_concept_id,
        "route_source_value": row.route_source_value,
        "dose_unit_source_value": row.dose_unit_source_value
    }

    return drug_exposure_dict

async def create_fact_relationship(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new fact_relationship record into the database.
    """
    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.fact_relationship (
            domain_concept_id_1, fact_id_1, domain_concept_id_2, fact_id_2, relationship_concept_id
        ) VALUES (
            :domain_concept_id_1, :fact_id_1, :domain_concept_id_2, :fact_id_2, :relationship_concept_id
        ) RETURNING domain_concept_id_1, fact_id_1, domain_concept_id_2, fact_id_2, relationship_concept_id
    """)

    fact_relationship_params = {
        "domain_concept_id_1": int(record_data.get('domain_concept_id_1')),
        "fact_id_1": int(record_data.get('fact_id_1')),
        "domain_concept_id_2": int(record_data.get('domain_concept_id_2')),
        "fact_id_2": int(record_data.get('fact_id_2')),
        "relationship_concept_id": int(record_data.get('relationship_concept_id'))
    }

    result = await session.execute(insert_sql, fact_relationship_params)
    row = result.fetchone()

    # Convert row to dictionary
    fact_relationship_dict = {
        "domain_concept_id_1": row.domain_concept_id_1,
        "fact_id_1": row.fact_id_1,
        "domain_concept_id_2": row.domain_concept_id_2,
        "fact_id_2": row.fact_id_2,
        "relationship_concept_id": row.relationship_concept_id
    }

    return fact_relationship_dict

async def create_death(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new death record into the database.
    """
    # Handle death_datetime conversion
    if 'death_datetime' in record_data and record_data['death_datetime'] is not None:
        if isinstance(record_data['death_datetime'], str):
            try:
                record_data['death_datetime'] = datetime.fromisoformat(
                    record_data['death_datetime'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data['date_datetime']}. Expected ISO 8601 format."
                )

    # Handle death_date conversion
    if 'death_date' in record_data and record_data['death_date'] is not None:
        if isinstance(record_data['death_date'], str):
            try:
                record_data['death_date'] = date.fromisoformat(record_data['death_date'])
            except ValueError:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"Invalid datetime format: {record_data['death_date']}. Expected ISO 8601 format."
                )

    insert_sql = text(f"""
        INSERT INTO {settings.CDM_SCHEMA}.death (
            person_id, death_date, death_datetime, death_type_concept_id,
            cause_concept_id, cause_source_value, cause_source_concept_id
        ) VALUES (
            :person_id, :death_date, :death_datetime, :death_type_concept_id,
            :cause_concept_id, :cause_source_value, :cause_source_concept_id
        ) RETURNING person_id, death_date, death_datetime, death_type_concept_id,
            cause_concept_id, cause_source_value, cause_source_concept_id
    """)

    death_params = {
        "person_id": int(record_data.get('person_id')),
        "death_date": record_data.get('death_date'),
        "death_datetime": record_data.get('death_datetime') if record_data.get('death_datetime') else None,
        "death_type_concept_id": int(record_data.get('death_type_concept_id')) if record_data.get('death_type_concept_id') else None,
        "cause_concept_id": int(record_data.get('cause_concept_id')) if record_data.get('cause_concept_id') else None,
        "cause_source_value": record_data.get('cause_source_value') if record_data.get('cause_source_value') else None,
        "cause_source_concept_id": int(record_data.get('cause_source_concept_id')) if record_data.get('cause_source_concept_id') else None
    }

    result = await session.execute(insert_sql, death_params)
    row = result.fetchone()

    # Convert row to dictionary
    death_dict = {
        "person_id": row.person_id,
        "death_date": row.death_date,
        "death_datetime": row.death_datetime,
        "death_type_concept_id": row.death_type_concept_id,
        "cause_concept_id": row.cause_concept_id,
        "cause_source_value": row.cause_source_value,
        "cause_source_concept_id": row.cause_source_concept_id
    }

    return death_dict

async def create_dataset(
    session: AsyncSession,
    record_data: dict,
):
    """
    Inserts a new dataset record into the database.
    """
    insert_sql = text(f"""
                INSERT INTO {settings.CANDIG_SCHEMA}.dataset (source_value, info)
                VALUES (:source_value, :info)
                RETURNING id, source_value, info
                """)

    dataset_params = {
        "source_value": record_data.get('source_value'),
        "info": record_data.get('info') if record_data.get('info') else None,
    }

    result = await session.execute(insert_sql, dataset_params)
    row = result.fetchone()

    # Convert row to dictionary
    dataset_dict = {
        "id": row.id,
        "source_value": row.source_value,
        "info": row.info
    }

    return dataset_dict

async def create_person_in_dataset(
    session: AsyncSession,
    record_data: dict,
):
    """
    Create FK between person and dataset
    """
    insert_sql = text(f"""
                INSERT INTO {settings.CANDIG_SCHEMA}.person_in_dataset (dataset_id, person_id)
                VALUES (:dataset_id, :person_id)
                RETURNING dataset_id, person_id
                """)

    dataset_params = {
        "dataset_id": record_data.get('dataset_id'),
        "person_id": record_data.get('person_id'),
    }

    result = await session.execute(insert_sql, dataset_params)
    row = result.fetchone()

    # Convert row to dictionary
    result_dict = {
        "dataset_id": row.dataset_id,
        "person_id": row.person_id
    }

    return result_dict