from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.person_operations import delete


@pytest.mark.asyncio
async def test_delete_person_success(
    mock_db_session_factory, admin_user, sample_persons
):
    """Test successfully deleting a person with authorized user"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 1
    target_person = sample_persons[0]  # PERSON_001

    # Mock person exists check
    mock_person_exists = MagicMock()
    mock_person_exists.fetchone.return_value = MagicMock(
        person_id=target_person.person_id
    )

    # Mock deletion results (person_in_dataset delete, person delete)
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_person_exists, None, None])
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get(dataset_id, {}).get("write", False)

        # Act
        response = await delete(dataset_id=dataset_id, id=str(person_id))
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert isinstance(result, dict)
        assert "message" in result
        assert str(person_id) in result["message"]
        assert "deleted successfully" in result["message"]
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_person_unauthorized_user(mock_db_session_factory, user2):
    """Test unauthorized user returns 403"""
    # Arrange
    dataset_id = "dataset1"
    person_id = "1"

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        mock_auth.return_value = dataset_id in user2["authorized_datasets"] and user2[
            "permissions"
        ].get(dataset_id, {}).get("write", False)

        # Act
        response = await delete(dataset_id=dataset_id, id=person_id)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert isinstance(result, dict)
        assert "error" in result
        assert "not authorized" in result["error"]
        assert dataset_id in result["error"]


@pytest.mark.asyncio
async def test_delete_person_not_found(mock_db_session_factory, admin_user):
    """Test person not found returns 404"""
    # Arrange
    dataset_id = "dataset1"
    person_id = "999"

    # Mock person doesn't exist
    mock_person_not_exists = MagicMock()
    mock_person_not_exists.fetchone.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_person_not_exists)
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get(dataset_id, {}).get("write", False)

        # Act & Assert
        with pytest.raises(ProblemException) as exc_info:
            await delete(dataset_id=dataset_id, id=person_id)

        assert exc_info.value.status == 404
        assert exc_info.value.title == "Not Found"
        assert exc_info.value.detail is not None
        assert person_id in exc_info.value.detail
        assert dataset_id in exc_info.value.detail
        mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_delete_person_curator_user(
    mock_db_session_factory, curator_user, sample_persons
):
    """Test curator user can delete person in their authorized dataset"""
    # Arrange
    dataset_id = "dataset1"
    person_id = 2
    target_person = sample_persons[1]  # PERSON_002

    # Mock person exists check
    mock_person_exists = MagicMock()
    mock_person_exists.fetchone.return_value = MagicMock(
        person_id=target_person.person_id
    )

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_person_exists, None, None])
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in curator_user[
            "authorized_datasets"
        ] and curator_user["permissions"].get(dataset_id, {}).get("write", False)

        # Act
        response = await delete(dataset_id=dataset_id, id=str(person_id))
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert "message" in result
        assert str(person_id) in result["message"]
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_person_readonly_user_forbidden(mock_db_session_factory, user1):
    """Test read-only user cannot delete person"""
    # Arrange
    dataset_id = "dataset1"
    person_id = "1"

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        mock_auth.return_value = dataset_id in user1["authorized_datasets"] and user1[
            "permissions"
        ].get(dataset_id, {}).get("write", False)

        # Act
        response = await delete(dataset_id=dataset_id, id=person_id)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]


@pytest.mark.asyncio
async def test_delete_person_admin_user(
    mock_db_session_factory, admin_user, sample_persons
):
    """Test admin user can delete person from any dataset"""
    # Arrange
    dataset_id = "dataset3"
    person_id = 3
    target_person = sample_persons[2]  # PERSON_003

    # Mock person exists check
    mock_person_exists = MagicMock()
    mock_person_exists.fetchone.return_value = MagicMock(
        person_id=target_person.person_id
    )

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_person_exists, None, None])
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get(dataset_id, {}).get("write", False)

        # Act
        response = await delete(dataset_id=dataset_id, id=str(person_id))
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert "message" in result
        assert str(person_id) in result["message"]
        mock_session.commit.assert_called_once()
