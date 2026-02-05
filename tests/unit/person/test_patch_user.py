from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.person_operations import patch_user


@pytest.mark.asyncio
async def test_patch_user_success(admin_user, mock_person_record):
    """Test successful partial update of a person"""
    dataset_id = "dataset1"
    person_id = 1
    body = {"gender_concept_id": 8532}

    mock_session = AsyncMock()

    # Mock person exists check
    mock_exists = MagicMock()
    mock_exists.fetchone.return_value = MagicMock(person_id=person_id)

    # Mock current and updated person using fixture
    current_person = mock_person_record(person_id, gender_concept_id=8507)
    updated_person = mock_person_record(person_id, gender_concept_id=8532)

    mock_current = MagicMock()
    mock_current.fetchone.return_value = current_person

    mock_update = MagicMock()
    mock_update.fetchone.return_value = updated_person

    mock_session.execute = AsyncMock(
        side_effect=[mock_exists, mock_current, mock_update]
    )
    mock_session.commit = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get(dataset_id, {}).get("write", False)

        response = await patch_user(dataset_id=dataset_id, id=str(person_id), body=body)
        assert response is not None
        result, status_code = response

        assert status_code == 200
        assert result["person_id"] == person_id
        assert result["gender_concept_id"] == 8532
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_patch_user_unauthorized(user2):
    """Test patching when user is not authorized"""
    dataset_id = "dataset1"

    with patch("src.api.person_operations.is_action_allowed") as mock_auth:
        mock_auth.return_value = dataset_id in user2["authorized_datasets"] and user2[
            "permissions"
        ].get(dataset_id, {}).get("write", False)

        response = await patch_user(dataset_id=dataset_id, id="1", body={})
        assert response is not None
        result, status_code = response

        assert status_code == 403
        assert "not authorized" in result["error"]


@pytest.mark.asyncio
async def test_patch_user_not_found(admin_user):
    """Test patching a person that doesn't exist"""
    dataset_id = "dataset1"
    mock_session = AsyncMock()
    mock_exists = MagicMock()
    mock_exists.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_exists)
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get(dataset_id, {}).get("write", False)

        with pytest.raises(ProblemException) as exc_info:
            await patch_user(
                dataset_id=dataset_id, id="9999", body={"gender_concept_id": 8532}
            )

        assert exc_info.value.status == 404


@pytest.mark.asyncio
async def test_patch_user_id_mismatch(curator_user):
    """Test patching with mismatched URL ID and body person_id"""
    dataset_id = "dataset1"
    mock_session = AsyncMock()
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = dataset_id in curator_user[
            "authorized_datasets"
        ] and curator_user["permissions"].get(dataset_id, {}).get("write", False)

        with pytest.raises(ProblemException) as exc_info:
            await patch_user(dataset_id=dataset_id, id="1", body={"person_id": 999})

        assert exc_info.value.status == 400
        assert exc_info.value.detail is not None
        assert "does not match" in exc_info.value.detail
