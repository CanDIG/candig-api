import asyncio
import pathlib

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from sqlalchemy import text

SCHEMA_SQL = (pathlib.Path(__file__).parent / "omop_schema.sql").read_text()


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container once for the entire test session."""
    with PostgresContainer("postgres:18-alpine") as pg:
        dsn = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")

        async def _setup():
            conn = await asyncpg.connect(dsn)
            await conn.execute(SCHEMA_SQL)
            await conn.close()

        asyncio.run(_setup())
        yield pg


@pytest.fixture(scope="session")
def async_engine(postgres_container):
    url = postgres_container.get_connection_url()
    async_url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    engine = create_async_engine(async_url, echo=False)
    return engine


@pytest.fixture(scope="session")
def session_factory(async_engine):
    return async_sessionmaker(
        bind=async_engine, expire_on_commit=False, class_=AsyncSession
    )


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(session_factory):
    """
    Provide a database session that rolls back after each test
    """
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def patch_db_settings(db_session, monkeypatch):
    # Patch settings
    monkeypatch.setattr("src.config.Settings.CDM_SCHEMA", "omop")
    monkeypatch.setattr("src.config.Settings.CANDIG_SCHEMA", "candig")

    async def mock_db_session():
        yield db_session

    monkeypatch.setattr(
        "src.api.phenopacket_operations.get_db_session", mock_db_session
    )


async def insert_concept(session, concept_id, name, vocabulary_id="SNOMED", code=None):

    code = code or str(concept_id)
    await session.execute(
        text("""
            INSERT INTO omop.concept (concept_id, concept_name, domain_id, vocabulary_id, concept_class_id, concept_code)
            VALUES (:id, :name, 'Observation', :vocab, 'Clinical Finding', :code)
            ON CONFLICT (concept_id) DO NOTHING
        """),
        {"id": concept_id, "name": name, "vocab": vocabulary_id, "code": code},
    )
