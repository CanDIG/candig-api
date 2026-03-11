from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.dataset_operations import list_samples


def make_sample_record(sample_id, person_id, specimen_id, sample_info):
    record = MagicMock()
    record.sample_id = sample_id
    record.person_id = person_id
    record.specimen_id = specimen_id
    record.sample_info = sample_info
    return record


def make_db_session(records=None, side_effect=None):
    mock_result = MagicMock()
    mock_result.all.return_value = records or []

    session = AsyncMock()
    if side_effect:
        session.execute.side_effect = side_effect
    else:
        session.execute.return_value = mock_result
    return session


@pytest.mark.asyncio
async def test_list_samples_authorized_user_returns_samples():
    """Authorized user retrieves all samples for a dataset"""
    dataset_id = "dataset1"
    records = [
        make_sample_record("sample1", "person1", "specimen1", {"tissue": "blood"}),
        make_sample_record("sample2", "person2", "specimen2", {"tissue": "tissue"}),
    ]
    session = make_db_session(records)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [session]
        mock_auth.return_value = True

        response = await list_samples(dataset_id)
        assert response is not None
        result, status_code = response

        assert isinstance(result, list)
        assert status_code == 200
        assert len(result) == 2
        assert result[0]["sample_id"] == "sample1"
        assert result[0]["dataset_id"] == dataset_id
        assert result[0]["person_id"] == "person1"
        assert result[0]["specimen_id"] == "specimen1"
        assert result[0]["sample_info"] == {"tissue": "blood"}
        assert result[1]["sample_id"] == "sample2"
        session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_list_samples_returns_empty_list_when_no_samples():
    """Authorized user gets an empty list when dataset has no samples"""
    dataset_id = "dataset1"
    session = make_db_session(records=[])

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [session]
        mock_auth.return_value = True

        response = await list_samples(dataset_id)
        assert response is not None
        result, status_code = response

        assert status_code == 200
        assert result == []


@pytest.mark.asyncio
async def test_list_samples_unauthorized_user_returns_403():
    """Unauthorized user receives a 403 response"""
    dataset_id = "dataset1"

    with patch("src.api.dataset_operations.is_action_allowed") as mock_auth:
        mock_auth.return_value = False

        response = await list_samples(dataset_id)
        assert response is not None
        result, status_code = response

        assert isinstance(result, dict)
        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]
        assert dataset_id in result["error"]
