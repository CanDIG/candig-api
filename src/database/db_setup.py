"""
Database Setup and Configuration

This module handles database setup and applies customizations
to the OMOP CDM schema:

- Auto-increment IDs for primary keys
- Extended VARCHAR limits (50 to 200) for source_value columns
- CASCADE DELETE on foreign keys for automatic cleanup of related data
"""

# import asyncpg
# from candigv2_logging.logging import CanDIGLogger
# from sqlalchemy.dialects import postgresql
# from sqlalchemy.schema import CreateTable

# from ..config import settings
# # from .db_add_tables import Base

# logger = CanDIGLogger(__file__)


# async def create_tables():
#     """
#     Create database schemas and tables from models
#     """
#     conn = None
#     try:
#         logger.info("Attempting to connect to the database for schema setup...")
#         conn = await asyncpg.connect(dsn=settings.DATABASE_URI)
#         dialect = postgresql.asyncpg.dialect()
#         logger.info("Verifying and creating table schemas...")

#         # Create the schema if it doesn't exist
#         schema_exists_query = f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{settings.CANDIG_SCHEMA}'"
#         if await conn.fetchval(schema_exists_query) is None:
#             logger.info(
#                 f"  - Schema '{settings.CANDIG_SCHEMA}' does not exist. Creating..."
#             )
#             await conn.execute(f"CREATE SCHEMA {settings.CANDIG_SCHEMA}")
#             logger.info(f"  - Schema '{settings.CANDIG_SCHEMA}' created successfully.")
#         else:
#             logger.info(
#                 f"  - Schema '{settings.CANDIG_SCHEMA}' already exists. Skipping."
#             )

#         # Use Base.metadata.sorted_tables to ensure correct order
#         for table in Base.metadata.sorted_tables:
#             schema_name = table.schema or settings.CANDIG_SCHEMA
#             table_exists_query = f"SELECT to_regclass('{schema_name}.{table.name}')"

#             if await conn.fetchval(table_exists_query) is None:
#                 logger.info(
#                     f"  - Table '{schema_name}.{table.name}' does not exist. Creating..."
#                 )

#                 # Generate the "CREATE TABLE" statement using SQLAlchemy's DDL constructs
#                 create_ddl = CreateTable(table).compile(dialect=dialect)
#                 await conn.execute(str(create_ddl))

#                 logger.info(
#                     f"  - Table '{schema_name}.{table.name}' created successfully."
#                 )
#             else:
#                 logger.info(
#                     f"  - Table '{schema_name}.{table.name}' already exists. Skipping."
#                 )
#         logger.info("Database schema setup complete!")
#     except (
#         asyncpg.exceptions.CannotConnectNowError,
#         ConnectionRefusedError,
#         OSError,
#     ) as e:
#         logger.error("FATAL: Could not connect to database for setup.")
#         logger.error(f"Error: {e}")
#         raise
#     except Exception as e:
#         logger.error(f"FATAL: An error occurred during table creation: {e}")
#         raise
#     finally:
#         if conn:
#             await conn.close()


# async def update_tables_identity():
#     """
#     Update tables to use IDENTITY (auto-increment)
#     """
#     conn = None
#     try:
#         conn = await asyncpg.connect(dsn=settings.DATABASE_URI)

#         schema_name = settings.CDM_SCHEMA

#         # Tables and columns to update
#         tables_to_update = [
#             {"table": "person", "column": "person_id"},
#             {"table": "observation", "column": "observation_id"},
#             {"table": "condition_occurrence", "column": "condition_occurrence_id"},
#             {"table": "episode", "column": "episode_id"},
#             {"table": "measurement", "column": "measurement_id"},
#             {"table": "specimen", "column": "specimen_id"},
#             {"table": "procedure_occurrence", "column": "procedure_occurrence_id"},
#             {"table": "drug_exposure", "column": "drug_exposure_id"},
#             {"table": "visit_occurrence", "column": "visit_occurrence_id"},
#         ]

#         for table_info in tables_to_update:
#             table_name = table_info["table"]
#             column_name = table_info["column"]

#             table_exists_query = f"SELECT to_regclass('{schema_name}.{table_name}')"
#             if await conn.fetchval(table_exists_query) is None:
#                 logger.warning(
#                     f"Table '{schema_name}.{table_name}' does not exist. Skipping identity update."
#                 )
#                 continue

#             # Check if column already has identity
#             identity_check_query = """
#             SELECT is_identity 
#             FROM information_schema.columns 
#             WHERE table_schema = $1 AND table_name = $2 AND column_name = $3
#             """
#             is_identity = await conn.fetchval(
#                 identity_check_query, schema_name, table_name, column_name
#             )

#             if is_identity == "YES":
#                 logger.info(
#                     f"Column {column_name} in {schema_name}.{table_name} already has identity. Skipping identity update."
#                 )
#                 continue

#             logger.info(
#                 f"Updating {column_name} column in {schema_name}.{table_name} to use IDENTITY..."
#             )
#             alter_queries = [
#                 # First, drop the default constraint if it exists
#                 f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN {column_name} DROP DEFAULT",
#                 # Add identity to the existing column
#                 f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN {column_name} ADD GENERATED ALWAYS AS IDENTITY",
#             ]

#             for query in alter_queries:
#                 try:
#                     await conn.execute(query)
#                     logger.info(f"Executed: {query}")
#                 except asyncpg.exceptions.PostgresError as e:
#                     if "does not exist" in str(e) and "DROP DEFAULT" in query:
#                         logger.info("No default constraint to drop, continuing...")
#                         continue
#                     else:
#                         raise

#             logger.info(f"Successfully updated {column_name} column to use IDENTITY")

#     except (
#         asyncpg.exceptions.CannotConnectNowError,
#         ConnectionRefusedError,
#         OSError,
#     ) as e:
#         logger.error("FATAL: Could not connect to database for identity update.")
#         logger.error(f"Error: {e}")
#         raise
#     except Exception as e:
#         logger.error(f"FATAL: An error occurred during identity update: {e}")
#         raise
#     finally:
#         if conn:
#             await conn.close()


# async def update_column_limits():
#     """
#     Update column character limits across tables
#     """
#     conn = None
#     try:
#         conn = await asyncpg.connect(dsn=settings.DATABASE_URI)

#         schema_name = settings.CDM_SCHEMA

#         # Tables and columns to update with their new limits
#         columns_to_update = [
#             {"table": "observation", "column": "value_source_value", "new_limit": 200},
#             {
#                 "table": "procedure_occurrence",
#                 "column": "procedure_source_value",
#                 "new_limit": 200,
#             },
#             {
#                 "table": "procedure_occurrence",
#                 "column": "modifier_source_value",
#                 "new_limit": 200,
#             },
#             {
#                 "table": "measurement",
#                 "column": "measurement_source_value",
#                 "new_limit": 200,
#             },
#             # TODO: find all the value source to increase limit
#         ]

#         for column_info in columns_to_update:
#             table_name = column_info["table"]
#             column_name = column_info["column"]
#             new_limit = column_info["new_limit"]

#             table_exists_query = f"SELECT to_regclass('{schema_name}.{table_name}')"
#             if await conn.fetchval(table_exists_query) is None:
#                 logger.warning(
#                     f"Table '{schema_name}.{table_name}' does not exist. Skipping column limit update."
#                 )
#                 continue

#             # Check current column definition
#             column_info_query = """
#             SELECT character_maximum_length, data_type
#             FROM information_schema.columns 
#             WHERE table_schema = $1 AND table_name = $2 AND column_name = $3
#             """
#             column_data = await conn.fetchrow(
#                 column_info_query, schema_name, table_name, column_name
#             )

#             if not column_data:
#                 logger.warning(
#                     f"Column '{column_name}' does not exist in {schema_name}.{table_name}. Skipping limit update."
#                 )
#                 continue

#             current_length = column_data["character_maximum_length"]
#             data_type = column_data["data_type"]

#             if current_length == new_limit:
#                 logger.info(
#                     f"Column {column_name} in {schema_name}.{table_name} already has character limit of {new_limit}. Skipping update."
#                 )
#                 continue

#             if data_type not in ["character varying", "varchar", "character"]:
#                 logger.warning(
#                     f"Column {column_name} is not a character type (current: {data_type}). Skipping limit update."
#                 )
#                 continue

#             logger.info(
#                 f"Updating {column_name} column in {schema_name}.{table_name} from limit {current_length} to {new_limit}..."
#             )

#             # Alter the column to update the character limit
#             alter_query = f"ALTER TABLE {schema_name}.{table_name} ALTER COLUMN {column_name} TYPE VARCHAR({new_limit})"

#             await conn.execute(alter_query)
#             logger.info(f"Executed: {alter_query}")
#             logger.info(
#                 f"Successfully updated {column_name} column character limit to {new_limit}"
#             )

#     except (
#         asyncpg.exceptions.CannotConnectNowError,
#         ConnectionRefusedError,
#         OSError,
#     ) as e:
#         logger.error("FATAL: Could not connect to database for column limit update.")
#         logger.error(f"Error: {e}")
#         raise
#     except Exception as e:
#         logger.error(f"FATAL: An error occurred during column limit update: {e}")
#         raise
#     finally:
#         if conn:
#             await conn.close()


# async def update_FK_delete_cascade():
#     """
#     Update foreign key constraints to CASCADE on DELETE
#     """
#     conn = None
#     try:
#         conn = await asyncpg.connect(dsn=settings.DATABASE_URI)
#         schema_name = settings.CDM_SCHEMA

#         fk_updates = [
#             {
#                 "table": "observation",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "death",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "condition_occurrence",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "episode",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "episode_event",
#                 "fk_column": "episode_id",
#                 "referenced_table": "episode",
#                 "referenced_column": "episode_id",
#             },
#             {
#                 "table": "measurement",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "visit_occurrence",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "specimen",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "procedure_occurrence",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "drug_exposure",
#                 "fk_column": "person_id",
#                 "referenced_table": "person",
#                 "referenced_column": "person_id",
#             },
#             {
#                 "table": "fact_relationship",
#                 "fk_column": "fact_id_1",
#                 "referenced_table": "episode",
#                 "referenced_column": "episode_id",
#             },
#             {
#                 "table": "fact_relationship",
#                 "fk_column": "fact_id_2",
#                 "referenced_table": "episode",
#                 "referenced_column": "episode_id",
#             },
#         ]

#         for fk_info in fk_updates:
#             table = fk_info["table"]
#             fk_column = fk_info["fk_column"]
#             ref_table = fk_info["referenced_table"]
#             ref_column = fk_info["referenced_column"]
#             new_constraint_name = f"fk_{table}_{fk_column}"

#             # 1. Find the name of any existing FK on this specific column
#             find_fk_query = """
#             SELECT tc.constraint_name
#             FROM information_schema.table_constraints AS tc 
#             JOIN information_schema.key_column_usage AS kcu
#               ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
#             WHERE tc.constraint_type = 'FOREIGN KEY' 
#               AND tc.table_schema = $1
#               AND tc.table_name = $2 
#               AND kcu.column_name = $3;
#             """
#             existing_fk_name = await conn.fetchval(
#                 find_fk_query, schema_name, table, fk_column
#             )

#             # 2. If an old FK exists, drop it
#             if existing_fk_name:
#                 logger.info(
#                     f"Found existing constraint '{existing_fk_name}'. Dropping it."
#                 )
#                 drop_fk_query = f'ALTER TABLE "{schema_name}"."{table}" DROP CONSTRAINT "{existing_fk_name}"'
#                 await conn.execute(drop_fk_query)

#             # 3. Add the new, correctly defined foreign key constraint
#             logger.info(
#                 f"Adding constraint '{new_constraint_name}' with ON DELETE CASCADE."
#             )
#             add_fk_query = f"""
#             ALTER TABLE "{schema_name}"."{table}"
#             ADD CONSTRAINT "{new_constraint_name}"
#             FOREIGN KEY ("{fk_column}")
#             REFERENCES "{schema_name}"."{ref_table}" ("{ref_column}")
#             ON DELETE CASCADE
#             """
#             await conn.execute(add_fk_query)

#         logger.info("Foreign key cascade update complete!")

#     except Exception as e:
#         logger.error(f"FATAL: An error occurred during FK cascade update: {e}")
#         raise
#     finally:
#         if conn:
#             await conn.close()
