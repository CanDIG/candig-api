from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.dataset_operations import delete_by_id


@pytest.mark.asyncio
async def test_delete_by_id_success_with_persons(arranged_create_context):
    """Test delete a dataset with persons"""
    dataset_id = "dataset1"
    person_ids = [1, 2, 3]

    context = arranged_create_context(username="admin")

    # Mock dataset exists check
    mock_dataset_exists = MagicMock()
    mock_dataset_exists.one_or_none.return_value = MagicMock(id=dataset_id)

    # Mock person_ids retrieval
    mock_person_result = MagicMock()
    mock_person_result.fetchall.return_value = [(pid,) for pid in person_ids]

    execute_results = [mock_dataset_exists, mock_person_result, None, None]
    context["mock_session"].execute = AsyncMock(side_effect=execute_results)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
        patch("src.api.dataset_operations.remove_dataset") as mock_remove_authz,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = True
        mock_remove_authz.return_value = ({}, 200)

        response = await delete_by_id(dataset_id)
        assert response is not None
        result, status_code = response
        assert isinstance(result, dict)

        assert status_code == 200
        assert "message" in result
        assert dataset_id in result["message"]
        assert str(len(person_ids)) in result["message"]
        context["mock_session"].commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_by_id_unauthorized_user(arranged_create_context):
    """Test unauthorized user returns 403"""
    dataset_id = "dataset1"
    context = arranged_create_context(username="user2")  # user2 has no permissions

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = False

        response = await delete_by_id(dataset_id)
        assert response is not None
        result, status_code = response
        assert isinstance(result, dict)

        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]
        assert dataset_id in result["error"]


@pytest.mark.asyncio
async def test_delete_by_id_dataset_not_found():
    """Test dataset not found returns 404"""
    dataset_id = "nonexistent"
    mock_session = AsyncMock()

    # Mock dataset doesn't exist
    mock_dataset_not_exists = MagicMock()
    mock_dataset_not_exists.one_or_none.return_value = None

    mock_session.execute = AsyncMock(return_value=mock_dataset_not_exists)
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        with pytest.raises(ProblemException) as exc_info:
            await delete_by_id(dataset_id)

        assert exc_info.value.status == 404
        assert exc_info.value.title == "Not Found"
        assert exc_info.value.detail is not None
        assert dataset_id in exc_info.value.detail
        mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_delete_by_id_admin_user(arranged_create_context):
    """Test admin user can delete any dataset"""
    dataset_id = "dataset3"
    person_ids = [10, 11]

    context = arranged_create_context(username="admin")

    # Mock dataset exists check
    mock_dataset_exists = MagicMock()
    mock_dataset_exists.one_or_none.return_value = MagicMock(id=dataset_id)

    # Mock person_ids retrieval
    mock_person_result = MagicMock()
    mock_person_result.fetchall.return_value = [(pid,) for pid in person_ids]

    execute_results = [mock_dataset_exists, mock_person_result, None, None]
    context["mock_session"].execute = AsyncMock(side_effect=execute_results)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
        patch("src.api.dataset_operations.remove_dataset") as mock_remove_authz,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = True
        mock_remove_authz.return_value = ({}, 200)

        response = await delete_by_id(dataset_id)
        assert response is not None
        result, status_code = response
        assert isinstance(result, dict)

        assert status_code == 200
        assert "message" in result


@pytest.mark.asyncio
async def test_delete_by_id_curator_user(arranged_create_context):
    """Test curator user can delete authorized datasets"""
    dataset_id = "dataset2"
    person_ids = [5]

    context = arranged_create_context(username="curator")

    # Mock dataset exists check
    mock_dataset_exists = MagicMock()
    mock_dataset_exists.one_or_none.return_value = MagicMock(id=dataset_id)

    # Mock person_ids retrieval
    mock_person_result = MagicMock()
    mock_person_result.fetchall.return_value = [(pid,) for pid in person_ids]

    execute_results = [mock_dataset_exists, mock_person_result, None, None]
    context["mock_session"].execute = AsyncMock(side_effect=execute_results)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
        patch("src.api.dataset_operations.remove_dataset") as mock_remove_authz,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = True
        mock_remove_authz.return_value = ({}, 200)

        response = await delete_by_id(dataset_id)
        assert response is not None
        result, status_code = response
        assert isinstance(result, dict)

        assert status_code == 200
        assert "message" in result


@pytest.mark.asyncio
async def test_delete_by_id_read_only_user(arranged_create_context):
    """Test read-only user cannot delete datasets"""
    dataset_id = "dataset1"
    context = arranged_create_context(username="user1")  # user1 has read-only access

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = (
            False  # Read-only users should not be allowed to delete
        )

        response = await delete_by_id(dataset_id)
        assert response is not None
        result, status_code = response
        assert isinstance(result, dict)

        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]
