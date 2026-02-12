from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_auth_token():
    """Mock auth token"""
    return "mock_jwt_token_12345"


@pytest.fixture
def authorized_user_datasets():
    """Default authorized datasets for a user"""
    return ["dataset1", "dataset2", "dataset3"]


# --- User Authorization Fixtures ---


@pytest.fixture
def admin_user():
    """Admin user with read/write access to all 3 datasets"""
    return {
        "username": "admin",
        "authorized_datasets": ["dataset1", "dataset2", "dataset3"],
        "permissions": {
            "dataset1": {"read": True, "write": True},
            "dataset2": {"read": True, "write": True},
            "dataset3": {"read": True, "write": True},
        },
    }


@pytest.fixture
def curator_user():
    """Curator user with read/write access to dataset1 and dataset2"""
    return {
        "username": "curator",
        "authorized_datasets": ["dataset1", "dataset2"],
        "permissions": {
            "dataset1": {"read": True, "write": True},
            "dataset2": {"read": True, "write": True},
        },
    }


@pytest.fixture
def user1():
    """User1 with read-only access to dataset1"""
    return {
        "username": "user1",
        "authorized_datasets": ["dataset1"],
        "permissions": {"dataset1": {"read": True, "write": False}},
    }


@pytest.fixture
def user2():
    """User2 with no access to any dataset"""
    return {"username": "user2", "authorized_datasets": [], "permissions": {}}


@pytest.fixture
def all_users(admin_user, curator_user, user1, user2):
    return {
        "admin": admin_user,
        "curator": curator_user,
        "user1": user1,
        "user2": user2,
    }


@pytest.fixture
def mock_get_authorized_datasets(all_users):
    """Factory fixture that returns authorized datasets based on current user"""

    def get_authorized_datasets(username: str = "admin"):
        """
        Get authorized datasets for a specific user.
        Defaults to admin if no username provided.
        """
        return all_users.get(username, all_users["admin"])["authorized_datasets"]

    return get_authorized_datasets


# --- Dataset Record Fixtures ---


@pytest.fixture
def mock_dataset_record():
    """Factory fixture for creating mock dataset records"""

    def create_record(dataset_id: str, person_count: int = 10):
        record = MagicMock()
        record.id = dataset_id
        record.person_count = person_count
        return record

    return create_record


@pytest.fixture
def mock_db_result():
    """Factory fixture for creating mock database query results"""

    def create_result(records: list):
        result = MagicMock()
        result.all.return_value = records
        result.one_or_none.return_value = records[0] if records else None
        result.fetchall.return_value = [(r.id,) for r in records] if records else []
        return result

    return create_result


@pytest.fixture
def sample_datasets(mock_dataset_record):
    return [
        mock_dataset_record("dataset1", 5),
        mock_dataset_record("dataset2", 10),
        mock_dataset_record("dataset3", 15),
    ]


@pytest.fixture
def empty_dataset(mock_dataset_record):
    """Dataset with zero persons"""
    return mock_dataset_record("empty_dataset", 0)


# --- Other Data Fixtures ---


@pytest.fixture
def sample_dataset_info():
    """Sample dataset info object"""
    return {
        "dataset_description": "Sample dataset for testing",
        "study_id": "STUDY_001",
        "contact_email": "researcher@example.com",
    }


@pytest.fixture
def sample_person_data():
    """Sample person data for dataset operations"""
    return {
        "person_source_value": "PERSON_001",
        "gender_concept_id": 8507,
        "year_of_birth": 1990,
        "race_concept_id": 0,
        "ethnicity_concept_id": 0,
    }


@pytest.fixture
def mock_db_session_factory(mock_db_session):
    """Factory for creating configured mock db sessions with results"""

    def _create_session(result=None, side_effect=None):
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        if side_effect:
            session.execute.side_effect = side_effect
        elif result:
            session.execute.return_value = result
        else:
            session.execute = AsyncMock()

        return session

    return _create_session


# --- Arranged Test Context Fixtures ---


@pytest.fixture
def arranged_dataset_context(mock_db_result, mock_get_authorized_datasets, all_users):
    """
    General-purpose fixture for arranging dataset operation tests with user permissions.
    Returns a factory function that sets up test context for any dataset operation.

    Usage:
        # For list operations
        context = arranged_dataset_context(username="admin", datasets=sample_datasets)

        # For unauthorized tests
        context = arranged_dataset_context(username="user2", datasets=sample_datasets)

        # For single dataset operations
        context = arranged_dataset_context(username="curator", datasets=[dataset1])

        # With custom result behavior
        context = arranged_dataset_context(username="admin", datasets=[], result_type="one_or_none")
    """

    def setup_context(
        username: str = "admin",
        datasets: list | None = None,
        result_type: str = "all",
        db_error: Exception | None = None,
    ):
        # Default to empty datasets if none provided
        if datasets is None:
            datasets = []

        # Create mock session with database results
        mock_session = AsyncMock()

        if db_error:
            # Configure session to raise an error
            mock_session.execute.side_effect = db_error
        else:
            # Configure normal result
            mock_result = mock_db_result(datasets)
            mock_session.execute.return_value = mock_result

        # Get user information
        user_info = all_users.get(username, all_users["admin"])
        authorized_datasets = user_info["authorized_datasets"]
        user_permissions = user_info["permissions"]

        # Calculate expected count based on user permissions
        available_dataset_ids = [d.id for d in datasets]
        accessible_datasets = [
            d_id for d_id in available_dataset_ids if d_id in authorized_datasets
        ]
        expected_count = len(accessible_datasets)

        return {
            "mock_session": mock_session,
            "authorized_datasets": authorized_datasets,
            "user_permissions": user_permissions,
            "expected_count": expected_count,
            "username": username,
            "accessible_datasets": accessible_datasets,
        }

    return setup_context


@pytest.fixture
def arranged_create_context(all_users):
    """
    Pre-arranged context for create/write operation tests.
    Returns a factory function that sets up test context for a specific user.

    Usage:
        context = arranged_create_context(username="admin")  # for authorized create
        context = arranged_create_context(username="user2")  # for unauthorized tests
    """

    def setup_context(username: str = "admin", db_error: Exception | None = None):
        # Create mock session
        mock_session = AsyncMock()

        if db_error:
            # Configure session to raise an error
            mock_session.execute.side_effect = db_error
        else:
            # Configure normal session
            mock_session.execute = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()

        # Get user information
        user_info = all_users.get(username, all_users["admin"])
        user_permissions = user_info["permissions"]

        # Determine if user has write permissions (for create operations, we typically check for admin)
        # admin and curator have write permissions, user1 and user2 do not
        is_authorized = username in ["admin", "curator"]

        return {
            "mock_session": mock_session,
            "is_authorized": is_authorized,
            "username": username,
            "user_permissions": user_permissions,
        }

    return setup_context


@pytest.fixture
def mock_person_record():
    """Factory fixture for creating mock person records"""

    def create_record(
        person_id: int,
        gender_concept_id: int = 8507,
        year_of_birth: int = 1990,
        month_of_birth: int = 1,
        day_of_birth: int = 1,
        birth_datetime=None,
        race_concept_id: int = 0,
        ethnicity_concept_id: int = 0,
        location_id=None,
        provider_id=None,
        care_site_id=None,
        person_source_value=None,
        gender_source_value=None,
        gender_source_concept_id=None,
        race_source_value=None,
        race_source_concept_id=None,
        ethnicity_source_value=None,
        ethnicity_source_concept_id=None,
    ):
        record = MagicMock()
        record.person_id = person_id
        record.gender_concept_id = gender_concept_id
        record.year_of_birth = year_of_birth
        record.month_of_birth = month_of_birth
        record.day_of_birth = day_of_birth
        record.birth_datetime = birth_datetime
        record.race_concept_id = race_concept_id
        record.ethnicity_concept_id = ethnicity_concept_id
        record.location_id = location_id
        record.provider_id = provider_id
        record.care_site_id = care_site_id
        record.person_source_value = person_source_value or f"PERSON_{person_id}"
        record.gender_source_value = gender_source_value
        record.gender_source_concept_id = gender_source_concept_id
        record.race_source_value = race_source_value
        record.race_source_concept_id = race_source_concept_id
        record.ethnicity_source_value = ethnicity_source_value
        record.ethnicity_source_concept_id = ethnicity_source_concept_id
        return record

    return create_record


@pytest.fixture
def sample_persons(mock_person_record):
    """Pre-configured sample person records for dataset1"""
    return [
        mock_person_record(1, person_source_value="PERSON_001"),
        mock_person_record(2, person_source_value="PERSON_002"),
        mock_person_record(3, person_source_value="PERSON_003"),
    ]
