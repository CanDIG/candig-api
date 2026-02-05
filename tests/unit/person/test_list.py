from unittest.mock import MagicMock, patch

import pytest

from src.api.person_operations import list

# --- Test authorized user sees full person details ---


@pytest.mark.asyncio
async def test_list_authorized_user_sees_full_details(
    mock_db_session_factory, sample_persons, admin_user
):
    """Test admin user sees full person details for dataset1"""
    # Arrange
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(sample_persons)
    mock_session = mock_db_session_factory(result=mock_result)

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        # Check if dataset1 is in admin's authorized datasets and has read permission
        mock_auth.return_value = "dataset1" in admin_user[
            "authorized_datasets"
        ] and admin_user["permissions"].get("dataset1", {}).get("read", False)

        # Act
        response = await list(dataset_id="dataset1")
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert len(result) == 3
        assert result[0]["person_id"] == 1
        assert result[0]["person_source_value"] == "PERSON_001"
        assert "gender_concept_id" in result[0]
        assert "year_of_birth" in result[0]
        assert result[1]["person_id"] == 2
        assert result[2]["person_id"] == 3


@pytest.mark.asyncio
async def test_list_authorized_user_empty_dataset(
    mock_db_session_factory, curator_user
):
    """Test curator user with empty dataset returns empty list"""
    # Arrange
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([])
    mock_session = mock_db_session_factory(result=mock_result)

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        # Check if dataset1 is in curator's authorized datasets and has read permission
        mock_auth.return_value = "dataset1" in curator_user[
            "authorized_datasets"
        ] and curator_user["permissions"].get("dataset1", {}).get("read", False)

        # Act
        response = await list(dataset_id="dataset1")
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert len(result) == 0


# --- Test unauthorized user sees only person IDs ---


@pytest.mark.asyncio
async def test_list_unauthorized_user_sees_only_ids(mock_db_session_factory, user2):
    """Test user2 (no access) sees only person IDs"""
    # Arrange
    # Create minimal mock records with just person_id
    mock_id_records = [
        MagicMock(person_id=1),
        MagicMock(person_id=2),
        MagicMock(person_id=3),
    ]

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(mock_id_records)
    mock_session = mock_db_session_factory(result=mock_result)

    with (
        patch("src.api.person_operations.get_db_session") as mock_get_db,
        patch("src.api.person_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        # Check if dataset1 is in user2's authorized datasets (it's not)
        mock_auth.return_value = "dataset1" in user2["authorized_datasets"] and user2[
            "permissions"
        ].get("dataset1", {}).get("read", False)

        # Act
        response = await list(dataset_id="dataset1")
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert len(result) == 3
        # Should return just IDs, not dictionaries
        assert result == [1, 2, 3]
