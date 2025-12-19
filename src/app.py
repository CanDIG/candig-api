"""
CanDIG API Application

This module initializes Connexion app with OpenAPI schema
"""

import sys
from contextlib import asynccontextmanager

from candigv2_logging.logging import CanDIGLogger, initialize
from connexion import AsyncApp

from .api import beacon_operations, dataset_operations, person_operations, query_operations, auth

initialize()
logger = CanDIGLogger(__file__)

sys.modules["auth"] = auth
from .api import authz_operations
sys.modules["authz_operations"] = authz_operations
sys.modules["query_operations"] = query_operations
sys.modules["dataset_operations"] = dataset_operations
sys.modules["person_operations"] = person_operations
sys.modules['beacon_operations'] = beacon_operations

@asynccontextmanager
async def lifespan(app):
    """
    Lifespan context manager for startup and shutdown tasks.
    """
    # Startup
    logger.info("Application starting up...")
    # put any setup functions here
    logger.info("Application startup complete.")

    yield

    # Shutdown
    logger.info("Application shutting down...")


app = AsyncApp(__name__, specification_dir="../", lifespan=lifespan)

app.add_api("schema.yml", validate_responses=True)
app.add_api("beacon-schema.yml", validate_responses=True)
app.add_api("authz-schema.yml", validate_responses=True, pythonic_params=True, strict_validation=True)

if __name__ == "__main__":
    app.run(port=8080, reload=False)
