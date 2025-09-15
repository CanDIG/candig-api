"""
Database Setup

This module sets up database
"""

import asyncpg
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from .db_add_table import Base
from ..config import settings

from candigv2_logging.logging import CanDIGLogger  # type: ignore

logger = CanDIGLogger(__file__)

async def create_tables_async():
    """
    Create database schemas and tables from models
    """
    conn = None
    try:
        logger.info("Attempting to connect to the database for schema setup...")
        conn = await asyncpg.connect(dsn=settings.DATABASE_URI)
        dialect = postgresql.asyncpg.dialect()
        logger.info("Verifying and creating table schemas...")

        # Create the schema if it doesn't exist
        schema_exists_query = f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{settings.CANDIG_SCHEMA}'"
        if await conn.fetchval(schema_exists_query) is None:
            logger.info(f"  - Schema '{settings.CANDIG_SCHEMA}' does not exist. Creating...")
            await conn.execute(f"CREATE SCHEMA {settings.CANDIG_SCHEMA}")
            logger.info(f"  - Schema '{settings.CANDIG_SCHEMA}' created successfully.")
        else:
            logger.info(f"  - Schema '{settings.CANDIG_SCHEMA}' already exists. Skipping.")

        # Use Base.metadata.sorted_tables to ensure correct order
        for table in Base.metadata.sorted_tables:
            schema_name = table.schema or settings.CANDIG_SCHEMA
            table_exists_query = f"SELECT to_regclass('{schema_name}.{table.name}')"

            if await conn.fetchval(table_exists_query) is None:
                logger.info(
                    f"  - Table '{schema_name}.{table.name}' does not exist. Creating..."
                )

                # Generate the "CREATE TABLE" statement using SQLAlchemy's DDL constructs
                create_ddl = CreateTable(table).compile(dialect=dialect)
                await conn.execute(str(create_ddl))

                logger.info(f"  - Table '{schema_name}.{table.name}' created successfully.")
            else:
                logger.info(
                    f"  - Table '{schema_name}.{table.name}' already exists. Skipping."
                )
        logger.info("Database schema setup complete!")
    except (
        asyncpg.exceptions.CannotConnectNowError,
        ConnectionRefusedError,
        OSError,
    ) as e:
        logger.error("FATAL: Could not connect to database for setup.")
        logger.error(f"Error: {e}")
        raise
    except Exception as e:
        logger.error(f"FATAL: An error occurred during table creation: {e}")
        raise
    finally:
        if conn:
            await conn.close()
            logger.info("Setup connection closed.")