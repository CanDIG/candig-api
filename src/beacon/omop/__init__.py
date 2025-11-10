import logging
from ...config import settings

LOG = logging.getLogger(__name__)

db_url = settings.DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://")
LOG.debug(db_url)

#client = psycopg2.connect(db_url)

