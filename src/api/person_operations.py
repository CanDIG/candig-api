"""
Provides CRUD operations for person like LIST, GET, CREATE, UPDATE, DELETE
"""
from connexion.exceptions import ProblemException
from sqlalchemy import text

from ..database.db_operations import get_db_session
from datetime import datetime
from ..config import settings
from candigv2_logging.logging import CanDIGLogger

logger = CanDIGLogger(__file__)

# --- List persons Endpoint ---
async def list(dataset_id: str):
    """Lists all person for a given dataset"""
    # TODO: implement authorize
    authorized = True
    if not authorized:
        stmt = text(f"""
                SELECT person_id 
                FROM {settings.CANDIG_SCHEMA}.person_in_dataset 
                WHERE dataset_id = :dataset_id
            """)

        async for session in get_db_session():
            try:
                result = await session.execute(stmt, {"dataset_id": dataset_id})
                person_ids = [row.person_id for row in result]

                return person_ids, 200
            except Exception as e:
                logger.error(f"Database Error in person.list: {str(e)}")
                raise ProblemException(
                    status=500,
                    title="Database Error",
                    detail="An error occurred while fetching person IDs from the database.",
                )
    else:
        raw_sql = text(f"""
            SELECT 
                p.person_id,
                p.gender_concept_id,
                p.year_of_birth,
                p.month_of_birth,
                p.day_of_birth,
                p.birth_datetime,
                p.race_concept_id,
                p.ethnicity_concept_id,
                p.location_id,
                p.provider_id,
                p.care_site_id,
                p.person_source_value,
                p.gender_source_value,
                p.gender_source_concept_id,
                p.race_source_value,
                p.race_source_concept_id,
                p.ethnicity_source_value,
                p.ethnicity_source_concept_id
            FROM {settings.CDM_SCHEMA}.person p
            INNER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid ON p.person_id = pid.person_id
            WHERE pid.dataset_id = :dataset_id
        """)

        async for session in get_db_session():
            try:
                result = await session.execute(raw_sql, {"dataset_id": dataset_id})
                persons = []

                for row in result:
                    person_dict = {
                        "person_id": row.person_id,
                        "gender_concept_id": row.gender_concept_id,
                        "year_of_birth": row.year_of_birth,
                        "month_of_birth": row.month_of_birth,
                        "day_of_birth": row.day_of_birth,
                        "birth_datetime": row.birth_datetime,
                        "race_concept_id": row.race_concept_id,
                        "ethnicity_concept_id": row.ethnicity_concept_id,
                        "location_id": row.location_id,
                        "provider_id": row.provider_id,
                        "care_site_id": row.care_site_id,
                        "person_source_value": row.person_source_value,
                        "gender_source_value": row.gender_source_value,
                        "gender_source_concept_id": row.gender_source_concept_id,
                        "race_source_value": row.race_source_value,
                        "race_source_concept_id": row.race_source_concept_id,
                        "ethnicity_source_value": row.ethnicity_source_value,
                        "ethnicity_source_concept_id": row.ethnicity_source_concept_id,
                    }
                    persons.append(person_dict)

                return persons, 200
            except Exception as e:
                logger.error(f"Database Error in person.list (detailed): {str(e)}")
                raise ProblemException(
                    status=500,
                    title="Database Error",
                    detail="An error occurred while fetching detailed person information from the database.",
                )

# --- Get person Endpoint ---
async def get_by_id(dataset_id: str, id: int):
    """Get a person by ID within a dataset."""
    raw_sql = raw_sql = text(f"""
        SELECT 
            p.person_id,
            p.gender_concept_id,
            p.year_of_birth,
            p.month_of_birth,
            p.day_of_birth,
            p.birth_datetime,
            p.race_concept_id,
            p.ethnicity_concept_id,
            p.location_id,
            p.provider_id,
            p.care_site_id,
            p.person_source_value,
            p.gender_source_value,
            p.gender_source_concept_id,
            p.race_source_value,
            p.race_source_concept_id,
            p.ethnicity_source_value,
            p.ethnicity_source_concept_id
        FROM {settings.CDM_SCHEMA}.person p
        INNER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid ON p.person_id = pid.person_id
        WHERE pid.dataset_id = :dataset_id AND p.person_id = :person_id
        LIMIT 1
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(
                raw_sql, {"dataset_id": dataset_id, "person_id": int(id)}
            )
            row = result.fetchone()

            if row is None:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Person with id {id} not found in dataset {dataset_id}.",
                )

            person_dict = {
                "person_id": row.person_id,
                "gender_concept_id": row.gender_concept_id,
                "year_of_birth": row.year_of_birth,
                "month_of_birth": row.month_of_birth,
                "day_of_birth": row.day_of_birth,
                "birth_datetime": row.birth_datetime.isoformat()
                if row.birth_datetime
                else None,
                "race_concept_id": row.race_concept_id,
                "ethnicity_concept_id": row.ethnicity_concept_id,
                "location_id": row.location_id,
                "provider_id": row.provider_id,
                "care_site_id": row.care_site_id,
                "person_source_value": row.person_source_value,
                "gender_source_value": row.gender_source_value,
                "gender_source_concept_id": row.gender_source_concept_id,
                "race_source_value": row.race_source_value,
                "race_source_concept_id": row.race_source_concept_id,
                "ethnicity_source_value": row.ethnicity_source_value,
                "ethnicity_source_concept_id": row.ethnicity_source_concept_id,
            }

            return person_dict, 200

        except ProblemException:
            raise
        except Exception as e:
            logger.error(f"Database Error in person.get_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching person information from the database.",
            )

# --- Create person Endpoint ---
async def create(dataset_id: str, body: dict):
    """Create a new person in the dataset"""

    # First check if the dataset exists
    check_dataset_sql = text(f"""
        SELECT id FROM {settings.CANDIG_SCHEMA}.dataset WHERE id = :dataset_id LIMIT 1
    """)

    # Insert into person table and return all fields
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
        ) RETURNING person_id, gender_concept_id, year_of_birth, month_of_birth, 
                   day_of_birth, birth_datetime, race_concept_id, ethnicity_concept_id,
                   location_id, provider_id, care_site_id, person_source_value,
                   gender_source_value, gender_source_concept_id, race_source_value,
                   race_source_concept_id, ethnicity_source_value, ethnicity_source_concept_id
    """)

    # Insert into person_in_dataset table (link person to dataset)
    insert_person_dataset_sql = text(f"""
        INSERT INTO {settings.CANDIG_SCHEMA}.person_in_dataset (person_id, dataset_id)
        VALUES (:person_id, :dataset_id)
    """)

    async for session in get_db_session():
        try:
            # Validate required fields
            required_fields = [
                "gender_concept_id",
                "race_concept_id",
                "ethnicity_concept_id",
            ]
            for field in required_fields:
                if field not in body:
                    raise ProblemException(
                        status=400,
                        title="Bad Request",
                        detail=f"Missing required field: {field}",
                    )

            # Check if dataset exists
            result = await session.execute(
                check_dataset_sql, {"dataset_id": dataset_id}
            )
            if result.fetchone() is None:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {dataset_id} not found.",
                )

            # Parse birth_datetime
            birth_datetime = None
            if body.get("birth_datetime"):
                try:
                    birth_datetime = datetime.fromisoformat(
                        body["birth_datetime"].replace("Z", "+00:00")
                    )
                except ValueError:
                    raise ProblemException(
                        status=400,
                        title="Bad Request",
                        detail="Invalid birth_datetime format. Expected ISO 8601 format (e.g., '1985-03-15T10:30:00').",
                    )

            person_params = {
                "gender_concept_id": body.get("gender_concept_id"),
                "year_of_birth": body.get("year_of_birth"),
                "month_of_birth": body.get("month_of_birth"),
                "day_of_birth": body.get("day_of_birth"),
                "birth_datetime": birth_datetime,
                "race_concept_id": body.get("race_concept_id"),
                "ethnicity_concept_id": body.get("ethnicity_concept_id"),
                "location_id": body.get("location_id"),
                "provider_id": body.get("provider_id"),
                "care_site_id": body.get("care_site_id"),
                "person_source_value": body.get("person_source_value"),
                "gender_source_value": body.get("gender_source_value"),
                "gender_source_concept_id": body.get("gender_source_concept_id"),
                "race_source_value": body.get("race_source_value"),
                "race_source_concept_id": body.get("race_source_concept_id"),
                "ethnicity_source_value": body.get("ethnicity_source_value"),
                "ethnicity_source_concept_id": body.get("ethnicity_source_concept_id"),
            }

            result = await session.execute(insert_person_sql, person_params)
            row = result.fetchone()
            if row is None:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Person with id {id} not found in dataset {dataset_id}.",
                )

            person_id = row.person_id  # Get the person_id for linking to dataset

            # Link person to dataset
            await session.execute(
                insert_person_dataset_sql,
                {"person_id": person_id, "dataset_id": dataset_id},
            )

            await session.commit()

            person_dict = {
                "person_id": row.person_id,
                "gender_concept_id": row.gender_concept_id,
                "year_of_birth": row.year_of_birth,
                "month_of_birth": row.month_of_birth,
                "day_of_birth": row.day_of_birth,
                "birth_datetime": row.birth_datetime.isoformat()
                if row.birth_datetime
                else None,
                "race_concept_id": row.race_concept_id,
                "ethnicity_concept_id": row.ethnicity_concept_id,
                "location_id": row.location_id,
                "provider_id": row.provider_id,
                "care_site_id": row.care_site_id,
                "person_source_value": row.person_source_value,
                "gender_source_value": row.gender_source_value,
                "gender_source_concept_id": row.gender_source_concept_id,
                "race_source_value": row.race_source_value,
                "race_source_concept_id": row.race_source_concept_id,
                "ethnicity_source_value": row.ethnicity_source_value,
                "ethnicity_source_concept_id": row.ethnicity_source_concept_id,
            }

            return person_dict, 201

        except ProblemException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in person.create: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while creating the person in the database.",
            )

# --- Update person Endpoint ---
async def put(dataset_id: str, id: int, body: dict):
    """Update an existing person"""

    # First check if the dataset exists
    check_dataset_sql = text(f"""
        SELECT id FROM {settings.CANDIG_SCHEMA}.dataset WHERE id = :dataset_id LIMIT 1
    """)

    # Check if person exists in the dataset
    check_person_sql = text(f"""
        SELECT p.person_id
        FROM {settings.CDM_SCHEMA}.person p
        INNER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid ON p.person_id = pid.person_id
        WHERE pid.dataset_id = :dataset_id AND p.person_id = :person_id LIMIT 1
    """)

    # Update person table
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
        RETURNING person_id, gender_concept_id, year_of_birth, month_of_birth, 
                  day_of_birth, birth_datetime, race_concept_id, ethnicity_concept_id,
                  location_id, provider_id, care_site_id, person_source_value,
                  gender_source_value, gender_source_concept_id, race_source_value,
                  race_source_concept_id, ethnicity_source_value, ethnicity_source_concept_id
    """)

    async for session in get_db_session():
        try:
            # Validate required fields
            required_fields = [
                "person_id",
                "gender_concept_id",
                "race_concept_id",
                "ethnicity_concept_id",
            ]
            for field in required_fields:
                if field not in body:
                    raise ProblemException(
                        status=400,
                        title="Bad Request",
                        detail=f"Missing required field: {field}",
                    )

            # Validate that URL ID matches body person_id
            if int(id) != int(body["person_id"]):
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"URL person ID ({id}) does not match person_id in request body ({body['person_id']})",
                )

            # Check if dataset exists
            result = await session.execute(
                check_dataset_sql, {"dataset_id": dataset_id}
            )
            if result.fetchone() is None:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {dataset_id} not found.",
                )

            # Check if person exists in dataset
            result = await session.execute(
                check_person_sql, {"dataset_id": dataset_id, "person_id": int(id)}
            )
            if result.fetchone() is None:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Person with id {id} not found in dataset {dataset_id}.",
                )

            # Parse birth_datetime
            birth_datetime = None
            if body.get("birth_datetime"):
                try:
                    birth_datetime = datetime.fromisoformat(
                        body["birth_datetime"].replace("Z", "+00:00")
                    )
                except ValueError:
                    raise ProblemException(
                        status=400,
                        title="Bad Request",
                        detail="Invalid birth_datetime format. Expected ISO 8601 format (e.g., '1985-03-15T10:30:00').",
                    )

            # Prepare parameters for person update
            person_params = {
                "person_id": int(id),
                "gender_concept_id": body.get("gender_concept_id"),
                "year_of_birth": body.get("year_of_birth"),
                "month_of_birth": body.get("month_of_birth"),
                "day_of_birth": body.get("day_of_birth"),
                "birth_datetime": birth_datetime,
                "race_concept_id": body.get("race_concept_id"),
                "ethnicity_concept_id": body.get("ethnicity_concept_id"),
                "location_id": body.get("location_id"),
                "provider_id": body.get("provider_id"),
                "care_site_id": body.get("care_site_id"),
                "person_source_value": body.get("person_source_value"),
                "gender_source_value": body.get("gender_source_value"),
                "gender_source_concept_id": body.get("gender_source_concept_id"),
                "race_source_value": body.get("race_source_value"),
                "race_source_concept_id": body.get("race_source_concept_id"),
                "ethnicity_source_value": body.get("ethnicity_source_value"),
                "ethnicity_source_concept_id": body.get("ethnicity_source_concept_id"),
            }

            # Update person
            result = await session.execute(update_person_sql, person_params)
            row = result.fetchone()
            if row is None:
                raise ProblemException(
                    status=500,
                    title="Database Error",
                    detail=f"Failed to update person with id {id}.",
                )

            await session.commit()

            person_dict = {
                "person_id": row.person_id,
                "gender_concept_id": row.gender_concept_id,
                "year_of_birth": row.year_of_birth,
                "month_of_birth": row.month_of_birth,
                "day_of_birth": row.day_of_birth,
                "birth_datetime": row.birth_datetime.isoformat()
                if row.birth_datetime
                else None,
                "race_concept_id": row.race_concept_id,
                "ethnicity_concept_id": row.ethnicity_concept_id,
                "location_id": row.location_id,
                "provider_id": row.provider_id,
                "care_site_id": row.care_site_id,
                "person_source_value": row.person_source_value,
                "gender_source_value": row.gender_source_value,
                "gender_source_concept_id": row.gender_source_concept_id,
                "race_source_value": row.race_source_value,
                "race_source_concept_id": row.race_source_concept_id,
                "ethnicity_source_value": row.ethnicity_source_value,
                "ethnicity_source_concept_id": row.ethnicity_source_concept_id,
            }

            return person_dict, 200

        except ProblemException:
            await session.rollback()
            raise
        except ValueError as e:
            await session.rollback()
            raise ProblemException(
                status=400,
                title="Bad Request",
                detail=f"Invalid person_id format: {id}. Must be an integer.",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in person.put: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while updating the person in the database.",
            )

# --- Delete person Endpoint ---
async def delete(dataset_id: str, id: str):
    """
    Delete a person from Person table
    """
    # First check if the person exists in the dataset
    check_sql = text(f"""
        SELECT p.person_id
        FROM {settings.CDM_SCHEMA}.person p
        INNER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid ON p.person_id = pid.person_id
        WHERE pid.dataset_id = :dataset_id AND p.person_id = :person_id LIMIT 1
    """)

    # Delete from person_in_dataset first since we cannot use DELETE CASCADE
    # due to person_in_dataset references person
    delete_dataset_sql = text(f"""
        DELETE FROM {settings.CANDIG_SCHEMA}.person_in_dataset 
        WHERE dataset_id = :dataset_id AND person_id = :person_id
    """)

    # Then delete from person table
    delete_person_sql = text(f"""
        DELETE FROM {settings.CDM_SCHEMA}.person 
        WHERE person_id = :person_id
    """)

    async for session in get_db_session():
        try:
            # Check if person exists in dataset
            result = await session.execute(
                check_sql, {"dataset_id": dataset_id, "person_id": int(id)}
            )

            if result.fetchone() is None:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Person with id {id} not found in dataset {dataset_id}.",
                )

            # Delete from person_in_dataset
            await session.execute(
                delete_dataset_sql, {"dataset_id": dataset_id, "person_id": int(id)}
            )

            # Delete from person table
            await session.execute(delete_person_sql, {"person_id": int(id)})

            await session.commit()
            return {"message": f"Person {id} deleted successfully"}, 200

        except ProblemException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in person.delete: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while deleting the person from the database.",
            )

# --- Update person Endpoint ---
async def patch_user(dataset_id: str, id: str, body: dict):
    """Update an existing person in the database."""
    # TODO: update related record

    # First check if the person exists in the dataset
    check_person_sql = text(f"""
        SELECT p.person_id
        FROM {settings.CDM_SCHEMA}.person p
        INNER JOIN {settings.CANDIG_SCHEMA}.person_in_dataset pid ON p.person_id = pid.person_id
        WHERE pid.dataset_id = :dataset_id AND p.person_id = :person_id LIMIT 1
    """)

    # Update person table
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
        RETURNING person_id, gender_concept_id, year_of_birth, month_of_birth, 
                  day_of_birth, birth_datetime, race_concept_id, ethnicity_concept_id,
                  location_id, provider_id, care_site_id, person_source_value,
                  gender_source_value, gender_source_concept_id, race_source_value,
                  race_source_concept_id, ethnicity_source_value, ethnicity_source_concept_id
    """)

    async for session in get_db_session():
        try:
            # Validate that URL ID matches body person_id if provided
            if "person_id" in body and int(id) != int(body["person_id"]):
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=f"URL person ID ({id}) does not match person_id in request body ({body['person_id']})",
                )

            # Check if person exists in dataset
            result = await session.execute(
                check_person_sql, {"dataset_id": dataset_id, "person_id": int(id)}
            )

            if result.fetchone() is None:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Person with id {id} not found in dataset {dataset_id}.",
                )

            # Parse birth_datetime if provided
            birth_datetime = None
            if body.get("birth_datetime"):
                try:
                    birth_datetime = datetime.fromisoformat(
                        body["birth_datetime"].replace("Z", "+00:00")
                    )
                except ValueError:
                    raise ProblemException(
                        status=400,
                        title="Bad Request",
                        detail="Invalid birth_datetime format. Expected ISO 8601 format (e.g., '1985-03-15T10:30:00').",
                    )

            # Get current person data first to use as defaults for fields not provided
            get_current_sql = text(f"""
                SELECT * FROM {settings.CDM_SCHEMA}.person WHERE person_id = :person_id LIMIT 1
            """)
            current_result = await session.execute(
                get_current_sql, {"person_id": int(id)}
            )
            current_person = current_result.fetchone()
            if current_person is None:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Person with id {id} not found.",
                )

            # Prepare parameters for person update using current values as defaults
            person_params = {
                "person_id": int(id),
                "gender_concept_id": body.get(
                    "gender_concept_id", current_person.gender_concept_id
                ),
                "year_of_birth": body.get(
                    "year_of_birth", current_person.year_of_birth
                ),
                "month_of_birth": body.get(
                    "month_of_birth", current_person.month_of_birth
                ),
                "day_of_birth": body.get("day_of_birth", current_person.day_of_birth),
                "birth_datetime": birth_datetime
                if "birth_datetime" in body
                else current_person.birth_datetime,
                "race_concept_id": body.get(
                    "race_concept_id", current_person.race_concept_id
                ),
                "ethnicity_concept_id": body.get(
                    "ethnicity_concept_id", current_person.ethnicity_concept_id
                ),
                "location_id": body.get("location_id", current_person.location_id),
                "provider_id": body.get("provider_id", current_person.provider_id),
                "care_site_id": body.get("care_site_id", current_person.care_site_id),
                "person_source_value": body.get(
                    "person_source_value", current_person.person_source_value
                ),
                "gender_source_value": body.get(
                    "gender_source_value", current_person.gender_source_value
                ),
                "gender_source_concept_id": body.get(
                    "gender_source_concept_id", current_person.gender_source_concept_id
                ),
                "race_source_value": body.get(
                    "race_source_value", current_person.race_source_value
                ),
                "race_source_concept_id": body.get(
                    "race_source_concept_id", current_person.race_source_concept_id
                ),
                "ethnicity_source_value": body.get(
                    "ethnicity_source_value", current_person.ethnicity_source_value
                ),
                "ethnicity_source_concept_id": body.get(
                    "ethnicity_source_concept_id",
                    current_person.ethnicity_source_concept_id,
                ),
            }

            # Update person and get the updated row
            result = await session.execute(update_person_sql, person_params)
            row = result.fetchone()
            if row is None:
                raise ProblemException(
                    status=500,
                    title="Database Error",
                    detail=f"Failed to update person with id {id}.",
                )

            await session.commit()

            # Create person dictionary from the returned row
            person_dict = {
                "person_id": row.person_id,
                "gender_concept_id": row.gender_concept_id,
                "year_of_birth": row.year_of_birth,
                "month_of_birth": row.month_of_birth,
                "day_of_birth": row.day_of_birth,
                "birth_datetime": row.birth_datetime.isoformat()
                if row.birth_datetime
                else None,
                "race_concept_id": row.race_concept_id,
                "ethnicity_concept_id": row.ethnicity_concept_id,
                "location_id": row.location_id,
                "provider_id": row.provider_id,
                "care_site_id": row.care_site_id,
                "person_source_value": row.person_source_value,
                "gender_source_value": row.gender_source_value,
                "gender_source_concept_id": row.gender_source_concept_id,
                "race_source_value": row.race_source_value,
                "race_source_concept_id": row.race_source_concept_id,
                "ethnicity_source_value": row.ethnicity_source_value,
                "ethnicity_source_concept_id": row.ethnicity_source_concept_id,
            }

            return person_dict, 200

        except ProblemException:
            await session.rollback()
            raise
        except ValueError as e:
            await session.rollback()
            raise ProblemException(
                status=400,
                title="Bad Request",
                detail=f"Invalid person_id format: {id}. Must be an integer.",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in person.patch_user: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while updating the person in the database.",
            )
