from datetime import date

import pytest

from src.api.phenopacket_operations import get_biosamples
from src.database.insert_operations import (
    create_measurement,
    create_observation,
    create_person,
    create_specimen,
)
from tests.testcontainer.conftest import insert_concept


async def create_biosample_data(
    session,
    specimen_source_id: str | None,
) -> tuple[int, int]:
    person_record = await create_person(
        session,
        {
            "person_source_value": f"BIOSAMPLE_{specimen_source_id or 'NO_SOURCE'}",
            "gender_concept_id": 8507,
            "year_of_birth": 1990,
            "month_of_birth": 1,
            "day_of_birth": 1,
        },
    )
    person_id = int(person_record["person_id"])

    await insert_concept(
        session,
        44497885,
        "Overlapping lesion of female genital organs",
        vocabulary_id="SNOMED",
        code="C57.8",
    )

    await insert_concept(
        session,
        44498902,
        "Primary cutaneous gamma-delta T-cell lymphoma",
        vocabulary_id="ICDO3",
        code="9726/3",
    )

    await insert_concept(
        session,
        37164072,
        "GX (AJCC)",
        vocabulary_id="SNOMED",
        code="1228845001",
    )

    await insert_concept(
        session,
        40480027,
        "Formalin-fixed paraffin-embedded tissue specimen",
        vocabulary_id="SNOMED",
        code="441652008",
    )

    await insert_concept(
        session,
        9177,
        "Other",
        vocabulary_id="SNOMED",
        code="74964007",
    )

    await insert_concept(
        session,
        920001,
        "T3",
        vocabulary_id="LOINC",
        code="LA3624-9",
    )

    await insert_concept(
        session,
        4298494,
        "HER2 [Presence] in Breast cancer specimen by Immune stain",
        vocabulary_id="LOINC",
        code="85319-2",
    )
    await insert_concept(
        session,
        920002,
        "Positive",
        vocabulary_id="LOINC",
        code="LA6576-8",
    )

    specimen_record = await create_specimen(
        session,
        {
            "person_id": person_id,
            "specimen_concept_id": 0,
            "specimen_type_concept_id": 0,
            "anatomic_site_concept_id": 44497885,
            "specimen_date": date(2023, 2, 15),
            "specimen_source_id": specimen_source_id,
        },
    )
    specimen_id = int(specimen_record["specimen_id"])

    await create_observation(
        session,
        {
            "person_id": person_id,
            "observation_concept_id": 36716952,
            "value_as_concept_id": 44498902,
            "observation_event_id": specimen_id,
            "obs_event_field_concept_id": 1147049,
        },
    )

    await create_observation(
        session,
        {
            "person_id": person_id,
            "observation_concept_id": 4160340,
            "value_as_concept_id": 37164072,
            "observation_event_id": specimen_id,
            "obs_event_field_concept_id": 1147049,
        },
    )

    await create_observation(
        session,
        {
            "person_id": person_id,
            "observation_concept_id": 4154128,
            "value_as_concept_id": 40480027,
            "observation_event_id": specimen_id,
            "obs_event_field_concept_id": 1147049,
        },
    )

    await create_observation(
        session,
        {
            "person_id": person_id,
            "observation_concept_id": 37169821,
            "value_as_concept_id": 9177,
            "observation_event_id": specimen_id,
            "obs_event_field_concept_id": 1147049,
        },
    )

    await create_measurement(
        session,
        {
            "person_id": person_id,
            "measurement_concept_id": 4293617,
            "value_as_concept_id": 920001,
            "measurement_date": date(2023, 2, 16),
        },
    )

    await create_observation(
        session,
        {
            "person_id": person_id,
            "observation_concept_id": 4298494,
            "value_as_concept_id": 920002,
            "observation_event_id": specimen_id,
            "obs_event_field_concept_id": 1147049,
            "observation_date": date(2023, 2, 17),
        },
    )

    return person_id, specimen_id



async def test_get_biosamples(db_session):
    person_id, _ = await create_biosample_data(
        db_session,
        specimen_source_id="SPECIMEN_0001",
    )
    await db_session.flush()

    biosamples, status_code = await get_biosamples(person_id)

    assert status_code == 200
    assert len(biosamples) == 1

    biosample = biosamples[0]
    assert biosample.id == "SPECIMEN_0001"
    assert biosample.individual_id == str(person_id)

    assert biosample.sampled_tissue.id == "SNOMED:C57.8"
    assert (
        biosample.sampled_tissue.label == "Overlapping lesion of female genital organs"
    )

    assert biosample.taxonomy.id == "SNOMED:337915000"
    assert biosample.taxonomy.label == "Homo sapiens (organism)"

    assert biosample.time_of_collection is not None
    toc = biosample.time_of_collection.timestamp.ToDatetime().date()
    assert toc == date(2023, 2, 15)

    assert biosample.histological_diagnosis.id == "ICDO3:9726/3"
    assert (
        biosample.histological_diagnosis.label
        == "Primary cutaneous gamma-delta T-cell lymphoma"
    )

    assert biosample.tumor_grade.id == "SNOMED:1228845001"
    assert biosample.tumor_grade.label == "GX (AJCC)"

    assert biosample.sample_processing.id == "SNOMED:441652008"
    assert biosample.sample_storage.id == "SNOMED:74964007"

    assert len(biosample.pathological_tnm_finding) == 1
    assert biosample.pathological_tnm_finding[0].id == "LOINC:LA3624-9"
    assert biosample.pathological_tnm_finding[0].label == "T3"

    assert len(biosample.measurements) == 1
    assert biosample.measurements[0].assay.id == "LOINC:85319-2"
    assert biosample.measurements[0].value.ontology_class.id == "LOINC:LA6576-8"



async def test_get_biosamples_time_of_collection(
    db_session,
):
    """date 1800-01-01 should not populate time_of_collection."""

    person_id, _ = await create_biosample_data(
        db_session,
        specimen_source_id="SPECIMEN_0003",
    )

    await create_specimen(
        db_session,
        {
            "person_id": person_id,
            "specimen_concept_id": 0,
            "specimen_type_concept_id": 0,
            "anatomic_site_concept_id": 44497885,
            "specimen_date": date(1800, 1, 1),
            "specimen_source_id": "SPECIMEN_1800",
        },
    )
    await db_session.flush()

    biosamples, status_code = await get_biosamples(person_id)

    assert status_code == 200
    by_id = {b.id: b for b in biosamples}
    sentinel_toc = by_id["SPECIMEN_1800"].time_of_collection
    assert sentinel_toc is None or not sentinel_toc.HasField("timestamp")
