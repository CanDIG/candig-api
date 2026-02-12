from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connexion.exceptions import ProblemException
from sqlalchemy.exc import IntegrityError

from src.api.dataset_operations import create


@pytest.mark.asyncio
async def test_create_dataset_without_persons_authorized_user(arranged_create_context):
    """Test creating a dataset without persons - authorized user"""
    # Arrange
    body = {
        "id": "new_dataset",
        "info": {"description": "Test dataset", "study_id": "STUDY_001"},
    }

    context = arranged_create_context(username="admin")

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = context["is_authorized"]

        # Act
        response = await create(body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 201
        assert isinstance(result, dict)
        assert result["id"] == "new_dataset"
        assert isinstance(result["info"], dict)
        assert result["info"]["description"] == "Test dataset"
        assert context["mock_session"].execute.call_count == 1
        context["mock_session"].commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_dataset_with_all_person_fields():
    """Test creating a dataset with person containing all optional fields"""
    # Arrange
    body = {
        "id": "complete_person_dataset",
        "info": {"description": "Complete person data"},
        "persons": [
            {
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
        ],
    }

    mock_session = AsyncMock()
    mock_person_result = MagicMock()
    mock_person_result.scalar_one.return_value = 99999

    execute_results = [None, mock_person_result, None]
    mock_session.execute = AsyncMock(side_effect=execute_results)
    mock_session.commit = AsyncMock()

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        # Act
        response = await create(body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 201
        assert isinstance(result, dict)
        assert result["id"] == "complete_person_dataset"
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_dataset_with_multiple_persons():
    """Test creating a dataset with multiple persons"""
    # Arrange
    body = {
        "id": "dataset_multi_person",
        "info": {"description": "Dataset with multiple persons"},
        "persons": [
            {
                "person_source_value": "PERSON_001",
                "gender_concept_id": 8507,
                "year_of_birth": 1990,
                "race_concept_id": 0,
                "ethnicity_concept_id": 0,
            },
            {
                "person_source_value": "PERSON_002",
                "gender_concept_id": 8532,
                "year_of_birth": 1985,
                "race_concept_id": 0,
                "ethnicity_concept_id": 0,
            },
        ],
    }

    mock_session = AsyncMock()
    mock_person_result1 = MagicMock()
    mock_person_result1.scalar_one.return_value = 12345
    mock_person_result2 = MagicMock()
    mock_person_result2.scalar_one.return_value = 12346

    # Setup execute: dataset insert, person1 insert, person1 link, person2 insert, person2 link
    execute_results = [None, mock_person_result1, None, mock_person_result2, None]
    mock_session.execute = AsyncMock(side_effect=execute_results)
    mock_session.commit = AsyncMock()

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        # Act
        response = await create(body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 201
        assert isinstance(result, dict)
        assert result["id"] == "dataset_multi_person"
        assert mock_session.execute.call_count == 5
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_dataset_unauthorized_user(arranged_create_context):
    """Test creating a dataset with unauthorized user returns 403"""
    # Arrange
    body = {"id": "unauthorized_dataset", "info": {"description": "Should fail"}}

    context = arranged_create_context(username="user2")  # user2 has no permissions

    with patch("src.api.dataset_operations.is_action_allowed") as mock_auth:
        mock_auth.return_value = context["is_authorized"]  # False for user2

        # Act
        response = await create(body)
        assert response is not None
        result, status_code = response

        # Assert
        assert status_code == 403
        assert isinstance(result, dict)
        assert "not authorized" in result["error"]
        assert "unauthorized_dataset" in result["error"]


@pytest.mark.asyncio
async def test_create_dataset_duplicate_id_integrity_error(arranged_create_context):
    """Test creating a dataset with duplicate ID raises IntegrityError"""
    # Arrange
    body = {"id": "existing_dataset", "info": {"description": "Duplicate"}}

    integrity_error = IntegrityError(
        "INSERT statement",
        {},
        Exception(
            "UniqueViolationError: duplicate key value\nDETAIL: Key (id)=(existing_dataset) already exists."
        ),
    )
    context = arranged_create_context(username="admin", db_error=integrity_error)

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [context["mock_session"]]
        mock_auth.return_value = context["is_authorized"]

        # Act & Assert
        with pytest.raises(ProblemException) as exc_info:
            await create(body)

        assert exc_info.value.status == 400
        assert exc_info.value.title == "Database Integrity Error"
        assert exc_info.value.detail is not None
        assert "unique" in exc_info.value.detail.lower()
        context["mock_session"].rollback.assert_called_once()


@pytest.mark.asyncio
async def test_create_dataset_foreign_key_violation():
    """Test creating a dataset with invalid foreign key raises IntegrityError"""
    # Arrange
    body = {
        "id": "fk_error_dataset",
        "info": {},
        "persons": [
            {
                "person_source_value": "PERSON_FK",
                "gender_concept_id": 9999999,  # Invalid FK
                "year_of_birth": 1990,
                "race_concept_id": 0,
                "ethnicity_concept_id": 0,
            }
        ],
    }

    mock_session = AsyncMock()
    integrity_error = IntegrityError(
        "INSERT statement",
        {},
        Exception(
            "ForeignKeyViolationError: invalid foreign key\nDETAIL: Key (gender_concept_id)=(9999999) is not present in table."
        ),
    )

    execute_results = [None, integrity_error]
    mock_session.execute = AsyncMock(side_effect=execute_results)
    mock_session.rollback = AsyncMock()

    with (
        patch("src.api.dataset_operations.get_db_session") as mock_get_db,
        patch("src.api.dataset_operations.is_action_allowed") as mock_auth,
    ):
        mock_get_db.return_value.__aiter__.return_value = [mock_session]
        mock_auth.return_value = True

        # Act & Assert
        with pytest.raises(ProblemException) as exc_info:
            await create(body)

        assert exc_info.value.status == 400
        assert exc_info.value.title == "Database Integrity Error"
        assert exc_info.value.detail is not None
        assert "foreign key" in exc_info.value.detail.lower()
        mock_session.rollback.assert_called_once()

