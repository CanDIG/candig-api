from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.person_operations import create


@pytest.mark.asyncio
async def test_create_person_with_required_fields_only(admin_user):
    """Test creating a person with only required fields - authorized user"""
    # Arrange
    dataset_id = "dataset1"
    body = {"gender_concept_id": 8507, "race_concept_id": 0, "ethnicity_concept_id": 0}

    mock_session = AsyncMock()

    # Mock dataset check result
    mock_dataset_result = MagicMock()
    mock_dataset_result.fetchone.return_value = MagicMock(id="dataset1")

    # Mock person insert result
    mock_person_result = MagicMock()
    mock_person_row = MagicMock()
    mock_person_row.person_id = 12345
    mock_person_row.gender_concept_id = 8507
    mock_person_row.year_of_birth = None
    mock_person_row.month_of_birth = None
    mock_person_row.day_of_birth = None
    mock_person_row.birth_datetime = None
    mock_person_row.race_concept_id = 0
    mock_person_row.ethnicity_concept_id = 0
    mock_person_row.location_id = None
    mock_person_row.provider_id = None
    mock_person_row.care_site_id = None
    mock_person_row.person_source_value = None
    mock_person_row.gender_source_value = None
    mock_person_row.gender_source_concept_id = None
    mock_person_row.race_source_value = None
    mock_person_row.race_source_concept_id = None
    mock_person_row.ethnicity_source_value = None
    mock_person_row.ethnicity_source_concept_id = None
    mock_person_result.fetchone.return_value = mock_person_row

    # Setup execute: dataset check, person insert, link insert
    execute_results = [mock_dataset_result, mock_person_result, None]
    mock_session.execute = AsyncMock(side_effect=execute_results)
    mock_session.commit = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get(dataset_id, {}).get("write", False)

        # Act
        response = await create(dataset_id=dataset_id, body=body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 201
        assert isinstance(result, dict)
        assert result["person_id"] == 12345
        assert result["gender_concept_id"] == 8507
        assert result["race_concept_id"] == 0
        assert result["ethnicity_concept_id"] == 0
        assert mock_session.execute.call_count == 3
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_person_with_all_fields(curator_user):
    """Test creating a person with all optional fields"""
    # Arrange
    dataset_id = "dataset1"
    body = {
        "person_source_value": "PERSON_COMPLETE",
        "gender_concept_id": 8507,
        "year_of_birth": 1990,
        "month_of_birth": 5,
        "day_of_birth": 15,
        "birth_datetime": "1990-05-15T10:30:00Z",
        "race_concept_id": 8515,
        "ethnicity_concept_id": 38003563,
        "location_id": 1,
        "provider_id": 100,
        "care_site_id": 50,
        "gender_source_value": "Male",
        "gender_source_concept_id": 0,
        "race_source_value": "Asian",
        "race_source_concept_id": 0,
        "ethnicity_source_value": "Not Hispanic",
        "ethnicity_source_concept_id": 0,
    }

    mock_session = AsyncMock()

    # Mock dataset check result
    mock_dataset_result = MagicMock()
    mock_dataset_result.fetchone.return_value = MagicMock(id="dataset1")

    # Mock person insert result
    from datetime import datetime

    mock_person_result = MagicMock()
    mock_person_row = MagicMock()
    mock_person_row.person_id = 99999
    mock_person_row.gender_concept_id = 8507
    mock_person_row.year_of_birth = 1990
    mock_person_row.month_of_birth = 5
    mock_person_row.day_of_birth = 15
    mock_person_row.birth_datetime = datetime.fromisoformat("1990-05-15T10:30:00+00:00")
    mock_person_row.race_concept_id = 8515
    mock_person_row.ethnicity_concept_id = 38003563
    mock_person_row.location_id = 1
    mock_person_row.provider_id = 100
    mock_person_row.care_site_id = 50
    mock_person_row.person_source_value = "PERSON_COMPLETE"
    mock_person_row.gender_source_value = "Male"
    mock_person_row.gender_source_concept_id = 0
    mock_person_row.race_source_value = "Asian"
    mock_person_row.race_source_concept_id = 0
    mock_person_row.ethnicity_source_value = "Not Hispanic"
    mock_person_row.ethnicity_source_concept_id = 0
    mock_person_result.fetchone.return_value = mock_person_row

    # Setup execute: dataset check, person insert, link insert
    execute_results = [mock_dataset_result, mock_person_result, None]
    mock_session.execute = AsyncMock(side_effect=execute_results)
    mock_session.commit = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in curator_user[
            "authorized_datasets"
        ] and curator_user["permissions"].get(dataset_id, {}).get("write", False)

        # Act
        response = await create(dataset_id=dataset_id, body=body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 201
        assert isinstance(result, dict)
        assert result["person_id"] == 99999
        assert result["person_source_value"] == "PERSON_COMPLETE"
        assert result["gender_concept_id"] == 8507
        assert result["year_of_birth"] == 1990
        assert result["month_of_birth"] == 5
        assert result["day_of_birth"] == 15
        assert result["birth_datetime"] == "1990-05-15T10:30:00+00:00"
        assert result["race_concept_id"] == 8515
        assert result["ethnicity_concept_id"] == 38003563
        assert result["location_id"] == 1
        assert result["provider_id"] == 100
        assert result["care_site_id"] == 50
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_person_unauthorized_user(user2):
    """Test creating a person with unauthorized user returns 403"""
    # Arrange
    dataset_id = "dataset1"
    body = {"gender_concept_id": 8507, "race_concept_id": 0, "ethnicity_concept_id": 0}

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        mock_auth.return_value = dataset_id in user2["authorized_datasets"] and user2[
            "permissions"
        ].get(dataset_id, {}).get("write", False)

        # Act
        response = await create(dataset_id=dataset_id, body=body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert isinstance(result, dict)
        assert "not authorized" in result["error"]
        assert dataset_id in result["error"]


@pytest.mark.asyncio
async def test_create_person_readonly_user(user1):
    """Test creating a person with read-only user returns 403"""
    # Arrange
    dataset_id = "dataset1"
    body = {"gender_concept_id": 8507, "race_concept_id": 0, "ethnicity_concept_id": 0}

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        # user1 has read access to dataset1 but not write
        mock_auth.return_value = (
            user1["permissions"].get(dataset_id, {}).get("write", False)
        )

        # Act
        response = await create(dataset_id=dataset_id, body=body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert isinstance(result, dict)
        assert "not authorized" in result["error"]


@pytest.mark.asyncio
async def test_create_person_missing_required_field():
    """Test creating a person without required field raises 400"""
    # Arrange
    dataset_id = "dataset1"
    body = {
        "gender_concept_id": 8507,
        # Missing race_concept_id and ethnicity_concept_id
    }

    mock_session = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        # Act & Assert
        with pytest.raises(ProblemException) as exc_info:
            await create(dataset_id=dataset_id, body=body)

        assert exc_info.value.status == 400
        assert exc_info.value.title == "Bad Request"
        assert exc_info.value.detail is not None
        assert "Missing required field" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_person_dataset_not_found():
    """Test creating a person in non-existent dataset returns 404"""
    # Arrange
    dataset_id = "nonexistent_dataset"
    body = {"gender_concept_id": 8507, "race_concept_id": 0, "ethnicity_concept_id": 0}

    mock_session = AsyncMock()

    # Mock dataset check result - dataset not found
    mock_dataset_result = MagicMock()
    mock_dataset_result.fetchone.return_value = None

    mock_session.execute = AsyncMock(return_value=mock_dataset_result)
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        # Act & Assert
        with pytest.raises(ProblemException) as exc_info:
            await create(dataset_id=dataset_id, body=body)

        assert exc_info.value.status == 404
        assert exc_info.value.title == "Not Found"
        assert exc_info.value.detail is not None
        assert dataset_id in exc_info.value.detail
        mock_session.rollback.assert_called_once()
