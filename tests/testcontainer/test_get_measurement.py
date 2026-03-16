from datetime import date

import pytest
from sqlalchemy import text

from src.api.phenopacket_operations import get_measurements
from src.database.insert_operations import (
    create_measurement,
    create_observation,
    create_person,
)
from tests.testcontainer.conftest import insert_concept



async def test_get_measurements_observation(db_session):
    person = await create_person(
        db_session,
        {
            "gender_concept_id": 8507,
            "year_of_birth": 1990,
            "month_of_birth": 1,
            "day_of_birth": 1,
            "person_source_value": "MEAS_OBS_1",
        },
    )
    person_id = person["person_id"]

    await insert_concept(
        db_session,
        4203711,
        "Follow-up status",
        vocabulary_id="SNOMED",
        code="308273005",
    )
    await insert_concept(
        db_session,
        36309453,
        "Partial response",
        vocabulary_id="LOINC",
        code="LA28369-9",
    )

    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4203711,
            "value_as_concept_id": 36309453,
            "observation_date": date(2021, 11, 15),
        },
    )
    await db_session.flush()

    measurements = await get_measurements(person_id)

    assert measurements is not None
    assert len(measurements) == 1

    measurement = measurements[0]
    assert measurement.assay.id == "SNOMED:308273005"
    assert measurement.assay.label == "Follow-up status"
    assert measurement.value.ontology_class.id == "LOINC:LA28369-9"
    assert measurement.value.ontology_class.label == "Partial response"
    assert measurement.time_observed.timestamp.ToDatetime().date() == date(2021, 11, 15)



async def test_get_measurements_quantity(db_session):
    person = await create_person(
        db_session,
        {
            "gender_concept_id": 8507,
            "year_of_birth": 1990,
            "month_of_birth": 1,
            "day_of_birth": 1,
            "person_source_value": "MEAS_NUM_1",
        },
    )
    person_id = person["person_id"]

    await insert_concept(
        db_session,
        4272032,
        "Prostate specific antigen measurement",
        vocabulary_id="SNOMED",
        code="63476009",
    )
    await insert_concept(
        db_session,
        4122379,
        "mm",
        vocabulary_id="SNOMED",
        code="258673006",
    )

    # Ensure measurement_concept_id=4272032 is included via ancestor filter (4326835).
    await db_session.execute(
        text("""
			INSERT INTO omop.concept_ancestor (
				ancestor_concept_id,
				descendant_concept_id,
				min_levels_of_separation,
				max_levels_of_separation
			)
			VALUES (:ancestor, :descendant, 1, 1)
			ON CONFLICT (ancestor_concept_id, descendant_concept_id) DO NOTHING
		"""),
        {"ancestor": 4326835, "descendant": 4272032},
    )

    await create_measurement(
        db_session,
        {
            "person_id": person_id,
            "measurement_concept_id": 4272032,
            "value_as_number": 8.5,
            "unit_concept_id": 4122379,
            "measurement_date": date(2021, 11, 15),
        },
    )
    await db_session.flush()

    measurements = await get_measurements(person_id)

    assert measurements is not None
    assert len(measurements) == 1

    measurement = measurements[0]
    assert measurement.assay.id == "SNOMED:63476009"
    assert measurement.assay.label == "Prostate specific antigen measurement"
    assert measurement.value.quantity.value == 8.5
    assert measurement.value.quantity.unit.id == "SNOMED:258673006"
    assert measurement.value.quantity.unit.label == "mm"
    assert measurement.time_observed.timestamp.ToDatetime().date() == date(2021, 11, 15)
