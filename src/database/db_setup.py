"""
Database Setup

This module sets up database
"""

import asyncio
import asyncpg
from sqlalchemy.schema import CreateTable, CreateSchema
from sqlalchemy.dialects import postgresql
from .db_add_table import Base
from ..config import settings


async def _create_tables_async():
    """
    Create database schemas and tables from models
    """
    conn = None
    try:
        conn = await asyncpg.connect(dsn=settings.DATABASE_URI)
        dialect = postgresql.asyncpg.dialect()
        print("Verifying and creating table schemas...")

        # Create the schema if it doesn't exist
        schema_exists_query = f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{settings.CANDIG_SCHEMA}'"
        if await conn.fetchval(schema_exists_query) is None:
            print(f"  - Schema '{settings.CANDIG_SCHEMA}' does not exist. Creating...")
            await conn.execute(f"CREATE SCHEMA {settings.CANDIG_SCHEMA}")
            print(f"  - Schema '{settings.CANDIG_SCHEMA}' created successfully.")
        else:
            print(f"  - Schema '{settings.CANDIG_SCHEMA}' already exists. Skipping.")

        # Use Base.metadata.sorted_tables to ensure correct order
        for table in Base.metadata.sorted_tables:
            schema_name = table.schema or settings.CANDIG_SCHEMA
            table_exists_query = f"SELECT to_regclass('{schema_name}.{table.name}')"

            if await conn.fetchval(table_exists_query) is None:
                print(
                    f"  - Table '{schema_name}.{table.name}' does not exist. Creating..."
                )

                # Generate the "CREATE TABLE" statement using SQLAlchemy's DDL constructs
                create_ddl = CreateTable(table).compile(dialect=dialect)
                await conn.execute(str(create_ddl))

                print(f"  - Table '{schema_name}.{table.name}' created successfully.")
            else:
                print(
                    f"  - Table '{schema_name}.{table.name}' already exists. Skipping."
                )

    except Exception as e:
        print(f"FATAL: An error occurred during table creation: {e}")
        raise
    finally:
        if conn:
            await conn.close()
            print("Setup connection closed.")


def create_database_tables():
    """Synchronous wrapper to run the async table creation."""
    try:
        print("Attempting to connect to the database...")
        asyncio.run(_create_tables_async())
        print("Database schema setup complete!")

    except (
        asyncpg.exceptions.CannotConnectNowError,
        ConnectionRefusedError,
        OSError,
    ) as e:
        print("FATAL: Could not connect to database.")
        print(f"Error: {e}")
        raise
