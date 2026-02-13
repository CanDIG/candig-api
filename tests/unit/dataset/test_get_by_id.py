from unittest.mock import patch

import pytest
from connexion.exceptions import ProblemException

from src.api.dataset_operations import get_by_id


@pytest.mark.asyncio
async def test_get_by_id_authorized_user_dataset_exists(
    arranged_dataset_context, mock_dataset_record
):
    """Test getting a dataset by ID - authorized user, dataset exists"""
    # Arrange
    dataset_id = "dataset1"
    mock_record = mock_dataset_record(dataset_id, 10)
    context = arranged_dataset_context(username="admin", datasets=[mock_record])

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = True

        # Act
        response = await get_by_id(dataset_id)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert isinstance(result, dict)
        assert result["id"] == dataset_id
        assert result["count"] == 10
        context["mock_session"].execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_id_dataset_with_zero_persons(
    arranged_dataset_context, mock_dataset_record
):
    """Test getting a dataset with zero persons"""
    # Arrange
    dataset_id = "empty_dataset"
    mock_record = mock_dataset_record(dataset_id, 0)
    context = arranged_dataset_context(username="admin", datasets=[mock_record])

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = True

        # Act
        response = await get_by_id(dataset_id)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert result["id"] == dataset_id
        assert result["count"] == 0


@pytest.mark.asyncio
async def test_get_by_id_unauthorized_user(arranged_dataset_context):
    """Test getting a dataset with unauthorized user returns 403"""
    dataset_id = "dataset1"
    context = arranged_dataset_context(username="user2")  # user2 has no permissions

    with patch("src.api.dataset_operations.is_action_allowed") as mock_auth:
        mock_auth.return_value = dataset_id in context["authorized_datasets"]

        response = await get_by_id(dataset_id)
        assert response is not None
        result, status_code = response

        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]
        assert dataset_id in result["error"]


@pytest.mark.asyncio
async def test_get_by_id_dataset_not_found(arranged_dataset_context):
    """Test getting a dataset that does not exist returns 404"""
    # Arrange
    dataset_id = "nonexistent_dataset"
    context = arranged_dataset_context(
        username="admin", datasets=[]
    )  # No datasets in DB

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = True

        # Act & Assert
        with pytest.raises(ProblemException) as exc_info:
            await get_by_id(dataset_id)

        assert exc_info.value.status == 404
        assert exc_info.value.title == "Not Found"
        assert exc_info.value.detail is not None
        assert dataset_id in exc_info.value.detail
