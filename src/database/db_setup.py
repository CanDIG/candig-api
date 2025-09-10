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

async def create_tables():
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

async def update_person_table():
    """
    Update person_id to use IDENTITY (auto-increment) and drop all FK constraints
    """
    conn = None
    try:
        conn = await asyncpg.connect(dsn=settings.DATABASE_URI)
        
        schema_name = settings.CDM_SCHEMA
        table_name = "person"
        
        table_exists_query = f"SELECT to_regclass('{schema_name}.{table_name}')"
        if await conn.fetchval(table_exists_query) is None:
            logger.warning(f"Table '{schema_name}.{table_name}' does not exist. Skipping identity update.")
            return
        
        # Get all foreign key constraints on the person table
        fk_constraints_query = """
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_schema = $1 AND table_name = $2 AND constraint_type = 'FOREIGN KEY'
        """
        fk_constraints = await conn.fetch(fk_constraints_query, schema_name, table_name)
        
        # Drop all foreign key constraints
        if fk_constraints:
            logger.info(f"Found {len(fk_constraints)} foreign key constraints to drop...")
            for constraint in fk_constraints:
                constraint_name = constraint['constraint_name']
                drop_fk_query = f"ALTER TABLE {schema_name}.{table_name} DROP CONSTRAINT {constraint_name}"
                try:
                    await conn.execute(drop_fk_query)
                    logger.info(f"Dropped FK constraint: {constraint_name}")
                except asyncpg.exceptions.PostgresError as e:
                    logger.warning(f"Failed to drop FK constraint {constraint_name}: {e}")
        else:
            logger.info("No foreign key constraints found on person table.")
        
        # Check if person_id column already has identity
        identity_check_query = """
        SELECT is_identity 
        FROM information_schema.columns 
        WHERE table_schema = $1 AND table_name = $2 AND column_name = 'person_id'
        """
        is_identity = await conn.fetchval(identity_check_query, schema_name, table_name)
        
        if is_identity == 'YES':
            logger.info(f"Column person_id in {schema_name}.{table_name} already has identity. Skipping identity update.")
            return
        
        logger.info(f"Updating person_id column in {schema_name}.{table_name} to use IDENTITY...")
        alter_queries = [
            # First, drop the default constraint if it exists
            f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN person_id DROP DEFAULT",
            # Add identity to the existing column
            f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN person_id ADD GENERATED ALWAYS AS IDENTITY"
        ]
        
        for query in alter_queries:
            try:
                await conn.execute(query)
                logger.info(f"Executed: {query}")
            except asyncpg.exceptions.PostgresError as e:
                # If dropping default fails (no default exists), that's okay
                if "does not exist" in str(e) and "DROP DEFAULT" in query:
                    logger.info("No default constraint to drop, continuing...")
                    continue
                else:
                    raise
        
        logger.info(f"Successfully updated person_id column to use IDENTITY and dropped all FK constraints")
        
    except (
        asyncpg.exceptions.CannotConnectNowError,
        ConnectionRefusedError,
        OSError,
    ) as e:
        logger.error("FATAL: Could not connect to database for person_id update.")
        logger.error(f"Error: {e}")
        raise
    except Exception as e:
        logger.error(f"FATAL: An error occurred during person_id identity update: {e}")
        raise
    finally:
        if conn:
            await conn.close()