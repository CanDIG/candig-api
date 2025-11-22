"""
CanDIG API Application

This module initializes Connexion app with OpenAPI schema
"""

import sys
from contextlib import asynccontextmanager
from connexion import AsyncApp
from .api import query_operations
from .api import dataset_operations
from .api import person_operations
from .database.db_setup import (
    create_tables,
    update_FK_delete_cascade,
    update_tables_identity,
    update_column_limits,
)

from candigv2_logging.logging import CanDIGLogger, initialize

initialize()
logger = CanDIGLogger(__file__)

sys.modules["query_operations"] = query_operations
sys.modules["dataset_operations"] = dataset_operations
sys.modules["person_operations"] = person_operations


@asynccontextmanager
async def lifespan(app):
    """
    Lifespan context manager for startup and shutdown tasks.
    """
    # Startup
    logger.info("Application starting up...")
    await create_tables()
    await update_tables_identity()
    await update_column_limits()
    await update_FK_delete_cascade()
    logger.info("Application startup complete.")

    yield

    # Shutdown
    logger.info("Application shutting down...")


app = AsyncApp(__name__, specification_dir="../", lifespan=lifespan)

app.add_api("schema.yml", validate_responses=True)

if __name__ == "__main__":
    app.run(port=8080, reload=False)
