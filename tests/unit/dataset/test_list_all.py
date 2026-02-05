from unittest.mock import patch

import pytest

from src.api.dataset_operations import list_all


@pytest.mark.asyncio
async def test_list_all_admin_sees_all_three_datasets(
    arranged_dataset_context, sample_datasets
):
    """Test admin user sees all 3 datasets"""
    # Arrange
    context = arranged_dataset_context(username="admin", datasets=sample_datasets)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.get_authorized_datasets") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = context["authorized_datasets"]

        # Act
        response = await list_all()
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert len(result) == context["expected_count"]
        assert result[0]["id"] == "dataset1"
        assert result[0]["count"] == 5
        assert result[1]["id"] == "dataset2"
        assert result[1]["count"] == 10
        assert result[2]["id"] == "dataset3"
        assert result[2]["count"] == 15


@pytest.mark.asyncio
async def test_list_all_curator_sees_two_datasets(
    arranged_dataset_context, sample_datasets
):
    """Test curator user sees dataset1 and dataset2"""
    # Arrange
    context = arranged_dataset_context(username="curator", datasets=sample_datasets)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.get_authorized_datasets") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = context["authorized_datasets"]

        # Act
        response = await list_all()
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert len(result) == context["expected_count"]
        assert result[0]["id"] == "dataset1"
        assert result[0]["count"] == 5
        assert result[1]["id"] == "dataset2"
        assert result[1]["count"] == 10


@pytest.mark.asyncio
async def test_list_all_user1_sees_only_dataset1(
    arranged_dataset_context, sample_datasets
):
    """Test user1 sees only dataset1 (read-only access)"""
    # Arrange
    context = arranged_dataset_context(username="user1", datasets=sample_datasets)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.get_authorized_datasets") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = context["authorized_datasets"]

        # Act
        response = await list_all()
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert len(result) == context["expected_count"]
        assert result[0]["id"] == "dataset1"
        assert result[0]["count"] == 5


@pytest.mark.asyncio
async def test_list_all_user2_sees_no_datasets(
    arranged_dataset_context, sample_datasets
):
    """Test user2 sees no datasets (no access) - unauthorized scenario"""
    # Arrange
    context = arranged_dataset_context(
        username="user2", datasets=sample_datasets
    )  # user2 has no permissions

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.get_authorized_datasets") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = context["authorized_datasets"]

        # Act
        response = await list_all()
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 200
        assert len(result) == context["expected_count"]  # 0 datasets
