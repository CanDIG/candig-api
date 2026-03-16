from datetime import date
from typing import Any, cast

from src.api.phenopacket_operations import get_by_id
from src.database.insert_operations import (
    create_condition_occurrence,
    create_episode,
    create_episode_event,
    create_person,
    create_person_in_dataset,
    create_specimen,
)
from tests.testcontainer.conftest import insert_concept


async def create_phenopacket_data(session, dataset_id: str) -> tuple[int, int, str]:
    person_source_value = "DONOR_001"
    person_record = await create_person(
        session,
        {
            "person_source_value": person_source_value,
            "gender_concept_id": 8507,
            "year_of_birth": 1990,
            "month_of_birth": 3,
            "day_of_birth": 15,
        },
    )
    person_id = int(person_record["person_id"])

    await create_person_in_dataset(
        session,
        {
            "dataset_id": dataset_id,
            "person_id": person_id,
        },
    )

    await insert_concept(
        session,
        45590880,
        "Malignant neoplasm of gallbladder",
        vocabulary_id="ICD10",
        code="C23",
    )
    await insert_concept(
        session,
        44497885,
        "Overlapping lesion of female genital organs",
        vocabulary_id="SNOMED",
        code="C57.8",
    )

    condition_record = await create_condition_occurrence(
        session,
        {
            "person_id": person_id,
            "condition_concept_id": 45590880,
            "condition_start_date": date(2024, 1, 2),
            "condition_end_date": date(2024, 4, 2),
        },
    )

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
            "event_id": condition_record["condition_occurrence_id"],
            "episode_event_field_concept_id": 1147127,
        },
    )

    specimen_record = await create_specimen(
        session,
        {
            "person_id": person_id,
            "specimen_concept_id": 0,
            "specimen_type_concept_id": 0,
            "anatomic_site_concept_id": 44497885,
            "specimen_date": date(2024, 2, 15),
            "specimen_source_id": None,
        },
    )
    specimen_id = int(specimen_record["specimen_id"])

    return person_id, specimen_id, person_source_value


async def test_get_phenopacket(db_session, monkeypatch):
    dataset_id = "dataset_phenopacket"
    monkeypatch.setattr(
        "src.api.phenopacket_operations.is_action_allowed",
        lambda dataset=None: True,
    )

    person_id, specimen_id, person_source_value = await create_phenopacket_data(
        db_session, dataset_id
    )
    await db_session.flush()

    result = await get_by_id(dataset_id, person_id)
    assert isinstance(result, dict)
    phenopacket = cast(dict[str, Any], result)

    assert phenopacket["id"] == str(person_id)

    assert phenopacket["subject"]["id"] == str(person_id)
    assert phenopacket["subject"]["alternate_ids"] == [person_source_value]
    assert phenopacket["subject"]["sex"] == "MALE"
    assert phenopacket["subject"]["taxonomy"]["id"] == "SNOMED:337915000"

    assert len(phenopacket["diseases"]) == 1
    assert phenopacket["diseases"][0]["term"]["id"] == "ICD10:C23"
    assert (
        phenopacket["diseases"][0]["term"]["label"]
        == "Malignant neoplasm of gallbladder"
    )
    assert phenopacket["diseases"][0]["onset"]["timestamp"].startswith("2024-01-02")
    assert phenopacket["diseases"][0]["resolution"]["timestamp"].startswith(
        "2024-04-02"
    )

    assert len(phenopacket["biosamples"]) == 1
    assert phenopacket["biosamples"][0]["id"] == str(specimen_id)
    assert phenopacket["biosamples"][0]["individual_id"] == str(person_id)
    assert phenopacket["biosamples"][0]["sampled_tissue"]["id"] == "SNOMED:C57.8"

    assert phenopacket["meta_data"]["phenopacket_schema_version"] == "2.0.0"
    assert len(phenopacket["meta_data"]["resources"]) > 0


async def test_get_phenopacket_person_not_in_dataset(db_session, monkeypatch):
    dataset_id = "dataset_phenopacket"
    monkeypatch.setattr(
        "src.api.phenopacket_operations.is_action_allowed",
        lambda dataset=None: True,
    )

    person_record = await create_person(
        db_session,
        {
            "person_source_value": "DONOR_NOT_IN_DATASET",
            "gender_concept_id": 8507,
            "year_of_birth": 1991,
            "month_of_birth": 1,
            "day_of_birth": 1,
        },
    )
    person_id = int(person_record["person_id"])
    await db_session.flush()

    response = await get_by_id(dataset_id, person_id)
    assert isinstance(response, tuple)
    result, status_code = response

    assert status_code == 403
    assert f"Person {person_id} not in dataset {dataset_id}" in result["error"]
