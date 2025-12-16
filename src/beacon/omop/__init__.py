from ...config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from ...database.db_operations import async_engine

from candigv2_logging.logging import CanDIGLogger, initialize

logger = CanDIGLogger(__file__)

db_url = settings.DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://")
logger.info(db_url)

#client = psycopg2.connect(db_url)
#engine = create_engine(db_url, echo=True)

#async def init():
#    async def extract_column_names(db_name: str) -> list:
#        with Session(engine) as session:
#            result = await session.execute(text(f"SELECT * from x LIMIT 1"), {"x": db_name})
#            return result.keys()
#
#    # For some reason, entire lists of column names are required under each possible dataset
#    engine.beacon = {}
#    engine.beacon.datasets = await extract_column_names('datasets')
#    engine.beacon.genomicVariations = await extract_column_names('genomicVariations')
#
#    engine.initialized = True

engine = async_engine
