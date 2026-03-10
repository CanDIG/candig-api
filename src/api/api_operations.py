"""
API operations like service info, file upload and status tracking...
"""

import json
import os
import secrets
import shutil
import tempfile
from datetime import datetime, timezone

import connexion
from authx.auth import get_user_id
from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException

from src.api.auth import get_authorized_datasets
from src.api.ingest_helpers import check_genomic_data

from ..config import settings  # Import settings

logger = CanDIGLogger(__file__)


# --- Service Info Endpoint ---
async def get_service_info():
    service_info = {
        "name": "CanDIG-API",
        "description": "This is an API for CanDIG.",
        "version": "0.1.0",
    }

    return service_info


# --- Upload Endpoint ---
async def upload_file(file):
    """
    Write a file to server and create a queue status ID
    """
    temp_path = None
    try:
        content = await file.read()

        # Before attempting to ingest a dataset, we need to check user permissions
        try:
            request = connexion.request
            token = request.headers["Authorization"].split("Bearer ")[1]
            jsoncontent = json.loads(content)
            authzed_datasets = get_authorized_datasets()
            for dataset in jsoncontent["datasets"]:
                ds_id = dataset["id"]
                if ds_id not in authzed_datasets:
                    return {
                        "error": "Forbidden",
                        "message": f"User {get_user_id(request)} does not have permission to ingest '{ds_id}'",
                    }, 403
        except Exception as e:
            raise ProblemException(
                status=500, title="Uploaded File in Unexpected Format", detail=str(e)
            )

        # Generate a unique ID for this job
        queue_id = secrets.token_hex(8)

        # write to file
        temp_dir = tempfile.gettempdir()
        with tempfile.NamedTemporaryFile(
            delete=False, mode="wb", dir=temp_dir, suffix=".tmp"
        ) as f:
            temp_path = f.name
            f.write(content)

        # Create an initial status file with filename and timestamp
        results_path = os.path.join(settings.RESULTS_DIR, queue_id)
        with open(results_path, "w") as f:
            json.dump(
                {
                    "status": "In Queue",
                    "file_name": file.filename,
                    "file_size": len(content),
                    "uploaded_at": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S UTC"
                    ),
                },
                f,
            )

        # move the file to trigger the daemon
        final_path = os.path.join(settings.TO_INGEST_DIR, queue_id)
        shutil.move(temp_path, final_path)

        logger.info(f"File '{file.filename}' queued with ID: {queue_id}")

        return {
            "message": "File uploaded for processing.",
            "queue_id": queue_id,
            "url": f"/v1/datasets/upload/status/{queue_id}",
        }, 202

    except ProblemException:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    except Exception as e:
        # Cleanup the temp file if something went wrong
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        logger.error(f"Error in upload_file: {str(e)}")
        raise ProblemException(status=500, title="Upload Error", detail=str(e))


# --- Sample Upload Endpoint ---
async def upload_sample(file, prefix: str):
    """
    Write a sample to server and create a queue status ID
    """
    temp_path = None
    try:
        content = await file.read()

        # Before attempting to ingest, we need to check user permissions
        try:
            request = connexion.request
            jsoncontent = json.loads(content)
            authzed_datasets = get_authorized_datasets()
            for donor in jsoncontent["donors"]:
                program_id = f"{prefix}~{donor['program_id']}"
                if program_id not in authzed_datasets:
                    return {
                        "error": "Forbidden",
                        "message": f"User {get_user_id(request)} does not have permission to ingest '{program_id}'",
                    }, 403
        except (KeyError, json.JSONDecodeError) as e:
            raise ProblemException(
                status=500, title="Uploaded File in Unexpected Format", detail=str(e)
            )

        # Generate a unique ID for this job
        queue_id = secrets.token_hex(8)

        # Write the file to a temp location first
        temp_dir = tempfile.gettempdir()
        with tempfile.NamedTemporaryFile(
            delete=False, mode="wb", dir=temp_dir, suffix=".tmp"
        ) as f:
            temp_path = f.name
            f.write(content)

        results_path = os.path.join(settings.RESULTS_DIR, queue_id)
        stub = {
            "status": "In Queue",
            "file_name": file.filename,
            "file_size": len(content),
            "uploaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "prefix": prefix,
        }

        with open(results_path, "w") as f:
            json.dump(stub, f)

        # Move the file into the ingest folder to trigger the daemon
        final_path = os.path.join(settings.TO_INGEST_DIR, queue_id)
        shutil.move(temp_path, final_path)

        logger.info(
            f"Sample file '{file.filename}' queued with ID: {queue_id} (prefix='{prefix}')"
        )

        return {
            "message": "Sample file uploaded for processing.",
            "queue_id": queue_id,
            "url": f"/v1/datasets/upload/status/{queue_id}",
        }, 202

    except ProblemException:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        logger.error(f"Error in upload_sample: {str(e)}")
        raise ProblemException(status=500, title="Upload Error", detail=str(e))


# --- Status Endpoint ---
async def get_upload_status(queue_id: str):
    """
    Checks the results file for a given queue_id.
    """
    results_path = os.path.join(settings.RESULTS_DIR, queue_id)

    if not os.path.exists(results_path):
        return {
            "query": {
                "error": "Not Found",
                "message": f"No job found with ID {queue_id}",
            }
        }, 404

    try:
        with open(results_path, "r") as f:
            status_data = json.load(f)
        return status_data, 200
    except Exception as e:
        logger.error(f"Error reading status file for {queue_id}: {str(e)}")
        return {
            "query": {
                "error": "Internal Server Error",
                "message": f"Unable to read status for job {queue_id}",
            }
        }, 500


async def whoami():
    """
    Determine the user key of the currently logged in user
    NB: This should probably not be in candig-api, and should be moved out when we can
    """
    OPA_URL = os.getenv("OPA_URL", f"http://localhost:8181")
    return {"key": get_user_id(connexion.request, opa_url=OPA_URL)}, 200
