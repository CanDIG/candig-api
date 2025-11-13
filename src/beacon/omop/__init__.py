import logging
from ...config import settings
from sqlalchemy import create_engine

LOG = logging.getLogger(__name__)

db_url = settings.DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://")
LOG.debug(db_url)

#client = psycopg2.connect(db_url)
engine = create_engine(db_url)

