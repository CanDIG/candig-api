"""
Tests for API operations - upload_file endpoint
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from connexion.exceptions import ProblemException

from src.api.api_operations import upload_file


@pytest.fixture
def mock_file():
    """Factory fixture for creating mock uploaded files"""

    def create_file(filename: str, content: dict):
        """
        Create a mock file object that mimics connexion file upload
        """
        file_mock = MagicMock()
        file_mock.filename = filename
        json_content = json.dumps(content).encode("utf-8")
        file_mock.read = AsyncMock(return_value=json_content)
        return file_mock

    return create_file


@pytest.fixture
def valid_dataset_payload():
    """Valid dataset JSON payload with authorized datasets"""
    return {
        "datasets": [
            {"id": "dataset1", "info": {"description": "Test dataset 1"}},
            {"id": "dataset2", "info": {"description": "Test dataset 2"}},
        ]
    }


@pytest.fixture
def unauthorized_dataset_payload():
    """Dataset JSON payload with unauthorized dataset"""
    return {
        "datasets": [
            {"id": "dataset1", "info": {"description": "Authorized dataset"}},
            {
                "id": "unauthorized_dataset",
                "info": {"description": "User doesn't have access"},
            },
        ]
    }


@pytest.fixture
def mock_connexion_request(mock_auth_token):
    """Mock connexion.request with authorization header"""

    def create_request(user_id: str = "test_user"):
        request_mock = MagicMock()
        request_mock.headers = {"Authorization": f"Bearer {mock_auth_token}"}
        return request_mock

    return create_request


@pytest.fixture
def mock_directories(tmp_path):
    """Create temporary directories for file operations"""
    to_ingest_dir = tmp_path / "to_ingest"
    results_dir = tmp_path / "results"
    to_ingest_dir.mkdir()
    results_dir.mkdir()

    return {
        "to_ingest": str(to_ingest_dir),
        "results": str(results_dir),
        "tmp": str(tmp_path),
    }


@pytest.fixture
def setup_auth_mocks():
    """Setup common authentication mocks"""

    def setup(
        mock_request,
        mock_get_auth_datasets,
        mock_get_user_id,
        authorized_datasets,
        user_id="test_user",
        token="test_token",
    ):
        mock_request.headers = {"Authorization": f"Bearer {token}"}
        mock_get_auth_datasets.return_value = authorized_datasets
        mock_get_user_id.return_value = user_id

    return setup


@pytest.fixture
def setup_file_system_mocks():
    """Setup common file system mocks"""

    def setup(
        mock_settings,
        mock_gettempdir,
        mock_named_temp_file,
        mock_directories,
        temp_filename="temp_file.tmp",
    ):
        mock_settings.RESULTS_DIR = mock_directories["results"]
        mock_settings.TO_INGEST_DIR = mock_directories["to_ingest"]
        mock_gettempdir.return_value = mock_directories["tmp"]

        temp_file_path = os.path.join(mock_directories["tmp"], temp_filename)
        temp_file_mock = mock_open()
        mock_named_temp_file.return_value.__enter__.return_value = temp_file_mock()
        mock_named_temp_file.return_value.__enter__.return_value.name = temp_file_path

        return temp_file_path

    return setup


# --- Success Path Tests ---


@pytest.mark.asyncio
@patch("src.api.api_operations.secrets.token_hex")
@patch("src.api.api_operations.shutil.move")
@patch("src.api.api_operations.tempfile.NamedTemporaryFile")
@patch("src.api.api_operations.tempfile.gettempdir")
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
@patch("src.api.api_operations.settings")
async def test_upload_file_success_authorized_datasets(
    mock_settings,
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_gettempdir,
    mock_named_temp_file,
    mock_shutil_move,
    mock_token_hex,
    mock_file,
    valid_dataset_payload,
    mock_connexion_request,
    mock_directories,
    authorized_user_datasets,
    setup_auth_mocks,
    setup_file_system_mocks,
):
    """Test successful file upload with authorized datasets"""
    # Arrange
    queue_id = "abc123def456"
    mock_token_hex.return_value = queue_id

    file = mock_file("test_data.json", valid_dataset_payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )
    setup_file_system_mocks(
        mock_settings, mock_gettempdir, mock_named_temp_file, mock_directories
    )

    # Mock the status file write
    with patch("builtins.open", mock_open()) as mocked_open:
        # Act
        result, status_code = await upload_file(file)

        # Assert
        assert status_code == 202
        assert result["message"] == "File uploaded for processing."
        assert result["queue_id"] == queue_id
        assert result["url"] == f"/v1/datasets/upload/status/{queue_id}"

        # Verify file operations
        file.read.assert_called_once()
        mock_shutil_move.assert_called_once()

        # Verify status file was created
        mocked_open.assert_called()


@pytest.mark.asyncio
@patch("src.api.api_operations.secrets.token_hex")
@patch("src.api.api_operations.shutil.move")
@patch("src.api.api_operations.tempfile.NamedTemporaryFile")
@patch("src.api.api_operations.tempfile.gettempdir")
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
@patch("src.api.api_operations.settings")
async def test_upload_file_creates_correct_status_file(
    mock_settings,
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_gettempdir,
    mock_named_temp_file,
    mock_shutil_move,
    mock_token_hex,
    mock_file,
    valid_dataset_payload,
    mock_directories,
    authorized_user_datasets,
    setup_auth_mocks,
    setup_file_system_mocks,
):
    """Test that status file is created with correct metadata"""
    # Arrange
    queue_id = "test_queue_id"
    mock_token_hex.return_value = queue_id
    filename = "upload_test.json"

    file = mock_file(filename, valid_dataset_payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )
    setup_file_system_mocks(
        mock_settings,
        mock_gettempdir,
        mock_named_temp_file,
        mock_directories,
        "temp.tmp",
    )

    written_data = {}

    def capture_json_dump(data, f):
        written_data.update(data)

    with patch("json.dump", side_effect=capture_json_dump):
        # Act
        result, status_code = await upload_file(file)

        # Assert
        assert status_code == 202
        assert written_data["status"] == "In Queue"
        assert written_data["file_name"] == filename
        assert written_data["file_size"] > 0
        assert "uploaded_at" in written_data
        assert "UTC" in written_data["uploaded_at"]


# --- Authorization Failure Tests ---


@pytest.mark.asyncio
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
async def test_upload_file_unauthorized_dataset_returns_403(
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_file,
    unauthorized_dataset_payload,
    authorized_user_datasets,
    setup_auth_mocks,
):
    """Test that uploading file with unauthorized dataset returns 403"""
    # Arrange
    file = mock_file("test.json", unauthorized_dataset_payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )

    # Act
    result, status_code = await upload_file(file)

    # Assert
    assert status_code == 403
    assert result["error"] == "Forbidden"
    assert "unauthorized_dataset" in result["message"]
    assert "test_user" in result["message"]


# --- Invalid Input Tests ---


@pytest.mark.asyncio
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
async def test_upload_file_malformed_json_returns_error(
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    authorized_user_datasets,
    setup_auth_mocks,
):
    """Test that malformed JSON content is handled"""
    # Arrange
    file_mock = MagicMock()
    file_mock.filename = "bad.json"
    file_mock.read = AsyncMock(return_value=b"not valid json {{{")

    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )

    # Act & Assert
    with pytest.raises(ProblemException) as exc_info:
        await upload_file(file_mock)

    assert exc_info.value.status == 500
    assert exc_info.value.title == "Uploaded File in Unexpected Format"


@pytest.mark.asyncio
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
async def test_upload_file_missing_datasets_key(
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_file,
    authorized_user_datasets,
    setup_auth_mocks,
):
    """Test that JSON without 'datasets' key is handled"""
    # Arrange
    invalid_payload = {"data": [{"id": "test"}]}  # Missing 'datasets' key
    file = mock_file("test.json", invalid_payload)

    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )

    # Act & Assert
    with pytest.raises(ProblemException) as exc_info:
        await upload_file(file)

    assert exc_info.value.status == 500
    assert exc_info.value.title == "Uploaded File in Unexpected Format"


@pytest.mark.asyncio
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
async def test_upload_file_empty_file(
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    authorized_user_datasets,
    setup_auth_mocks,
):
    """Test handling of empty file upload"""
    # Arrange
    file_mock = MagicMock()
    file_mock.filename = "empty.json"
    file_mock.read = AsyncMock(return_value=b"{}")

    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )

    # Act & Assert
    with pytest.raises(ProblemException) as exc_info:
        await upload_file(file_mock)

    assert exc_info.value.status == 500
    assert exc_info.value.title == "Uploaded File in Unexpected Format"


# --- Structural Validation Tests ---
# These tests verify the upload endpoint's behavior with various malformed structures


@pytest.mark.asyncio
@patch("src.api.api_operations.secrets.token_hex")
@patch("src.api.api_operations.shutil.move")
@patch("src.api.api_operations.tempfile.NamedTemporaryFile")
@patch("src.api.api_operations.tempfile.gettempdir")
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
@patch("src.api.api_operations.settings")
async def test_upload_file_with_nested_json(
    mock_settings,
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_gettempdir,
    mock_named_temp_file,
    mock_shutil_move,
    mock_token_hex,
    mock_file,
    mock_directories,
    authorized_user_datasets,
    setup_auth_mocks,
    setup_file_system_mocks,
):
    """Test upload with realistic complex OMOP structure"""
    # Arrange
    queue_id = "complex_test_id"
    mock_token_hex.return_value = queue_id

    complex_payload = {
        "datasets": [
            {
                "id": "dataset1",
                "info": {"description": "Complex dataset"},
                "linked_records": [
                    {
                        "person": {
                            "person_source_value": "DONOR_0001",
                            "gender_concept_id": 8507,
                            "year_of_birth": 1980,
                            "month_of_birth": 5,
                            "day_of_birth": 15,
                            "race_concept_id": 8527,
                            "ethnicity_concept_id": 38003564,
                        },
                        "linked_records": [
                            {
                                "observation": {
                                    "observation_id": "OBS_001",
                                    "observation_concept_id": 4035726,
                                    "observation_date": "2020-01-01",
                                    "observation_type_concept_id": 32879,
                                }
                            },
                            {
                                "condition_occurrence": {
                                    "condition_occurrence_id": "COND_001",
                                    "condition_concept_id": 201820,
                                    "condition_start_date": "2020-06-01",
                                    "condition_type_concept_id": 32020,
                                }
                            },
                        ],
                    }
                ],
            }
        ]
    }

    file = mock_file("complex.json", complex_payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )
    setup_file_system_mocks(
        mock_settings, mock_gettempdir, mock_named_temp_file, mock_directories
    )

    with patch("builtins.open", mock_open()):
        # Act
        result, status_code = await upload_file(file)

        # Assert - Upload should succeed; validation happens during ingestion
        assert status_code == 202
        assert result["queue_id"] == queue_id


@pytest.mark.asyncio
@patch("src.api.api_operations.secrets.token_hex")
@patch("src.api.api_operations.shutil.move")
@patch("src.api.api_operations.tempfile.NamedTemporaryFile")
@patch("src.api.api_operations.tempfile.gettempdir")
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
@patch("src.api.api_operations.settings")
async def test_upload_file_missing_person_in_linked_records(
    mock_settings,
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_gettempdir,
    mock_named_temp_file,
    mock_shutil_move,
    mock_token_hex,
    mock_file,
    mock_directories,
    authorized_user_datasets,
    setup_auth_mocks,
    setup_file_system_mocks,
):
    """Test upload with linked_records missing 'person' key (structural validation happens at ingestion)"""
    # Arrange
    queue_id = "missing_person_id"
    mock_token_hex.return_value = queue_id

    # This structure is missing the 'person' key in linked_records
    payload = {
        "datasets": [
            {
                "id": "dataset1",
                "linked_records": [
                    {
                        # Missing 'person' key
                        "linked_records": [
                            {
                                "observation": {
                                    "observation_id": "OBS_001",
                                    "observation_concept_id": 4035726,
                                    "observation_date": "2020-01-01",
                                }
                            }
                        ]
                    }
                ],
            }
        ]
    }

    file = mock_file("missing_person.json", payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )
    setup_file_system_mocks(
        mock_settings, mock_gettempdir, mock_named_temp_file, mock_directories
    )

    with patch("builtins.open", mock_open()):
        # Act - Upload accepts it but ingestion will fail
        result, status_code = await upload_file(file)

        # Assert - Upload succeeds, but this will fail during ingestion
        assert status_code == 202
        assert result["queue_id"] == queue_id


@pytest.mark.asyncio
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
async def test_upload_file_mixed_valid_invalid_datasets(
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_file,
    authorized_user_datasets,
    setup_auth_mocks,
):
    """Test that file with mix of valid and structurally invalid datasets is rejected"""
    # Arrange
    invalid_payload = {
        "datasets": [
            {"id": "dataset1", "info": {"description": "Valid dataset"}},
            {
                # Missing ID
                "info": {"description": "Invalid dataset"}
            },
        ]
    }
    file = mock_file("test.json", invalid_payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )

    # Act & Assert
    with pytest.raises(ProblemException) as exc_info:
        await upload_file(file)

    assert exc_info.value.status == 500
    assert exc_info.value.title == "Uploaded File in Unexpected Format"


# --- Foreign Key Mismatch Tests ---
# These tests verify FK validation during ingestion and error capture in status file
@pytest.mark.asyncio
@patch("src.api.helpers.get_db_session")
@patch("src.api.helpers.create_dataset")
@patch("src.api.helpers.create_person")
@patch("src.api.helpers.create_person_in_dataset")
@patch("src.api.helpers.create_record")
@patch("src.api.api_operations.secrets.token_hex")
@patch("src.api.api_operations.shutil.move")
@patch("src.api.api_operations.tempfile.NamedTemporaryFile")
@patch("src.api.api_operations.tempfile.gettempdir")
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
@patch("src.api.api_operations.settings")
async def test_upload_file_with_measurement_fk_mismatch(
    mock_settings,
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_gettempdir,
    mock_named_temp_file,
    mock_shutil_move,
    mock_token_hex,
    mock_create_record,
    mock_create_person_in_dataset,
    mock_create_person,
    mock_create_dataset,
    mock_get_db_session,
    mock_file,
    mock_directories,
    authorized_user_datasets,
    setup_auth_mocks,
    setup_file_system_mocks,
):
    """
    Test that FK mismatch in measurement_event_id is caught during ingestion
    and the error is properly captured in error_logs.
    """
    from src.api.helpers import ingest_data

    # Arrange
    queue_id = "fk_mismatch_test"
    mock_token_hex.return_value = queue_id

    fk_mismatch_payload = {
        "datasets": [
            {
                "id": "dataset1",
                "info": {"description": "Dataset with FK mismatch"},
                "linked_records": [
                    {
                        "person": {
                            "person_source_value": "DONOR_FK_TEST",
                            "gender_concept_id": 8507,
                            "year_of_birth": 1980,
                        },
                        "linked_records": [
                            {
                                "measurement": {
                                    "measurement_id": "MEAS_001",
                                    "measurement_concept_id": 3004249,
                                    "measurement_date": "2020-01-15",
                                    "measurement_type_concept_id": 44818702,
                                    # FK reference to non-existent event - will fail
                                    "measurement_event_id": "NONEXISTENT_EVENT_ID",
                                }
                            }
                        ],
                    }
                ],
            }
        ]
    }

    file = mock_file("fk_mismatch.json", fk_mismatch_payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )
    setup_file_system_mocks(
        mock_settings, mock_gettempdir, mock_named_temp_file, mock_directories
    )

    # Mock DB session
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar=MagicMock(return_value=None))
    )
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    # Setup mocks for dataset and person creation
    mock_create_dataset.return_value = {"id": "dataset1"}
    mock_create_person.return_value = {"person_id": 12345}
    mock_create_person_in_dataset.return_value = {}

    # Mock create_record to raise ProblemException for FK mismatch
    mock_create_record.side_effect = ProblemException(
        status=422,
        title="Missing Foreign Key in Mapping Table",
        detail="The FK 'NONEXISTENT_EVENT_ID' was not found in the mapping table for field 'measurement_event_id' in table 'measurement'.",
    )

    def create_session_gen():
        async def gen():
            yield mock_session

        return gen()

    mock_get_db_session.side_effect = lambda: create_session_gen()

    with patch(
        "src.api.helpers.check_person_exists", new_callable=AsyncMock
    ) as mock_check_person:
        mock_check_person.return_value = False

        with patch("builtins.open", mock_open()):
            # Act - Upload the file
            result, status_code = await upload_file(file)

            # Assert upload succeeded
            assert status_code == 202
            assert result["queue_id"] == queue_id

            # Now simulate ingestion by calling ingest_data directly
            ingested_persons, error_logs, fail_count = await ingest_data(
                fk_mismatch_payload, queue_id
            )

            # Assert - FK mismatch should cause ingestion failure
            assert fail_count == 1, f"Expected 1 failure, got {fail_count}"
            assert len(ingested_persons) == 0, (
                f"Expected 0 ingested persons, got {len(ingested_persons)}"
            )
            assert len(error_logs) > 0, "Expected error logs to be captured"

            # Verify error message contains FK mismatch details
            error_message = error_logs[0]
            assert "DONOR_FK_TEST" in error_message, (
                f"Expected person ID in error: {error_message}"
            )
            assert "Missing Foreign Key" in error_message, (
                f"Expected FK error message: {error_message}"
            )
            assert "NONEXISTENT_EVENT_ID" in error_message, (
                f"Expected FK reference in error: {error_message}"
            )


@pytest.mark.asyncio
@patch("src.api.helpers.get_db_session")
@patch("src.api.helpers.create_dataset")
@patch("src.api.helpers.create_person")
@patch("src.api.helpers.create_person_in_dataset")
@patch("src.api.helpers.create_record")
@patch("src.api.api_operations.secrets.token_hex")
@patch("src.api.api_operations.shutil.move")
@patch("src.api.api_operations.tempfile.NamedTemporaryFile")
@patch("src.api.api_operations.tempfile.gettempdir")
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
@patch("src.api.api_operations.settings")
async def test_upload_file_with_episode_event_fk_mismatch(
    mock_settings,
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_gettempdir,
    mock_named_temp_file,
    mock_shutil_move,
    mock_token_hex,
    mock_create_record,
    mock_create_person_in_dataset,
    mock_create_person,
    mock_create_dataset,
    mock_get_db_session,
    mock_file,
    mock_directories,
    authorized_user_datasets,
    setup_auth_mocks,
    setup_file_system_mocks,
):
    """
    Test that FK mismatch in episode_event (event_id doesn't exist) is caught
    and the error is properly captured.
    """
    from src.api.helpers import ingest_data

    # Arrange
    queue_id = "episode_event_fk_mismatch"
    mock_token_hex.return_value = queue_id

    fk_mismatch_payload = {
        "datasets": [
            {
                "id": "dataset1",
                "info": {"description": "Dataset with episode_event FK mismatch"},
                "linked_records": [
                    {
                        "person": {
                            "person_source_value": "DONOR_EPISODE_TEST",
                            "gender_concept_id": 8532,
                            "year_of_birth": 1975,
                        },
                        "linked_records": [
                            {
                                "episode": {
                                    "episode_id": "EPISODE_001",
                                    "episode_concept_id": 32533,
                                    "episode_start_date": "2020-05-01",
                                    "episode_type_concept_id": 32545,
                                }
                            },
                            {
                                "episode_event": {
                                    "episode_id": "EPISODE_001",
                                    "event_id": "MISSING_EVENT_999",
                                }
                            },
                        ],
                    }
                ],
            }
        ]
    }

    file = mock_file("episode_event_fk_mismatch.json", fk_mismatch_payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )
    setup_file_system_mocks(
        mock_settings, mock_gettempdir, mock_named_temp_file, mock_directories
    )

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar=MagicMock(return_value=None))
    )
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_create_dataset.return_value = {"id": "dataset1"}
    mock_create_person.return_value = {"person_id": 12345}
    mock_create_person_in_dataset.return_value = {}

    # First call creates episode successfully, second call (episode_event) raises FK error
    mock_create_record.side_effect = [
        {"episode_id": 100},  # First call for episode succeeds
        ProblemException(  # Second call for episode_event fails
            status=422,
            title="Missing Foreign Key in Mapping Table",
            detail="The FK 'MISSING_EVENT_999' was not found in the mapping table for field 'event_id' in table 'episode_event'.",
        ),
    ]

    def create_session_gen():
        async def gen():
            yield mock_session

        return gen()

    mock_get_db_session.side_effect = lambda: create_session_gen()

    with patch(
        "src.api.helpers.check_person_exists", new_callable=AsyncMock
    ) as mock_check_person:
        mock_check_person.return_value = False

        with patch("builtins.open", mock_open()):
            result, status_code = await upload_file(file)
            assert status_code == 202

            ingested_persons, error_logs, fail_count = await ingest_data(
                fk_mismatch_payload, queue_id
            )

            assert fail_count == 1
            assert len(ingested_persons) == 0
            assert len(error_logs) > 0

            error_message = error_logs[0]
            assert "DONOR_EPISODE_TEST" in error_message
            assert "Missing Foreign Key" in error_message
            assert "MISSING_EVENT_999" in error_message


@pytest.mark.asyncio
@patch("src.api.helpers.get_db_session")
@patch("src.api.helpers.create_dataset")
@patch("src.api.helpers.create_person")
@patch("src.api.helpers.create_person_in_dataset")
@patch("src.api.helpers.create_record")
@patch("src.api.api_operations.secrets.token_hex")
@patch("src.api.api_operations.shutil.move")
@patch("src.api.api_operations.tempfile.NamedTemporaryFile")
@patch("src.api.api_operations.tempfile.gettempdir")
@patch("src.api.api_operations.get_user_id")
@patch("src.api.api_operations.get_authorized_datasets")
@patch("src.api.api_operations.connexion.request", new_callable=MagicMock)
@patch("src.api.api_operations.settings")
async def test_upload_file_with_fact_relationship_fk_mismatch(
    mock_settings,
    mock_request,
    mock_get_auth_datasets,
    mock_get_user_id,
    mock_gettempdir,
    mock_named_temp_file,
    mock_shutil_move,
    mock_token_hex,
    mock_create_record,
    mock_create_person_in_dataset,
    mock_create_person,
    mock_create_dataset,
    mock_get_db_session,
    mock_file,
    mock_directories,
    authorized_user_datasets,
    setup_auth_mocks,
    setup_file_system_mocks,
):
    """
    Test that FK mismatch in fact_relationship (fact_id_2 must exist) is caught.
    """
    from src.api.helpers import ingest_data

    # Arrange
    queue_id = "fact_relationship_fk_mismatch"
    mock_token_hex.return_value = queue_id

    fk_mismatch_payload = {
        "datasets": [
            {
                "id": "dataset1",
                "info": {"description": "Dataset with fact_relationship FK mismatch"},
                "linked_records": [
                    {
                        "person": {
                            "person_source_value": "DONOR_FACT_TEST",
                            "gender_concept_id": 8532,
                            "year_of_birth": 1985,
                        },
                        "linked_records": [
                            {
                                "observation": {
                                    "observation_id": "OBS_001",
                                    "observation_concept_id": 4035726,
                                    "observation_date": "2020-01-01",
                                    "observation_type_concept_id": 32879,
                                }
                            },
                            {
                                "fact_relationship": {
                                    "domain_concept_id_1": 27,
                                    "fact_id_1": "OBS_001",
                                    "domain_concept_id_2": 21,
                                    "fact_id_2": "NONEXISTENT_FACT_999",
                                    "relationship_concept_id": 44818888,
                                }
                            },
                        ],
                    }
                ],
            }
        ]
    }

    file = mock_file("fact_relationship_fk.json", fk_mismatch_payload)
    setup_auth_mocks(
        mock_request, mock_get_auth_datasets, mock_get_user_id, authorized_user_datasets
    )
    setup_file_system_mocks(
        mock_settings, mock_gettempdir, mock_named_temp_file, mock_directories
    )

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar=MagicMock(return_value=None))
    )
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_create_dataset.return_value = {"id": "dataset1"}
    mock_create_person.return_value = {"person_id": 12345}
    mock_create_person_in_dataset.return_value = {}

    # First call creates observation successfully, second call (fact_relationship) raises FK error
    mock_create_record.side_effect = [
        {"observation_id": 200},  # First call for observation succeeds
        ProblemException(  # Second call for fact_relationship fails
            status=422,
            title="Missing Foreign Key in Mapping Table",
            detail="The FK 'NONEXISTENT_FACT_999' was not found in the mapping table for field 'fact_id_2' in table 'fact_relationship'.",
        ),
    ]

    def create_session_gen():
        async def gen():
            yield mock_session

        return gen()

    mock_get_db_session.side_effect = lambda: create_session_gen()

    with patch(
        "src.api.helpers.check_person_exists", new_callable=AsyncMock
    ) as mock_check_person:
        mock_check_person.return_value = False

        with patch("builtins.open", mock_open()):
            result, status_code = await upload_file(file)
            assert status_code == 202

            ingested_persons, error_logs, fail_count = await ingest_data(
                fk_mismatch_payload, queue_id
            )

            assert fail_count == 1
            assert len(ingested_persons) == 0
            assert len(error_logs) > 0

            error_message = error_logs[0]
            assert "DONOR_FACT_TEST" in error_message
            assert "Missing Foreign Key" in error_message
            assert "NONEXISTENT_FACT_999" in error_message
