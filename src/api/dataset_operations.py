"""
Provides CRUD operations for dataset like LIST, GET, CREATE, UPDATE, DELETE
"""

import json
from datetime import datetime

from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.database.db_operations import get_db_session

from ..config import settings  # Import settings

logger = CanDIGLogger(__file__)


# --- List datasets Endpoint ---
async def list_all():
    """Lists all datasets"""

    stmt = text(f"""
            SELECT 
                d.id,
                COUNT(pid.person_id) AS person_count
            FROM {settings.CANDIG_SCHEMA}.dataset d
            LEFT OUTER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid 
                ON d.id = pid.dataset_id
            GROUP BY d.id
            ORDER BY d.id
        """)

    async for session in get_db_session():
        try:
            result = await session.execute(stmt)
            records = result.all()

            datasets = [
                {
                    "id": record.id,
                    "count": record.person_count or 0,
                }
                for record in records
            ]

            return datasets, 200
        except Exception as e:
            logger.error(f"Database Error in dataset.list_all: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail=f"An error occurred while fetching datasets from the database. Details: {e}",
            )


# --- Create dataset Endpoint ---
async def create(body: dict):
    """
    Create a new dataset with new person(s)
    """
    async for session in get_db_session():
        try:
            dataset_id = body["id"]
            info = body.get("info", {})
            persons = body.get("persons", [])
            insert_dataset_sql = text(f"""
                INSERT INTO {settings.CANDIG_SCHEMA}.dataset (id, info)
                VALUES (:id, :info)
            """)

            await session.execute(
                insert_dataset_sql, {"id": dataset_id, "info": json.dumps(info)}
            )

            # insert persons if included
            if persons:
                for person_data in persons:
                    birth_datetime = None
                    if person_data.get("birth_datetime"):
                        birth_datetime = datetime.fromisoformat(
                            person_data["birth_datetime"].replace("Z", "+00:00")
                        )

                    insert_person_sql = text(f"""
                        INSERT INTO {settings.CDM_SCHEMA}.person (
                            gender_concept_id, year_of_birth, month_of_birth, 
                            day_of_birth, birth_datetime, race_concept_id, ethnicity_concept_id,
                            location_id, provider_id, care_site_id, person_source_value,
                            gender_source_value, gender_source_concept_id, race_source_value,
                            race_source_concept_id, ethnicity_source_value, ethnicity_source_concept_id
                        ) VALUES (
                            :gender_concept_id, :year_of_birth, :month_of_birth,
                            :day_of_birth, :birth_datetime, :race_concept_id, :ethnicity_concept_id,
                            :location_id, :provider_id, :care_site_id, :person_source_value,
                            :gender_source_value, :gender_source_concept_id, :race_source_value,
                            :race_source_concept_id, :ethnicity_source_value, :ethnicity_source_concept_id
                        ) RETURNING person_id
                    """)

                    person_params = {
                        "gender_concept_id": person_data.get("gender_concept_id"),
                        "year_of_birth": person_data.get("year_of_birth"),
                        "month_of_birth": person_data.get("month_of_birth"),
                        "day_of_birth": person_data.get("day_of_birth"),
                        "birth_datetime": birth_datetime,
                        "race_concept_id": person_data.get("race_concept_id"),
                        "ethnicity_concept_id": person_data.get("ethnicity_concept_id"),
                        "location_id": person_data.get("location_id"),
                        "provider_id": person_data.get("provider_id"),
                        "care_site_id": person_data.get("care_site_id"),
                        "person_source_value": person_data.get("person_source_value"),
                        "gender_source_value": person_data.get("gender_source_value"),
                        "gender_source_concept_id": person_data.get(
                            "gender_source_concept_id"
                        ),
                        "race_source_value": person_data.get("race_source_value"),
                        "race_source_concept_id": person_data.get(
                            "race_source_concept_id"
                        ),
                        "ethnicity_source_value": person_data.get(
                            "ethnicity_source_value"
                        ),
                        "ethnicity_source_concept_id": person_data.get(
                            "ethnicity_source_concept_id"
                        ),
                    }

                    # Get the auto-generated person_id from the db
                    result = await session.execute(insert_person_sql, person_params)
                    person_id = result.scalar_one()

                    # Link person to dataset
                    insert_person_dataset_sql = text(f"""
                        INSERT INTO {settings.CANDIG_SCHEMA}.person_in_dataset (person_id, dataset_id)
                        VALUES (:person_id, :dataset_id)
                    """)
                    await session.execute(
                        insert_person_dataset_sql,
                        {"person_id": person_id, "dataset_id": dataset_id},
                    )

            await session.commit()

            # Return the created dataset
            dataset = {
                "id": dataset_id,
                "info": info,
            }
            return dataset, 201

        except ProblemException:
            await session.rollback()
            raise
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Database Integrity Error in dataset.create: {str(e)}")
            extra_details = ""
            if "foreignkeyviolationerror" in str(e).lower():
                extra_details += "Foreign key invalid.\n"
            if "uniqueviolationerror" in str(e).lower():
                extra_details += "Value should be unique.\n"

            error_msg = str(e)
            if "DETAIL:" in error_msg:
                error_msg = error_msg.split("DETAIL:", 1)[1].split("\n", 1)[0].strip()
            raise ProblemException(
                status=400,
                title="Database Integrity Error",
                detail=f"Violation of database integrity constraints.\n{extra_details}Error details: {error_msg}",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in dataset.create: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while creating the dataset in the database",
            )


# --- Get dataset Endpoint ---
async def get_by_id(id: str):
    """Gets a single dataset"""

    stmt = text(f"""
    SELECT 
        d.id,
        COUNT(pid.person_id) AS person_count
    FROM {settings.CANDIG_SCHEMA}.dataset d
    LEFT OUTER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid 
        ON d.id = pid.dataset_id
    WHERE d.id = :id
    GROUP BY d.id
""")

    async for session in get_db_session():
        try:
            result = await session.execute(stmt, {"id": id})
            record = result.one_or_none()

            if not record:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            dataset = {
                "id": record.id,
                "count": record.person_count or 0,
            }

            return dataset, 200
        except ProblemException:
            raise
        except Exception as e:
            logger.error(f"Database Error in dataset.get_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching the dataset from the database.",
            )


# --- Update dataset Endpoint ---
async def put_by_id(id: str, body: dict):
    """
    Update an existing dataset with person(s)
    """
    async for session in get_db_session():
        try:
            # Check if dataset exists and get current data
            check_dataset_sql = text(f"""
                SELECT id, info FROM {settings.CANDIG_SCHEMA}.dataset 
                WHERE id = :id
            """)
            result = await session.execute(check_dataset_sql, {"id": id})
            existing_dataset = result.one_or_none()

            if not existing_dataset:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            # Update dataset fields
            info = body.get("info", {})

            update_dataset_sql = text(f"""
                UPDATE {settings.CANDIG_SCHEMA}.dataset 
                SET info = :info
                WHERE id = :id
            """)
            await session.execute(
                update_dataset_sql, {"id": id, "info": json.dumps(info)}
            )

            # Get all existing person_ids for this dataset
            existing_persons_sql = text(f"""
                SELECT person_id FROM {settings.CANDIG_SCHEMA}.person_in_dataset
                WHERE dataset_id = :dataset_id
            """)
            existing_persons_result = await session.execute(
                existing_persons_sql, {"dataset_id": id}
            )
            existing_person_ids = {row[0] for row in existing_persons_result.fetchall()}

            # Handle persons if provided
            persons = body.get("persons", [])
            provided_person_ids = set()

            if persons:
                for person_data in persons:
                    person_id = person_data.get("person_id")

                    if person_id:
                        provided_person_ids.add(person_id)

                        # Check if person exists before updating
                        check_person_exists_sql = text(f"""
                            SELECT 1 FROM {settings.CDM_SCHEMA}.person WHERE person_id = :person_id LIMIT 1
                        """)
                        person_exists = await session.execute(
                            check_person_exists_sql, {"person_id": person_id}
                        )

                        if not person_exists.fetchone():
                            raise ProblemException(
                                status=400,
                                title="Bad Request",
                                detail=f"Person with id {person_id} does not exist",
                            )

                        # Update existing person
                        birth_datetime = None
                        if person_data.get("birth_datetime"):
                            birth_datetime = datetime.fromisoformat(
                                person_data["birth_datetime"].replace("Z", "+00:00")
                            )

                        update_person_sql = text(f"""
                            UPDATE {settings.CDM_SCHEMA}.person SET
                                gender_concept_id = :gender_concept_id,
                                year_of_birth = :year_of_birth,
                                month_of_birth = :month_of_birth,
                                day_of_birth = :day_of_birth,
                                birth_datetime = :birth_datetime,
                                race_concept_id = :race_concept_id,
                                ethnicity_concept_id = :ethnicity_concept_id,
                                location_id = :location_id,
                                provider_id = :provider_id,
                                care_site_id = :care_site_id,
                                person_source_value = :person_source_value,
                                gender_source_value = :gender_source_value,
                                gender_source_concept_id = :gender_source_concept_id,
                                race_source_value = :race_source_value,
                                race_source_concept_id = :race_source_concept_id,
                                ethnicity_source_value = :ethnicity_source_value,
                                ethnicity_source_concept_id = :ethnicity_source_concept_id
                            WHERE person_id = :person_id
                        """)

                        person_params = {
                            "person_id": person_id,
                            "gender_concept_id": person_data.get("gender_concept_id"),
                            "year_of_birth": person_data.get("year_of_birth"),
                            "month_of_birth": person_data.get("month_of_birth"),
                            "day_of_birth": person_data.get("day_of_birth"),
                            "birth_datetime": birth_datetime,
                            "race_concept_id": person_data.get("race_concept_id"),
                            "ethnicity_concept_id": person_data.get(
                                "ethnicity_concept_id"
                            ),
                            "location_id": person_data.get("location_id"),
                            "provider_id": person_data.get("provider_id"),
                            "care_site_id": person_data.get("care_site_id"),
                            "person_source_value": person_data.get(
                                "person_source_value"
                            ),
                            "gender_source_value": person_data.get(
                                "gender_source_value"
                            ),
                            "gender_source_concept_id": person_data.get(
                                "gender_source_concept_id"
                            ),
                            "race_source_value": person_data.get("race_source_value"),
                            "race_source_concept_id": person_data.get(
                                "race_source_concept_id"
                            ),
                            "ethnicity_source_value": person_data.get(
                                "ethnicity_source_value"
                            ),
                            "ethnicity_source_concept_id": person_data.get(
                                "ethnicity_source_concept_id"
                            ),
                        }

                        await session.execute(update_person_sql, person_params)

                        # Link person to this dataset
                        check_link_sql = text(f"""
                            SELECT 1 FROM {settings.CANDIG_SCHEMA}.person_in_dataset 
                            WHERE person_id = :person_id AND dataset_id = :dataset_id LIMIT 1
                        """)
                        link_exists = await session.execute(
                            check_link_sql, {"person_id": person_id, "dataset_id": id}
                        )

                        if not link_exists.fetchone():
                            insert_person_dataset_sql = text(f"""
                                INSERT INTO {settings.CANDIG_SCHEMA}.person_in_dataset (person_id, dataset_id)
                                VALUES (:person_id, :dataset_id)
                            """)
                            await session.execute(
                                insert_person_dataset_sql,
                                {"person_id": person_id, "dataset_id": id},
                            )

                    else:
                        # Create new person
                        birth_datetime = None
                        if person_data.get("birth_datetime"):
                            birth_datetime = datetime.fromisoformat(
                                person_data["birth_datetime"].replace("Z", "+00:00")
                            )

                        insert_person_sql = text(f"""
                            INSERT INTO {settings.CDM_SCHEMA}.person (
                                gender_concept_id, year_of_birth, month_of_birth, 
                                day_of_birth, birth_datetime, race_concept_id, ethnicity_concept_id,
                                location_id, provider_id, care_site_id, person_source_value,
                                gender_source_value, gender_source_concept_id, race_source_value,
                                race_source_concept_id, ethnicity_source_value, ethnicity_source_concept_id
                            ) VALUES (
                                :gender_concept_id, :year_of_birth, :month_of_birth,
                                :day_of_birth, :birth_datetime, :race_concept_id, :ethnicity_concept_id,
                                :location_id, :provider_id, :care_site_id, :person_source_value,
                                :gender_source_value, :gender_source_concept_id, :race_source_value,
                                :race_source_concept_id, :ethnicity_source_value, :ethnicity_source_concept_id
                            ) RETURNING person_id
                        """)

                        person_params = {
                            "gender_concept_id": person_data.get("gender_concept_id"),
                            "year_of_birth": person_data.get("year_of_birth"),
                            "month_of_birth": person_data.get("month_of_birth"),
                            "day_of_birth": person_data.get("day_of_birth"),
                            "birth_datetime": birth_datetime,
                            "race_concept_id": person_data.get("race_concept_id"),
                            "ethnicity_concept_id": person_data.get(
                                "ethnicity_concept_id"
                            ),
                            "location_id": person_data.get("location_id"),
                            "provider_id": person_data.get("provider_id"),
                            "care_site_id": person_data.get("care_site_id"),
                            "person_source_value": person_data.get(
                                "person_source_value"
                            ),
                            "gender_source_value": person_data.get(
                                "gender_source_value"
                            ),
                            "gender_source_concept_id": person_data.get(
                                "gender_source_concept_id"
                            ),
                            "race_source_value": person_data.get("race_source_value"),
                            "race_source_concept_id": person_data.get(
                                "race_source_concept_id"
                            ),
                            "ethnicity_source_value": person_data.get(
                                "ethnicity_source_value"
                            ),
                            "ethnicity_source_concept_id": person_data.get(
                                "ethnicity_source_concept_id"
                            ),
                        }

                        # Get the auto-generated person_id from the db
                        result = await session.execute(insert_person_sql, person_params)
                        new_person_id = result.scalar_one()
                        provided_person_ids.add(new_person_id)

                        # Link new person to dataset
                        insert_person_dataset_sql = text(f"""
                            INSERT INTO {settings.CANDIG_SCHEMA}.person_in_dataset (person_id, dataset_id)
                            VALUES (:person_id, :dataset_id)
                        """)
                        await session.execute(
                            insert_person_dataset_sql,
                            {"person_id": new_person_id, "dataset_id": id},
                        )

            # Delete persons that exist in the database but not in the request body
            persons_to_delete = existing_person_ids - provided_person_ids

            if persons_to_delete:
                # Delete from person_in_dataset table first
                delete_person_dataset_sql = text(f"""
                    DELETE FROM {settings.CANDIG_SCHEMA}.person_in_dataset 
                    WHERE person_id = ANY(:person_ids) AND dataset_id = :dataset_id
                """)
                await session.execute(
                    delete_person_dataset_sql,
                    {"person_ids": list(persons_to_delete), "dataset_id": id},
                )

                # Delete the persons from omop.person table
                delete_persons_sql = text(f"""
                    DELETE FROM {settings.CDM_SCHEMA}.person 
                    WHERE person_id = ANY(:person_ids)
                """)
                await session.execute(
                    delete_persons_sql, {"person_ids": list(persons_to_delete)}
                )

            await session.commit()

            # Return the updated dataset
            dataset = {
                "id": id,
                "info": info,
            }
            return dataset, 200

        except ProblemException:
            await session.rollback()
            raise
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Database Integrity Error in dataset.put_by_id: {str(e)}")
            extra_details = ""
            if "foreignkeyviolationerror" in str(e).lower():
                extra_details += "Foreign key invalid.\n"
            if "uniqueviolationerror" in str(e).lower():
                extra_details += "Value should be unique.\n"

            error_msg = str(e)
            if "DETAIL:" in error_msg:
                error_msg = error_msg.split("DETAIL:", 1)[1].split("\n", 1)[0].strip()
            raise ProblemException(
                status=400,
                title="Database Integrity Error",
                detail=f"Violation of database integrity constraints.\n{extra_details}Error details: {error_msg}",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in dataset.put_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while updating the dataset in the database.",
            )


# --- Get dataset info Endpoint ---
async def get_info(id: str):
    """Gets dataset info"""

    stmt = text(f"""
        SELECT * FROM {settings.CANDIG_SCHEMA}.dataset 
        WHERE id = :id
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(stmt, {"id": id})
            record = result.one_or_none()

            if not record:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            info = record.info
            if info is None:
                info = {}
            elif isinstance(info, str):
                info = json.loads(info)

            return info, 200
        except ProblemException:
            raise
        except Exception as e:
            logger.error(f"Database Error in dataset.get_info: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail=f"An error occurred while fetching the dataset from the database: {e}",
            )


# --- Update dataset Endpoint ---
async def patch_info(id: str, body: dict):
    """
    Updates dataset info
    """

    async for session in get_db_session():
        try:
            # Check if dataset exists
            check_dataset_sql = text(f"""
                SELECT id FROM {settings.CANDIG_SCHEMA}.dataset 
                WHERE id = :id
            """)
            result = await session.execute(check_dataset_sql, {"id": id})
            existing_dataset = result.one_or_none()

            if not existing_dataset:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            # Update dataset info
            info = body if body else {}
            update_info_sql = text(f"""
                UPDATE {settings.CANDIG_SCHEMA}.dataset 
                SET info = :info
                WHERE id = :id
            """)
            await session.execute(update_info_sql, {"id": id, "info": json.dumps(info)})
            await session.commit()

            # Return the updated info
            if isinstance(info, str):
                info = json.loads(info)

            return info, 200

        except ProblemException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in dataset.patch_info: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while updating the dataset info in the database.",
            )


# --- Get datasets stats Endpoint ---
async def statistics():
    """
    Gets summary statistics for all datasets
    """

    # Get total dataset count and person counts per dataset
    stmt = text(f"""
    SELECT 
        d.id,
        COUNT(pid.person_id) AS person_count
    FROM {settings.CANDIG_SCHEMA}.dataset d
    LEFT OUTER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid 
        ON d.id = pid.dataset_id
    GROUP BY d.id
""")

    async for session in get_db_session():
        try:
            result = await session.execute(stmt)
            records = result.all()

            # Calculate statistics
            dataset_count = len(records)
            total_person_count = sum(record.person_count or 0 for record in records)
            # Build persons_per_dataset mapping
            persons_per_dataset = {
                str(record.id): record.person_count or 0 for record in records
            }

            stats = {
                "person_count": total_person_count,
                "dataset_count": dataset_count,
                "persons_per_dataset": persons_per_dataset,
            }

            return stats, 200
        except Exception as e:
            logger.error(f"Database Error in dataset.statistics: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching dataset statistics from the database.",
            )


# --- Get dataset stats Endpoint ---
async def statistics_by_id(id: str):
    """
    Gets summary statistics for a specific dataset
    """

    stmt = text(f"""
    SELECT 
        d.id,
        COUNT(pid.person_id) AS person_count
    FROM {settings.CANDIG_SCHEMA}.dataset d
    LEFT OUTER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid 
        ON d.id = pid.dataset_id
    WHERE d.id = :id
    GROUP BY d.id
""")

    async for session in get_db_session():
        try:
            result = await session.execute(stmt, {"id": id})
            record = result.one_or_none()

            if not record:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            stats = {"person_count": record.person_count or 0}

            return stats, 200
        except ProblemException:
            raise
        except Exception as e:
            logger.error(f"Database Error in dataset.statistics_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching dataset statistics from the database.",
            )


# --- Delete dataset Endpoint ---
async def delete_by_id(id: str):
    """
    Delete a dataset and all associated data.

    1. Deletes the dataset itself
    2. Removes person-dataset link from person_in_dataset
    3. Deletes all persons with its associated clinical data (treatments, events...) through FK
    """
    async for session in get_db_session():
        try:
            # Check if dataset exists
            check_dataset_sql = text(f"""
                SELECT id FROM {settings.CANDIG_SCHEMA}.dataset 
                WHERE id = :id
            """)
            result = await session.execute(check_dataset_sql, {"id": id})
            dataset_exists = result.one_or_none()

            if not dataset_exists:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with ID '{id}' not found.",
                )

            # Get all person_ids associated with this dataset
            get_persons_sql = text(f"""
                SELECT person_id FROM {settings.CANDIG_SCHEMA}.person_in_dataset
                WHERE dataset_id = :dataset_id
            """)
            person_result = await session.execute(get_persons_sql, {"dataset_id": id})
            person_ids = [row[0] for row in person_result.fetchall()]

            # Delete persons first if any exist
            # This also cascade to other tables through person_id
            if person_ids:
                delete_persons_sql = text(f"""
                    DELETE FROM {settings.CDM_SCHEMA}.person 
                    WHERE person_id = ANY(:person_ids)
                """)
                await session.execute(delete_persons_sql, {"person_ids": person_ids})

            # Finally delete the dataset
            delete_dataset_sql = text(f"""
                DELETE FROM {settings.CANDIG_SCHEMA}.dataset 
                WHERE id = :id
            """)
            await session.execute(delete_dataset_sql, {"id": id})
            await session.commit()

            return {
                "message": f"Dataset {id} and {len(person_ids)} associated person(s) deleted successfully."
            }, 200

        except ProblemException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in dataset.delete_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail=f"An error occurred while deleting the dataset: {str(e)}",
            )
