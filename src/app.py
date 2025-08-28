"""
CanDIG API Application

This module initializes Connexion app with OpenAPI specification
The API spec is loaded from schema.yml.
"""
import sys
from connexion import AsyncApp
from .api import query_operations
from .api import dataset_operations
# from .api import person_operations
from .database.db_setup import create_database_tables

from candigv2_logging.logging import CanDIGLogger, initialize  # type: ignore

initialize()
logger = CanDIGLogger(__file__)

sys.modules['query_operations'] = query_operations
sys.modules['dataset_operations'] = dataset_operations
# sys.modules['person_operations'] = person_operations

app = AsyncApp(__name__, specification_dir='../')

app.add_api("schema.yml", validate_responses=True)


if __name__ == "__main__":
    create_database_tables()
    app.run(port=8080, reload=False)