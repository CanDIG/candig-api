from ...config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from ...database.db_operations import async_engine

from candigv2_logging.logging import CanDIGLogger, initialize

logger = CanDIGLogger(__file__)

db_url = settings.DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://")
logger.info(db_url)

engine = async_engine
