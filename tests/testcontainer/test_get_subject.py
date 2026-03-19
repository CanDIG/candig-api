from datetime import date

import pytest

from src.database.insert_operations import (
    create_condition_occurrence,
    create_death,
    create_episode,
    create_episode_event,
    create_observation,
    create_person,
)
from tests.testcontainer.conftest import insert_concept
from src.api.phenopacket_operations import get_subject

async def insert_person(
    session, gender_concept_id=8507, person_source_value="DONOR_TEST"
):
    person = await create_person(
        session,
        {
            "gender_concept_id": gender_concept_id,
            "year_of_birth": 1990,
            "month_of_birth": 3,
            "day_of_birth": 15,
            "person_source_value": person_source_value,
        },
    )
    # Insert gender concepts so ontology lookup works
    await insert_concept(session, 8507, "MALE", vocabulary_id="Gender", code="M")
    await insert_concept(session, 8532, "FEMALE", vocabulary_id="Gender", code="F")
    await insert_concept(session, 8521, "OTHER_SEX", vocabulary_id="Gender", code="O")
    await session.flush()
    return person["person_id"], person_source_value



async def test_get_subject_male(db_session):
    """get_subject correctly maps sex_concept_id=8507 to MALE"""

    person_id, person_source_value = await insert_person(db_session)

    subject, status_code = await get_subject(person_id)

    assert status_code == 200
    assert subject.id == str(person_id)
    assert subject.alternate_ids == [person_source_value]
    assert subject.sex == 2  # MALE



async def test_get_subject_female(db_session):
    """get_subject correctly maps sex_concept_id=8532 to FEMALE."""

    person_id, _ = await insert_person(db_session, gender_concept_id=8532)

    subject, status_code = await get_subject(person_id)

    assert status_code == 200
    assert subject.sex == 1  # FEMALE



async def test_get_subject_date_of_birth(db_session):
    """get_subject constructs proper date_of_birth from year/month/day."""
    from google.protobuf.timestamp_pb2 import Timestamp

    person_id, _ = await insert_person(db_session)

    subject, status_code = await get_subject(person_id)

    assert status_code == 200
    assert isinstance(subject.date_of_birth, Timestamp)
    dob = subject.date_of_birth.ToDatetime()
    assert dob.year == 1990
    assert dob.month == 3
    assert dob.day == 15



async def test_get_subject_with_death(db_session):
    """get_subject returns DECEASED status when death record exists."""

    person_id, _ = await insert_person(db_session)
    # Insert a cause-of-death concept
    await insert_concept(
        session=db_session,
        concept_id=443392,
        name="Malignant neoplastic disease",
        vocabulary_id="SNOMED",
        code="363346000",
    )
    await create_death(
        db_session,
        {
            "person_id": person_id,
            "death_date": date(2023, 6, 15),
            "cause_concept_id": 443392,
        },
    )
    await db_session.flush()

    subject, status_code = await get_subject(person_id)

    assert status_code == 200
    assert subject.vital_status is not None
    # VitalStatus.DECEASED = 2
    assert subject.vital_status.status == 2



async def test_get_subject_survival_time(db_session):
    """get_subject calculates survival_time_in_days from disease onset to death."""

    person_id, _ = await insert_person(db_session)

    # Cause-of-death concept: 443392 -> SNOMED:363346000 "Malignant neoplastic disease"
    await insert_concept(
        db_session,
        concept_id=443392,
        name="Malignant neoplastic disease",
        vocabulary_id="SNOMED",
        code="363346000",
    )

    # Disease First Occurrence episode (episode_concept_id=32528)
    episode = await create_episode(
        db_session,
        {"person_id": person_id, "episode_concept_id": 32528},
    )

    # condition_occurrence with onset date 2023-01-01
    condition = await create_condition_occurrence(
        db_session,
        {
            "person_id": person_id,
            "condition_concept_id": 999999,
            "condition_start_date": date(2023, 1, 1),
        },
    )
    await insert_concept(
        db_session, 999999, "Some Disease", vocabulary_id="SNOMED", code="12345"
    )

    # Link episode -> condition_occurrence via episode_event (field_concept_id=1147127)
    await create_episode_event(
        db_session,
        {
            "episode_id": episode["episode_id"],
            "event_id": condition["condition_occurrence_id"],
            "episode_event_field_concept_id": 1147127,
        },
    )

    # Death date 2023-01-10, cause = Malignant neoplastic disease (443392)
    await create_death(
        db_session,
        {
            "person_id": person_id,
            "death_date": date(2023, 1, 10),
            "cause_concept_id": 443392,
        },
    )
    await db_session.flush()

    subject, status_code = await get_subject(person_id)

    assert status_code == 200
    assert subject.vital_status is not None
    assert subject.vital_status.cause_of_death.id == "SNOMED:363346000"
    assert subject.vital_status.cause_of_death.label == "Malignant neoplastic disease"
    # Death (2023-01-10) - Onset (2023-01-01) = 9 days
    assert subject.vital_status.survival_time_in_days == 9



async def test_get_subject_with_gender_observation(db_session):

    person_id, _ = await insert_person(db_session)

    # concept_id 765761 -> SNOMED:446141000124107 "Identifies as female gender"
    gender_value_concept = 765761
    await insert_concept(
        db_session,
        gender_value_concept,
        "Identifies as female gender",
        vocabulary_id="SNOMED",
        code="446141000124107",
    )

    # Insert gender-identity observation (observation_concept_id=37171290)
    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 37171290,
            "value_as_concept_id": gender_value_concept,
        },
    )
    await db_session.flush()

    subject, status_code = await get_subject(person_id)

    assert status_code == 200
    assert subject.gender is not None
    assert subject.gender.id == "SNOMED:446141000124107"
    assert subject.gender.label == "Identifies as female gender"
