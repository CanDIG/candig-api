from datetime import date

import pytest

from src.api.phenopacket_operations import get_diseases
from src.database.insert_operations import (
    create_condition_occurrence,
    create_episode,
    create_episode_event,
    create_measurement,
    create_observation,
    create_person,
)
from tests.testcontainer.conftest import insert_concept


async def create_primary_disease(
    session,
    term_concept_id: int,
    primary_site_concept_id: int,
    laterality_value_concept_id: int,
    onset_date: date,
    resolution_date: date,
) -> tuple[int, int]:
    person_record = await create_person(
        session,
        {
            "person_source_value": (
                f"DISEASE_{term_concept_id}_{onset_date.isoformat()}"
            ),
            "gender_concept_id": 8507,
            "year_of_birth": 1990,
            "month_of_birth": 1,
            "day_of_birth": 1,
        },
    )
    person_id = int(person_record["person_id"])

    await insert_concept(
        session,
        term_concept_id,
        "Malignant neoplasm of gallbladder",
        vocabulary_id="ICD10",
        code="C23",
    )
    await insert_concept(
        session,
        primary_site_concept_id,
        "Breast",
        vocabulary_id="ICDO3",
        code="C50",
    )
    await insert_concept(
        session,
        laterality_value_concept_id,
        "Left",
        vocabulary_id="Cancer Modifier",
        code="OMOP4999911",
    )

    condition_record = await create_condition_occurrence(
        session,
        {
            "person_id": person_id,
            "condition_concept_id": term_concept_id,
            "condition_start_date": onset_date,
            "condition_end_date": resolution_date,
        },
    )
    condition_occurrence_id = int(condition_record["condition_occurrence_id"])

    disease_episode = await create_episode(
        session,
        {
            "person_id": person_id,
            "episode_concept_id": 32528,
        },
    )
    await create_episode_event(
        session,
        {
            "episode_id": disease_episode["episode_id"],
            "event_id": condition_occurrence_id,
            "episode_event_field_concept_id": 1147127,
        },
    )

    await create_observation(
        session,
        {
            "person_id": person_id,
            "observation_concept_id": 3011717,
            "value_as_concept_id": primary_site_concept_id,
            "observation_event_id": condition_occurrence_id,
        },
    )

    await create_measurement(
        session,
        {
            "person_id": person_id,
            "measurement_concept_id": 35918306,
            "value_as_concept_id": laterality_value_concept_id,
            "measurement_event_id": condition_occurrence_id,
        },
    )

    return person_id, condition_occurrence_id



async def test_get_diseases_maps_primary_disease_fields(db_session):
    person_id, _ = await create_primary_disease(
        db_session,
        term_concept_id=45590880,
        primary_site_concept_id=44497844,
        laterality_value_concept_id=36770232,
        onset_date=date(2024, 1, 2),
        resolution_date=date(2024, 4, 2),
    )
    await db_session.flush()

    diseases, status_code = await get_diseases(person_id)

    assert status_code == 200
    assert len(diseases) == 1

    disease = diseases[0]
    assert disease.term.id == "ICD10:C23"
    assert disease.term.label == "Malignant neoplasm of gallbladder"
    assert disease.primary_site.id == "ICDO3:C50"
    assert disease.primary_site.label == "Breast"
    assert disease.laterality.id == "Cancer Modifier:OMOP4999911"
    assert disease.laterality.label == "Left"

    onset = disease.onset.timestamp.ToDatetime()
    resolution = disease.resolution.timestamp.ToDatetime()
    assert onset.date() == date(2024, 1, 2)
    assert resolution.date() == date(2024, 4, 2)



async def test_get_diseases(db_session):
    """get_diseases includes clinical_tnm_finding and disease_stage ontologies."""

    person_id, _ = await create_primary_disease(
        db_session,
        term_concept_id=45590880,
        primary_site_concept_id=44497844,
        laterality_value_concept_id=36770232,
        onset_date=date(2023, 5, 1),
        resolution_date=date(2023, 7, 1),
    )

    # One clinical TNM finding (measurement_concept_id 4164336).
    await insert_concept(
        db_session,
        920010,
        "Tis",
        vocabulary_id="LOINC",
        code="LA3608-2",
    )
    await create_measurement(
        db_session,
        {
            "person_id": person_id,
            "measurement_concept_id": 4164336,
            "value_as_concept_id": 920010,
        },
    )

    # One disease stage observation (observation_concept_id 4295636).
    await insert_concept(
        db_session,
        920011,
        "Stage B",
        vocabulary_id="LOINC",
        code="LA3668-6",
    )
    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4295636,
            "value_as_concept_id": 920011,
        },
    )

    await db_session.flush()

    diseases, status_code = await get_diseases(person_id)

    assert status_code == 200
    assert len(diseases) == 1

    disease = diseases[0]
    assert len(disease.clinical_tnm_finding) == 1
    assert disease.clinical_tnm_finding[0].id == "LOINC:LA3608-2"
    assert disease.clinical_tnm_finding[0].label == "Tis"

    assert len(disease.disease_stage) == 1
    assert disease.disease_stage[0].id == "LOINC:LA3668-6"
    assert disease.disease_stage[0].label == "Stage B"



async def test_get_diseases_comorbidities(db_session):
    person_id, _ = await create_primary_disease(
        db_session,
        term_concept_id=45590880,
        primary_site_concept_id=44497844,
        laterality_value_concept_id=36770232,
        onset_date=date(2022, 1, 10),
        resolution_date=date(2022, 2, 10),
    )

    # Additional condition_occurrence not linked to Disease First Occurrence episode.
    await insert_concept(
        db_session,
        930004,
        "Comorbidity",
        vocabulary_id="SNOMED",
        code="44054006",
    )
    await insert_concept(
        db_session,
        930005,
        "Right",
        vocabulary_id="SNOMED",
        code="24028007",
    )
    comorbidity = await create_condition_occurrence(
        db_session,
        {
            "person_id": person_id,
            "condition_concept_id": 930004,
            "condition_start_date": date(2021, 9, 1),
            "condition_end_date": date(2021, 10, 1),
        },
    )
    await create_measurement(
        db_session,
        {
            "person_id": person_id,
            "measurement_concept_id": 35918306,
            "value_as_concept_id": 930005,
            "measurement_event_id": comorbidity["condition_occurrence_id"],
        },
    )

    await db_session.flush()

    diseases, status_code = await get_diseases(person_id)

    assert status_code == 200
    assert len(diseases) == 2

    by_term = {d.term.label: d for d in diseases}
    assert "Malignant neoplasm of gallbladder" in by_term
    assert "Comorbidity" in by_term
    assert by_term["Comorbidity"].laterality.id == "SNOMED:24028007"
