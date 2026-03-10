"""
Background daemon that monitors upload folder for new data JSON files.

When a file is detected, it queues for process, ingest each donor
with clinical data, and writes the result to a status update.

If any ingestion fails, skip to the next.

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

from src.api.ingest_helpers import calculate_status, ingest_data, ingest_samples, ingest_genomic, write_results
from src.config import settings

initialize()
logger = CanDIGLogger(__file__)

processing_queue = Queue()


def detect_data_type(data: dict) -> str:
    """
    Determine the type of data based on the JSON structure.
    """
    # Check for MoH schema (samples/donors data)
    if data.get("schema_class") == "MoHSchemaV3":
        return "samples"

    # Default to OMOP for all other cases
    return "omop"


# ==============================================================================
# Main Ingest Function
# ==============================================================================


async def process_queued_file(file_path: str):
    """Read a file, ingest data, and removes the file after complete"""
    queue_id = os.path.basename(file_path)
    results_path = os.path.join(settings.RESULTS_DIR, queue_id)

    # Get file_name, file_size, uploaded_at from file
    result_data = {}
    try:
        if os.path.exists(results_path):
            with open(results_path, "r") as f:
                result_data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read existing metadata for {queue_id}: {e}")

    site_id = result_data.get("site_id")

    logger.info(f"PROCESSING JOB: {queue_id}")

    try:
        # 1. Read file
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2. Detect data type and use ingest function
        data_type = detect_data_type(data)
        logger.info(f"Detected data type: {data_type} for job {queue_id}")

        if data_type == "samples" and site_id:
            ingested_items, error_logs, fail_count = await ingest_samples(
                data, queue_id, site_id=site_id
            )
        elif data_type == "omop":
            ingested_items, error_logs, fail_count = await ingest_data(data, queue_id)
        else:
            raise ValueError(f"Unknown data type: {data_type}")

        # 3. Get status report
        success_count = len(ingested_items)
        status = calculate_status(success_count, fail_count)
        result_data.update(
            {
                "status": status,
                "data_type": data_type,
                "processed_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                ),
                "ingested_count": success_count,
                "ingested_items": ingested_items,
                "errors": error_logs if error_logs else None,
            }
        )

    except Exception as e:
        logger.error(f"FAILURE IN JOB: {queue_id}: {e}")
        logger.error(traceback.format_exc())

        result_data.update({"status": "Failed", "error_details": str(e)})

    # Save & Cleanup
    write_results(results_path, result_data, file_path)


# ==============================================================================
# Daemon Process
# ==============================================================================


class DaemonHandler(watchdog.events.FileSystemEventHandler):
    def on_created(self, event):
        """Add to queue when there is a new file"""
        if not event.is_directory:
            logger.info(f"New file detected: {event.src_path}. Adding to queue.")
            processing_queue.put(event.src_path)


def worker_thread_func():
    """Processes files asynchronously."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        while True:
            file_path = processing_queue.get()
            if file_path is None:
                break
            try:
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
    os.makedirs(settings.TO_INGEST_DIR, exist_ok=True)
    os.makedirs(settings.RESULTS_DIR, exist_ok=True)

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
