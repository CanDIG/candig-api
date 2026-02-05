from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.dataset_operations import put_by_id


@pytest.mark.asyncio
async def test_put_by_id_update_info(arranged_create_context):
    """Test updating dataset info"""
    dataset_id = "dataset1"
    body = {"info": {"description": "Updated"}}

    context = arranged_create_context(username="admin")

    mock_existing_dataset = MagicMock()
    mock_existing_dataset.id = dataset_id
    mock_check_result = MagicMock()
    mock_check_result.one_or_none.return_value = mock_existing_dataset

    mock_existing_persons_result = MagicMock()
    mock_existing_persons_result.fetchall.return_value = []

    execute_results = [mock_check_result, None, mock_existing_persons_result]
    context["mock_session"].execute = AsyncMock(side_effect=execute_results)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = True

        response = await put_by_id(dataset_id, body)
        assert response is not None
        result, status_code = response

        assert status_code == 200
        assert result["id"] == dataset_id
        context["mock_session"].commit.assert_called_once()


@pytest.mark.asyncio
async def test_put_by_id_add_new_person():
    """Test adding a new person"""
    dataset_id = "dataset1"
    body = {
        "info": {},
        "persons": [
            {
                "person_source_value": "NEW_PERSON",
                "gender_concept_id": 8507,
                "year_of_birth": 1995,
                "race_concept_id": 0,
                "ethnicity_concept_id": 0,
            }
        ],
    }

    mock_session = AsyncMock()
    mock_existing_dataset = MagicMock()
    mock_check_result = MagicMock()
    mock_check_result.one_or_none.return_value = mock_existing_dataset

    mock_existing_persons_result = MagicMock()
    mock_existing_persons_result.fetchall.return_value = []

    mock_person_result = MagicMock()
    mock_person_result.scalar_one.return_value = 99999

    execute_results = [
        mock_check_result,
        None,
        mock_existing_persons_result,
        mock_person_result,
        None,
    ]
    mock_session.execute = AsyncMock(side_effect=execute_results)
    mock_session.commit = AsyncMock()

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        response = await put_by_id(dataset_id, body)
        assert response is not None
        result, status_code = response

        assert status_code == 200
        assert result["id"] == dataset_id


@pytest.mark.asyncio
async def test_put_by_id_update_existing_person():
    """Test updating an existing person"""
    dataset_id = "dataset1"
    person_id = 12345
    body = {
        "info": {},
        "persons": [
            {
                "person_id": person_id,
                "person_source_value": "UPDATED",
                "gender_concept_id": 8532,
                "year_of_birth": 1990,
                "race_concept_id": 0,
                "ethnicity_concept_id": 0,
            }
        ],
    }

    mock_session = AsyncMock()
    mock_existing_dataset = MagicMock()
    mock_check_result = MagicMock()
    mock_check_result.one_or_none.return_value = mock_existing_dataset

    mock_existing_persons_result = MagicMock()
    mock_existing_persons_result.fetchall.return_value = [(person_id,)]

    mock_person_exists = MagicMock()
    mock_person_exists.fetchone.return_value = (1,)

    mock_link_exists = MagicMock()
    mock_link_exists.fetchone.return_value = (1,)

    execute_results = [
        mock_check_result,
        None,
        mock_existing_persons_result,
        mock_person_exists,
        None,
        mock_link_exists,
    ]
    mock_session.execute = AsyncMock(side_effect=execute_results)
    mock_session.commit = AsyncMock()

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        response = await put_by_id(dataset_id, body)
        assert response is not None
        result, status_code = response

        assert status_code == 200


@pytest.mark.asyncio
async def test_put_by_id_unauthorized_user(arranged_create_context):
    """Test unauthorized user returns 403"""
    dataset_id = "dataset1"
    context = arranged_create_context(username="user2")  # user2 has no permissions

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = context["is_authorized"]

        response = await put_by_id(dataset_id, {"info": {}})
        assert response is not None
        result, status_code = response

        assert status_code == 403
        assert "error" in result
        assert "not authorized" in result["error"]


@pytest.mark.asyncio
async def test_put_by_id_dataset_not_found():
    """Test dataset not found returns 404"""
    mock_session = AsyncMock()
    mock_check_result = MagicMock()
    mock_check_result.one_or_none.return_value = None

    mock_session.execute = AsyncMock(return_value=mock_check_result)
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        with pytest.raises(ProblemException) as exc_info:
            await put_by_id("nonexistent", {"info": {}})

        assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_put_by_id_person_not_found():
    """Test updating with non-existent person_id returns 400"""
    mock_session = AsyncMock()

    mock_existing_dataset = MagicMock()
    mock_check_result = MagicMock()
    mock_check_result.one_or_none.return_value = mock_existing_dataset

    mock_existing_persons_result = MagicMock()
    mock_existing_persons_result.fetchall.return_value = []

    mock_person_not_exists = MagicMock()
    mock_person_not_exists.fetchone.return_value = None

    execute_results = [
        mock_check_result,
        None,
        mock_existing_persons_result,
        mock_person_not_exists,
    ]
    mock_session.execute = AsyncMock(side_effect=execute_results)
    mock_session.rollback = AsyncMock()

    body = {
        "info": {},
        "persons": [
            {"person_id": 99999, "gender_concept_id": 8507, "year_of_birth": 1990}
        ],
    }

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        with pytest.raises(ProblemException) as exc_info:
            await put_by_id("dataset1", body)

        assert exc_info.value.status == 400
