from unittest.mock import MagicMock, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.person_operations import get_by_id

# --- Test authorized user gets full person details ---


@pytest.mark.asyncio
async def test_get_by_id_authorized_user_person_exists(
    mock_db_session_factory, sample_persons, admin_user
):
    """Test admin user gets full person details for person_id=1 in dataset1"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 1
    target_person = sample_persons[0]  # PERSON_001

    mock_result = MagicMock()
    mock_result.fetchone.return_value = target_person
    mock_session = mock_db_session_factory(result=mock_result)

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        # Check if dataset1 is in admin's authorized datasets and has read permission
        mock_auth.return_value = dataset_id in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get(dataset_id, {}).get("read", False)

        # Act
        response = await get_by_id(dataset_id=dataset_id, id=person_id)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert isinstance(result, dict)
        assert result["person_id"] == 1
        assert result["person_source_value"] == "PERSON_001"
        assert "gender_concept_id" in result
        assert "year_of_birth" in result
        assert "race_concept_id" in result
        assert "ethnicity_concept_id" in result


@pytest.mark.asyncio
async def test_get_by_id_curator_user_person_exists(
    mock_db_session_factory, sample_persons, curator_user
):
    """Test curator user gets full person details for person_id=2 in dataset1"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 2
    target_person = sample_persons[1]  # PERSON_002

    mock_result = MagicMock()
    mock_result.fetchone.return_value = target_person
    mock_session = mock_db_session_factory(result=mock_result)

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        # Check if dataset1 is in curator's authorized datasets and has read permission
        mock_auth.return_value = dataset_id in curator_user[
            "authorized_datasets"
        ] and curator_user["permissions"].get(dataset_id, {}).get("read", False)

        # Act
        response = await get_by_id(dataset_id=dataset_id, id=person_id)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert result["person_id"] == 2
        assert result["person_source_value"] == "PERSON_002"


# --- Test unauthorized user gets 403 ---


@pytest.mark.asyncio
async def test_get_by_id_unauthorized_user(mock_db_session_factory, user2):
    """Test user2 (no access) gets 403 error"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 1

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        # Check if dataset1 is in user2's authorized datasets
        mock_auth.return_value = dataset_id in user2["authorized_datasets"] and user2[
            "permissions"
        ].get(dataset_id, {}).get("read", False)

        # Act
        response = await get_by_id(dataset_id=dataset_id, id=person_id)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]
        assert dataset_id in result["error"]


@pytest.mark.asyncio
async def test_get_by_id_user1_unauthorized_for_dataset2(
    mock_db_session_factory, user1
):
    """Test user1 (only has access to dataset1) gets 403 for dataset2"""
    # Arrange
    dataset_id = "dataset2"
    person_id = 1

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        # Check if dataset2 is in user1's authorized datasets
        mock_auth.return_value = dataset_id in user1["authorized_datasets"] and user1[
            "permissions"
        ].get(dataset_id, {}).get("read", False)

        # Act
        response = await get_by_id(dataset_id=dataset_id, id=person_id)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]


# --- Test person not found returns 404 ---


@pytest.mark.asyncio
async def test_get_by_id_person_not_found(mock_db_session_factory, admin_user):
    """Test getting a person that does not exist returns 404"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 99999  # Non-existent person

    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session = mock_db_session_factory(result=mock_result)

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get(dataset_id, {}).get("read", False)

        # Act & Assert
        with pytest.raises(ProblemException) as exc_info:
            await get_by_id(dataset_id=dataset_id, id=person_id)

        assert exc_info.value.status == 404
        assert exc_info.value.title == "Not Found"
        assert exc_info.value.detail is not None
        assert str(person_id) in exc_info.value.detail
        assert dataset_id in exc_info.value.detail
