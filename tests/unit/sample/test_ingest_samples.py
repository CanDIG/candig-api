import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.ingest_helpers import ingest_samples
from src.daemon import detect_data_type


def make_donor(donor_id="DONOR_001", program_id="PROG_A"):
    return {
        "submitter_donor_id": donor_id,
        "program_id": program_id,
        "primary_diagnoses": [
            {
                "specimens": [
                    {
                        "submitter_specimen_id": "SPEC_001",
                        "sample_registrations": [{"submitter_sample_id": "SAMPLE_001"}],
                    }
                ]
            }
        ],
    }


def make_payload(*donors):
    return {"schema_class": "MoHSchemaV3", "donors": list(donors)}


def make_session(person_id=42, specimen_id=99):
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    def make_row(val):
        row = MagicMock()
        row.__getitem__ = lambda self, idx: val
        return row

    def make_result(row):
        r = MagicMock()
        r.fetchone = MagicMock(return_value=row)
        return r

    session.execute = AsyncMock(
        side_effect=[
            make_result(make_row(person_id)),
            make_result(make_row(specimen_id)),
        ]
    )
    return session


def session_gen(session):
    async def _gen():
        yield session

    return lambda: _gen()


class TestDetectDataType:
    def test_moh_schema_returns_samples(self):
        assert (
            detect_data_type({"schema_class": "MoHSchemaV3", "donors": []}) == "samples"
        )

    def test_non_moh_returns_omop(self):
        assert detect_data_type({"schema_class": "Other"}) == "omop"
        assert detect_data_type({}) == "omop"


class TestIngestSamplesSuccess:
    @pytest.mark.asyncio
    @patch("src.api.ingest_helpers.create_sample", new_callable=AsyncMock)
    @patch("src.api.ingest_helpers.get_db_session")
    async def test_single_sample_ingested(
        self, mock_get_db_session, mock_create_sample
    ):
        """Happy path: one donor → one sample ingested, commit called, no errors."""
        session = make_session()
        mock_get_db_session.side_effect = session_gen(session)

        ingested, errors, fails = await ingest_samples(
            make_payload(make_donor()), "queue_id_1", "TEST-SITE"
        )

        assert len(ingested) == 1
        assert errors == []
        assert fails == 0
        session.commit.assert_called_once()


class TestIngestSamplesDBFailures:
    @pytest.mark.asyncio
    @patch("src.api.ingest_helpers.get_db_session")
    async def test_person_not_found(self, mock_get_db_session):
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        no_row = MagicMock()
        no_row.fetchone = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=no_row)

        async def _gen():
            yield session

        mock_get_db_session.side_effect = lambda: _gen()

        ingested, errors, fails = await ingest_samples(
            make_payload(make_donor()), "q", "TEST"
        )
        assert (
            fails == 1
            and ingested == []
            and any("Person Not Found" in e for e in errors)
        )

    @pytest.mark.asyncio
    @patch("src.api.ingest_helpers.create_sample", new_callable=AsyncMock)
    @patch("src.api.ingest_helpers.get_db_session")
    async def test_rollback_on_failure(self, mock_get_db_session, mock_create_sample):
        session = make_session()
        mock_get_db_session.side_effect = session_gen(session)
        mock_create_sample.side_effect = Exception("oops")

        await ingest_samples(make_payload(make_donor()), "q", "TEST")
        session.rollback.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.api.ingest_helpers.create_sample", new_callable=AsyncMock)
    @patch("src.api.ingest_helpers.get_db_session")
    async def test_duplicate_409_skipped(self, mock_get_db_session, mock_create_sample):
        session = make_session()
        mock_get_db_session.side_effect = session_gen(session)
        mock_create_sample.side_effect = Exception("409 Conflict: already exists")

        ingested, errors, fails = await ingest_samples(
            make_payload(make_donor()), "q", "TEST"
        )
        assert fails == 1 and any("Already exists" in e for e in errors)
