"""
Custom error handling functions for the CanDIG API.
"""

import re
from typing import Optional

from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from sqlalchemy.exc import IntegrityError

logger = CanDIGLogger(__file__)


async def raise_integrity_error(e: IntegrityError):
    """
    Raise SQLAlchemy IntegrityErrors
    """
    logger.error(f"Database Integrity Error: {e}")

    error_str = str(e).lower()
    error_orig = str(e.orig) if hasattr(e, "orig") else str(e)

    # Defaults
    status = 400
    title = "Database Integrity Error"
    detail_msg = "Could not save the data due to a database constraint."
    extra_hint = ""

    # 1. Find specific error type
    if "foreign key constraint" in error_str or "foreignkeyviolation" in error_str:
        title = "Invalid Reference"
        extra_hint = "You are referencing an ID that does not exist in the database."

    elif "unique constraint" in error_str or "uniqueviolation" in error_str:
        status = 409
        title = "Duplicate Record"
        extra_hint = "A record with this identifier already exists."

    elif "not null constraint" in error_str or "notnullviolation" in error_str:
        title = "Missing Required Field"
        extra_hint = "A required database field was left empty."

    # Extract detail error message, e.g "DETAIL:  Key (id)=(123) already exists."
    match = re.search(r"DETAIL:\s*(.*?)(?:\n|$)", error_orig)
    if match:
        db_detail = match.group(1).strip()
        detail_msg = f"{extra_hint} Database Detail: {db_detail}"
    else:
        detail_msg = f"{extra_hint} {detail_msg}"

    raise ProblemException(
        status=status,
        title=title,
        detail=detail_msg.strip(),
    )


async def raise_problem_exception(e: Exception, custom_detail: Optional[str] = None):
    """
    Handles generic Python exceptions.
    """
    # Log the full error
    logger.error(f"Processing Exception: {type(e).__name__}: {e}")

    if isinstance(e, ProblemException):
        raise e

    # 1. Lookup Errors (Missing Keys/IDs)
    if isinstance(e, KeyError):
        raise ProblemException(
            status=400,
            title="Missing Reference ID",
            detail=custom_detail
            or f"Could not find a mapping for ID: {str(e)}. Ensure the referenced entity is defined before it is used.",
        )

    # 2. Data Format Errors
    elif isinstance(e, (ValueError, TypeError)):
        raise ProblemException(
            status=400,
            title="Invalid Data Format",
            detail=custom_detail or f"Data validation failed: {str(e)}",
        )

    else:
        raise ProblemException(
            status=500,
            title="Internal Processing Error",
            detail=custom_detail
            or "An unexpected internal error occurred. Please check server logs for traceback.",
        )
