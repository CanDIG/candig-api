"""
Custom error handling functions for the CanDIG API with
appropriate status codes and error messages.
"""
from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from sqlalchemy.exc import IntegrityError

logger = CanDIGLogger(__file__)


async def raise_integrity_error(e: IntegrityError):
    logger.error(f"Database Integrity Error: {e}")

    extra_details = ""
    error_str = str(e).lower()
    if "foreign key constraint" in error_str or "foreignkeyviolation" in error_str:
        extra_details += "A related record does not exist.\n"
    if "unique constraint" in error_str or "uniqueviolation" in error_str:
        extra_details += "This value must be unique and it already exists.\n"

    error_msg = str(e.orig)
    if "DETAIL:" in error_msg:
        error_msg = error_msg.split("DETAIL:", 1)[1].split("\n", 1)[0].strip()
    else:
        error_msg = "No specific detail available."

    raise ProblemException(
        status=400,
        title="Database Integrity Error",
        detail=f"Could not save the data.\n{extra_details}Details: {error_msg}",
    )


async def raise_problem_exception(e: Exception):
    logger.error(f"Problem Exception: {e}")

    raise ProblemException(
        status=500,
        title="Processing Error",
        detail="An internal error occurred while processing the payload.",
    )


async def raise_bad_request(obj: str):
    logger.error(f"Bad Request: Payload must contain one valid {obj}")
    
    raise ProblemException(
        status=400,
        title="Bad Request",
        detail=f"Payload must contain one valid {obj} record at the donor level.",
    )
