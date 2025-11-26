"""
Background daemon that monitors upload folder for new data JSON files.

When a file is detected, it queues for process, ingest each donor
with clinical data, and writes the result to a status update.

If any ingestion fails, all inserted data are rolled back.

Upload file is deleted after completion.
"""

import asyncio
import json
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from queue import Queue

import watchdog.events
from candigv2_logging.logging import CanDIGLogger, initialize
from watchdog.observers import Observer

from src.api.dataset_operations import delete_by_id
from src.api.helpers import handle_single_donor_data_ingestion
from src.config import settings

initialize()
logger = CanDIGLogger(__file__)

processing_queue = Queue()


# --- Helper to create directories on startup ---
def setup_upload_folders():
    os.makedirs(settings.TO_INGEST_DIR, exist_ok=True)
    os.makedirs(settings.RESULTS_DIR, exist_ok=True)


async def ingest_donors(donors_list: list) -> tuple[list, list]:
    """
    Ingest each donor with clinical data.
    If failure occurs, roll back and remove any inserted data.
    """
    failed_donors = []
    inserted_dataset_ids = []

    for idx, donor_data in enumerate(donors_list):
        try:
            logger.info(f"Ingesting data at index {idx}")
            result, status_code = await handle_single_donor_data_ingestion(donor_data)  # type: ignore
            if status_code == 201:
                dataset_record = next(
                    (
                        r
                        for r in result.get("records", [])
                        if r.get("omop_table") == "dataset"
                    ),
                    None,
                )
                if dataset_record and (dataset_id := dataset_record.get("id")):
                    if dataset_id not in inserted_dataset_ids:
                        inserted_dataset_ids.append(dataset_id)
            else:
                failed_donors.append({"donor_index": idx, "status": status_code})
                raise Exception(
                    f"Failed to insert donor at index {idx} with status {status_code}"
                )
        except Exception as e:
            logger.error(f"{traceback.format_exc()}\nError occurred during ingest. Starting rollback…")
            failed_donors.append({"donor_index": idx, "error": str(e)})
            # Delete cascade inserted dataset
            for dataset_id in inserted_dataset_ids:
                try:
                    await delete_by_id(dataset_id)
                except Exception as rollback_error:
                    logger.error(
                        f"Failed to rollback dataset {dataset_id}: {str(rollback_error)}"
                    )
            raise

    return failed_donors, inserted_dataset_ids


# --- Main ingest function ---
async def process_queued_file(file_path: str):
    """Read a file, ingest data, and removes the file after complete"""
    queue_id = os.path.basename(file_path)
    results_path = os.path.join(settings.RESULTS_DIR, queue_id)

    logger.info(f"Processing job {queue_id}")
    file_size = os.path.getsize(file_path)

    # Read existing metadata (filename, uploaded_at)
    existing_metadata = {}
    try:
        if os.path.exists(results_path):
            with open(results_path, "r") as f:
                existing_metadata = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read existing metadata for {queue_id}: {e}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            donors_list = json.load(f)["donors"]

        failed_donors, _ = await ingest_donors(donors_list)

        result_data = {
            **existing_metadata,
            "file_size": file_size,
            "status": "Success" if not failed_donors else "Failed",
            "processed_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
            **({"failures": failed_donors} if failed_donors else {}),
        }
    except Exception as e:
        logger.error(f"ERROR IN JOB QUEUE ID {queue_id}: {e}")
        result_data = {
            **existing_metadata,
            "file_size": file_size,
            "status": "Failed",
            "processed_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
            "error": f"{str(e)}",
        }

    # update status
    try:
        with open(results_path, "w") as f:
            json.dump(result_data, f, indent=4)
    except IOError as e:
        logger.error(f"Could not write results for {queue_id}: {e}")

    # remove file
    try:
        os.remove(file_path)
    except (IOError, FileNotFoundError) as e:
        logger.error(f"Could not remove source file for {queue_id}: {e}")


class DaemonHandler(watchdog.events.FileSystemEventHandler):
    def on_created(self, event):
        """Add to queue when there is a new file"""
        if not event.is_directory:
            logger.info(f"New file detected: {event.src_path}. Adding to queue.")
            processing_queue.put(event.src_path)


def worker_thread_func():
    """
    Processes files asynchronously.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        while True:
            file_path = processing_queue.get()
            if file_path is None:
                break
            try:
                # Run the async function in this thread's event loop
                loop.run_until_complete(process_queued_file(file_path))
            except Exception as e:
                logger.error(f"Unhandled exception in worker for file {file_path}: {e}")
            processing_queue.task_done()
    finally:
        loop.close()


def run_daemon():
    """
    This function starts a background worker thread and a file watcher
    that monitors a directory for new files to ingest.
    """
    ingest_path = settings.TO_INGEST_DIR
    logger.info("Daemon started. Watching for new files")

    # make sure we have a folder
    setup_upload_folders()

    # Start the background worker
    worker = threading.Thread(target=worker_thread_func)
    worker.daemon = True
    worker.start()

    # Process any backlog
    for filename in os.listdir(ingest_path):
        file_path = os.path.join(ingest_path, filename)
        if os.path.isfile(file_path):
            processing_queue.put(file_path)  # Add backlog to the queue
            logger.info(f"Added backlog file to queue: {file_path}")

    # Start the observer to watch for new files
    event_handler = DaemonHandler()
    observer = Observer()
    observer.schedule(event_handler, ingest_path, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
        observer.stop()
        processing_queue.put(None)  # Signal the worker to exit
    finally:
        observer.join()
        worker.join()
    logger.info("Daemon has shut down.")


if __name__ == "__main__":
    while True:
        try:
            run_daemon()
            break
        except Exception as e:
            logger.error(f"Daemon crashed: {e}")
            time.sleep(5)
