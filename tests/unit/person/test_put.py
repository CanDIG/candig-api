from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.person_operations import put


@pytest.mark.asyncio
async def test_put_person_with_required_fields_only(admin_user, sample_persons):
    """Test updating a person with only required fields - authorized user"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 1
    body = {
        "person_id": person_id,
        "gender_concept_id": 8532,
        "race_concept_id": 8515,
        "ethnicity_concept_id": 38003563,
    }

    mock_session = AsyncMock()

    # Mock dataset check result
    mock_dataset_result = MagicMock()
    mock_dataset_result.fetchone.return_value = MagicMock(id=dataset_id)

    # Mock person exists check result
    mock_person_exists_result = MagicMock()
    mock_person_exists_result.fetchone.return_value = MagicMock(person_id=person_id)

    # Mock person update result
    mock_update_result = MagicMock()
    mock_person_row = MagicMock()
    mock_person_row.person_id = person_id
    mock_person_row.gender_concept_id = 8532
    mock_person_row.year_of_birth = None
    mock_person_row.month_of_birth = None
    mock_person_row.day_of_birth = None
    mock_person_row.birth_datetime = None
    mock_person_row.race_concept_id = 8515
    mock_person_row.ethnicity_concept_id = 38003563
    mock_person_row.location_id = None
    mock_person_row.provider_id = None
    mock_person_row.care_site_id = None
    mock_person_row.person_source_value = "PERSON_001"
    mock_person_row.gender_source_value = None
    mock_person_row.gender_source_concept_id = None
    mock_person_row.race_source_value = None
    mock_person_row.race_source_concept_id = None
    mock_person_row.ethnicity_source_value = None
    mock_person_row.ethnicity_source_concept_id = None
    mock_update_result.fetchone.return_value = mock_person_row

    # Setup execute: dataset check, person exists check, person update
    execute_results = [
        mock_dataset_result,
        mock_person_exists_result,
        mock_update_result,
    ]
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
        response = await put(dataset_id=dataset_id, id=person_id, body=body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert isinstance(result, dict)
        assert result["person_id"] == person_id
        assert result["gender_concept_id"] == 8532
        assert result["race_concept_id"] == 8515
        assert result["ethnicity_concept_id"] == 38003563
        assert mock_session.execute.call_count == 3
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_put_person_with_all_fields(curator_user):
    """Test updating a person with all optional fields"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 2
    body = {
        "person_id": person_id,
        "person_source_value": "PERSON_UPDATED",
        "gender_concept_id": 8507,
        "year_of_birth": 1985,
        "month_of_birth": 3,
        "day_of_birth": 15,
        "birth_datetime": "1985-03-15T10:30:00Z",
        "race_concept_id": 8515,
        "ethnicity_concept_id": 38003563,
        "location_id": 2,
        "provider_id": 200,
        "care_site_id": 75,
        "gender_source_value": "Female",
        "gender_source_concept_id": 0,
        "race_source_value": "Asian",
        "race_source_concept_id": 0,
        "ethnicity_source_value": "Not Hispanic",
        "ethnicity_source_concept_id": 0,
    }

    mock_session = AsyncMock()

    # Mock dataset check result
    mock_dataset_result = MagicMock()
    mock_dataset_result.fetchone.return_value = MagicMock(id=dataset_id)

    # Mock person exists check result
    mock_person_exists_result = MagicMock()
    mock_person_exists_result.fetchone.return_value = MagicMock(person_id=person_id)

    # Mock person update result with datetime
    from datetime import datetime

    mock_update_result = MagicMock()
    mock_person_row = MagicMock()
    mock_person_row.person_id = person_id
    mock_person_row.gender_concept_id = 8507
    mock_person_row.year_of_birth = 1985
    mock_person_row.month_of_birth = 3
    mock_person_row.day_of_birth = 15
    mock_person_row.birth_datetime = datetime(1985, 3, 15, 10, 30, 0)
    mock_person_row.race_concept_id = 8515
    mock_person_row.ethnicity_concept_id = 38003563
    mock_person_row.location_id = 2
    mock_person_row.provider_id = 200
    mock_person_row.care_site_id = 75
    mock_person_row.person_source_value = "PERSON_UPDATED"
    mock_person_row.gender_source_value = "Female"
    mock_person_row.gender_source_concept_id = 0
    mock_person_row.race_source_value = "Asian"
    mock_person_row.race_source_concept_id = 0
    mock_person_row.ethnicity_source_value = "Not Hispanic"
    mock_person_row.ethnicity_source_concept_id = 0
    mock_update_result.fetchone.return_value = mock_person_row

    # Setup execute: dataset check, person exists check, person update
    execute_results = [
        mock_dataset_result,
        mock_person_exists_result,
        mock_update_result,
    ]
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
        response = await put(dataset_id=dataset_id, id=person_id, body=body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert result["person_id"] == person_id
        assert result["person_source_value"] == "PERSON_UPDATED"
        assert result["year_of_birth"] == 1985
        assert result["month_of_birth"] == 3
        assert result["day_of_birth"] == 15
        assert result["birth_datetime"] == "1985-03-15T10:30:00"
        assert result["location_id"] == 2
        assert result["provider_id"] == 200
        assert result["care_site_id"] == 75
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_put_person_unauthorized_user(user2):
    """Test unauthorized user gets 403 error"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 1
    body = {
        "person_id": person_id,
        "gender_concept_id": 8507,
        "race_concept_id": 0,
        "ethnicity_concept_id": 0,
    }

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        mock_auth.return_value = dataset_id in user2["authorized_datasets"] and user2[
            "permissions"
        ].get(dataset_id, {}).get("write", False)

        # Act
        response = await put(dataset_id=dataset_id, id=person_id, body=body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]


@pytest.mark.asyncio
async def test_put_person_dataset_not_found(admin_user):
    """Test dataset not found returns 404"""
    # Arrange
    dataset_id = "nonexistent"
    person_id = 1
    body = {
        "person_id": person_id,
        "gender_concept_id": 8507,
        "race_concept_id": 0,
        "ethnicity_concept_id": 0,
    }

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
            await put(dataset_id=dataset_id, id=person_id, body=body)

        assert exc_info.value.status == 404
        assert "not found" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_put_person_missing_required_field(admin_user):
    """Test missing required field returns 400"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 1
    body = {
        "person_id": person_id,
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
            await put(dataset_id=dataset_id, id=person_id, body=body)

        assert exc_info.value.status == 400
        assert exc_info.value.detail is not None
        assert "Missing required field" in exc_info.value.detail


@pytest.mark.asyncio
async def test_put_person_id_mismatch(admin_user):
    """Test URL ID not matching body person_id returns 400"""
    # Arrange
    dataset_id = "dataset1"
    url_person_id = 1
    body_person_id = 2
    body = {
        "person_id": body_person_id,
        "gender_concept_id": 8507,
        "race_concept_id": 0,
        "ethnicity_concept_id": 0,
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
            await put(dataset_id=dataset_id, id=url_person_id, body=body)

        assert exc_info.value.status == 400
        assert exc_info.value.detail is not None
        assert "does not match" in exc_info.value.detail


@pytest.mark.asyncio
async def test_put_person_read_only_user(user1):
    """Test user with read-only permission gets 403"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 1
    body = {
        "person_id": person_id,
        "gender_concept_id": 8507,
        "race_concept_id": 0,
        "ethnicity_concept_id": 0,
    }

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        # user1 has read permission but not write permission
        mock_auth.return_value = dataset_id in user1["authorized_datasets"] and user1[
            "permissions"
        ].get(dataset_id, {}).get("write", False)

        # Act
        response = await put(dataset_id=dataset_id, id=person_id, body=body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]
