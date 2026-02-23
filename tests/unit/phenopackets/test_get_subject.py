from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.phenopacket_operations import get_subject


def make_mock_session(mock_row):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def session_gen():
        yield mock_session

    return session_gen()


def make_mock_row(overrides=None):
    """
    Build a default mock row representing a person in OMOP.
    Value from the phenopackets_mapping examples
    """
    row = MagicMock()
    row.id = 1
    row.alternate_ids = "DONOR_001"
    row.sex_concept_id = 8507           
    row.year_of_birth = 1990         
    row.month_of_birth = 3
    row.day_of_birth = 10
    row.gender_concept_id = 123456    
    row.time_of_death = None        
    row.cause_of_death_concept_id = None 
    row.disease_first_occurrence_date = None 
    if overrides:
        for k, v in overrides.items():
            setattr(row, k, v)
    return row

# ---------------------------------------------------------------------------
# 1.3  date_of_birth
# ---------------------------------------------------------------------------

DATE_OF_BIRTH_CASES = [
    pytest.param(
        {},  # defaults: 1990-03-10
        1990, 3, 10, False,
        id="full date 1990-03-10",
    ),
    pytest.param(
        {"year_of_birth": 1990, "month_of_birth": None, "day_of_birth": None},
        1990, 1, 1, False,
        id="NULL month and day default to 01",
    ),
    pytest.param(
        {"year_of_birth": 1990, "month_of_birth": 11, "day_of_birth": None},
        1990, 11, 1, False,
        id="NULL day defaults to 01",
    ),
    pytest.param(
        {"year_of_birth": None, "month_of_birth": 3, "day_of_birth": 10},
        None, None, None, True,
        id="NULL year -> date_of_birth must be unset",
    ),
    pytest.param(
        {"year_of_birth": 1800, "month_of_birth": 1, "day_of_birth": 1},
        None, None, None, True,
        id="year=1800 (OMOP sentinel) -> date_of_birth must be unset",
    ),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,exp_year,exp_month,exp_day,expect_unset", DATE_OF_BIRTH_CASES)
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
async def test_date_of_birth(
    mock_get_ontologies, mock_get_db_session,
    overrides, exp_year, exp_month, exp_day, expect_unset,
):
    from google.protobuf.timestamp_pb2 import Timestamp

    mock_get_ontologies.return_value = {}
    row = make_mock_row(overrides)
    mock_get_db_session.return_value = make_mock_session(row)

    subject, status_code = await get_subject(1)

    assert status_code == 200

    if expect_unset:
        assert (
            subject.date_of_birth is None or subject.date_of_birth.seconds == 0
        ), "date_of_birth must be unset"
    else:
        assert isinstance(subject.date_of_birth, Timestamp), (
            "date_of_birth must be a Timestamp"
        )
        dob = subject.date_of_birth.ToDatetime()
        assert dob.year  == exp_year,  f"expected year  {exp_year}  got {dob.year}"
        assert dob.month == exp_month, f"expected month {exp_month} got {dob.month}"
        assert dob.day   == exp_day,   f"expected day   {exp_day}   got {dob.day}"


# ---------------------------------------------------------------------------
# 1.4  sex – OMOP concept_id mapping
# ---------------------------------------------------------------------------

SEX_CONCEPT_ID_CASES = [
    pytest.param(
        {"sex_concept_id": 8507},
        2,  # Sex.MALE
        id="concept_id=8507 -> MALE",
    ),
    pytest.param(
        {"sex_concept_id": 8532},
        1,  # Sex.FEMALE
        id="concept_id=8532 -> FEMALE",
    ),
    pytest.param(
        {"sex_concept_id": 8521},
        3,  # Sex.OTHER_SEX
        id="concept_id=8521 -> OTHER_SEX",
    ),
    pytest.param(
        {"sex_concept_id": None},
        0,  # Sex.UNKNOWN_SEX
        id="concept_id=None -> UNKNOWN_SEX",
    ),
    pytest.param(
        {"sex_concept_id": 9999},
        0,  # Sex.UNKNOWN_SEX
        id="concept_id=9999 (unmapped) -> UNKNOWN_SEX",
    ),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,exp_sex", SEX_CONCEPT_ID_CASES)
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
async def test_sex_concept_id(
    mock_get_ontologies, mock_get_db_session,
    overrides, exp_sex,
):
    mock_get_ontologies.return_value = {}
    row = make_mock_row(overrides)
    mock_get_db_session.return_value = make_mock_session(row)

    subject, status_code = await get_subject(1)

    assert status_code == 200

    assert subject.sex == exp_sex, (
        f"OMOP sex_concept_id={overrides.get('sex_concept_id')} "
        f"must map to sex enum value {exp_sex}"
    )

# ---------------------------------------------------------------------------
# 1.7.1  vital_status.status
# ---------------------------------------------------------------------------

VITAL_STATUS_CASES = [
    pytest.param(
        {"time_of_death": None},
        "UNKNOWN_STATUS",
        id="NULL death_date -> UNKNOWN_STATUS",
    ),
    pytest.param(
        {"time_of_death": date(2023, 1, 10)},
        "DECEASED",
        id="death_date present -> DECEASED",
    ),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,exp_status", VITAL_STATUS_CASES)
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
async def test_vital_status_status(
    mock_get_ontologies, mock_get_db_session,
    overrides, exp_status,
):
    """
    When time_of_death is NULL -> UNKNOWN_STATUS.
    When time_of_death is present -> DECEASED.
    """
    from phenopackets import VitalStatus

    STATUS_MAP = {
        "UNKNOWN_STATUS": VitalStatus.UNKNOWN_STATUS,
        "DECEASED": VitalStatus.DECEASED,
    }

    mock_get_ontologies.return_value = {}
    row = make_mock_row(overrides)
    mock_get_db_session.return_value = make_mock_session(row)

    subject, status_code = await get_subject(1)

    assert status_code == 200
    assert subject.vital_status is not None, "vital_status must be set"
    assert subject.vital_status.status == STATUS_MAP[exp_status], (
        f"time_of_death={overrides.get('time_of_death')} "
        f"must map to status {exp_status}"
    )


# ---------------------------------------------------------------------------
# 1.7.4  survival_time_in_days – death minus disease first occurrence
# ---------------------------------------------------------------------------

SURVIVAL_TIME_CASES = [
    pytest.param(
        {
            "time_of_death": date(2023, 1, 10),
            "disease_first_occurrence_date": date(2023, 1, 1),
        },
        9,
        id="Death(2023-01-10) - Onset(2023-01-01) -> 9 days",
    ),
    pytest.param(
        {
            "time_of_death": date(2023, 6, 1),
            "disease_first_occurrence_date": date(2023, 1, 1),
        },
        151,
        id="Death(2023-06-01) - Onset(2023-01-01) -> 151 days",
    ),
    pytest.param(
        {
            "time_of_death": date(2023, 1, 1),
            "disease_first_occurrence_date": date(2023, 1, 1),
        },
        0,
        id="Death == Onset -> 0 days",
    ),
    pytest.param(
        {
            "time_of_death": date(2023, 1, 10),
            "disease_first_occurrence_date": None,
        },
        None,
        id="NULL disease_first_occurrence_date -> survival_time_in_days unset",
    ),
    pytest.param(
        {
            "time_of_death": None,
            "disease_first_occurrence_date": date(2023, 1, 1),
        },
        None,
        id="NULL time_of_death -> survival_time_in_days unset",
    ),
    pytest.param(
        {
            "time_of_death": None,
            "disease_first_occurrence_date": None,
        },
        None,
        id="Both NULL -> survival_time_in_days unset",
    ),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,exp_days", SURVIVAL_TIME_CASES)
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
async def test_survival_time_in_days(
    mock_get_ontologies, mock_get_db_session,
    overrides, exp_days,
):
    """
    survival_time_in_days = time_of_death - disease_first_occurrence_date.
    If either value is NULL, survival_time_in_days must be unset (0 or None).
    """

    mock_get_ontologies.return_value = {}
    row = make_mock_row(overrides)
    mock_get_db_session.return_value = make_mock_session(row)

    subject, status_code = await get_subject(1)

    assert status_code == 200
    assert subject.vital_status is not None, "vital_status must be set"

    if exp_days is None:
        assert subject.vital_status.survival_time_in_days == 0, (
            "survival_time_in_days must be unset (0) when death or onset date is missing"
        )
    else:
        assert subject.vital_status.survival_time_in_days == exp_days, (
            f"expected survival_time_in_days={exp_days}, "
            f"got {subject.vital_status.survival_time_in_days}"
        )