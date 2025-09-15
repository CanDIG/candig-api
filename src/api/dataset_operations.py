import json
from datetime import datetime

from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from sqlalchemy import func, select, text

from ..database.db_add_table import Dataset, PersonInDataset
from ..database.db_operation import get_db_session

logger = CanDIGLogger(__file__)


async def list_all():
    """Lists all datasets"""

    stmt = (
        select(
            Dataset.id,
            Dataset.source_value,
            func.count(PersonInDataset.person_id).label("person_count"),
        )
        .join(
            PersonInDataset,
            Dataset.id == PersonInDataset.dataset_id,
            isouter=True,
        )
        .group_by(Dataset.id)
        .order_by(Dataset.id)
    )

    async for session in get_db_session():
        try:
            result = await session.execute(stmt)
            records = result.all()

            datasets = [
                {
                    "id": record.id,
                    "source_value": record.source_value,
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
                detail="An error occurred while fetching datasets from the database.",
            )


async def create(body: dict):
    """
    Create a new dataset with new person(s)
    """
    async for session in get_db_session():
        try:
            source_value = body["source_value"]
            info = body.get("info", {})
            persons = body.get("persons", [])
            new_dataset = Dataset(source_value=source_value, info=info)
            session.add(new_dataset)
            await session.flush()

            # insert persons if included
            if persons:
                for person_data in persons:
                    birth_datetime = None
                    if person_data.get("birth_datetime"):
                        birth_datetime = datetime.fromisoformat(
                            person_data["birth_datetime"].replace("Z", "+00:00")
                        )

                    insert_person_sql = text("""
                        INSERT INTO omop.person (
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
                    person_id = result.fetchone()[0]

                    # Link person to dataset
                    insert_person_dataset_sql = text("""
                        INSERT INTO candig.person_in_dataset (person_id, dataset_id)
                        VALUES (:person_id, :dataset_id)
                    """)
                    await session.execute(
                        insert_person_dataset_sql,
                        {"person_id": person_id, "dataset_id": new_dataset.id},
                    )

            await session.commit()

            # Return the created dataset
            dataset = {
                "id": new_dataset.id,
                "source_value": new_dataset.source_value,
                "info": new_dataset.info,
            }
            return dataset, 201

        except ProblemException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in dataset.create: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while creating the dataset in the database.",
            )


async def get_by_id(id: int):
    """Gets a single dataset"""

    stmt = (
        select(
            Dataset.id,
            Dataset.source_value,
            func.count(PersonInDataset.person_id).label("person_count"),
        )
        .join(
            PersonInDataset,
            Dataset.id == PersonInDataset.dataset_id,
            isouter=True,
        )
        .where(Dataset.id == id)
        .group_by(Dataset.id, Dataset.source_value)
    )

    async for session in get_db_session():
        try:
            result = await session.execute(stmt)
            record = result.one_or_none()

            if not record:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            dataset = {
                "id": record.id,
                "source_value": record.source_value,
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


async def put_by_id(id: int, body: dict):
    """
    Update an existing dataset with person(s)
    """
    async for session in get_db_session():
        try:
            # Get existing dataset
            existing_dataset = await session.get(Dataset, id)
            if not existing_dataset:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            # Update dataset fields
            existing_dataset.source_value = body["source_value"]
            existing_dataset.info = body.get("info", {})

            # Get all existing person_ids for this dataset
            existing_persons_stmt = select(PersonInDataset.person_id).where(
                PersonInDataset.dataset_id == id
            )
            existing_persons_result = await session.execute(existing_persons_stmt)
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
                        check_person_exists_sql = text("""
                            SELECT 1 FROM omop.person WHERE person_id = :person_id LIMIT 1
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

                        update_person_sql = text("""
                            UPDATE omop.person SET
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
                        check_link_sql = text("""
                            SELECT 1 FROM candig.person_in_dataset 
                            WHERE person_id = :person_id AND dataset_id = :dataset_id LIMIT 1
                        """)
                        link_exists = await session.execute(
                            check_link_sql, {"person_id": person_id, "dataset_id": id}
                        )

                        if not link_exists.fetchone():
                            insert_person_dataset_sql = text("""
                                INSERT INTO candig.person_in_dataset (person_id, dataset_id)
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

                        insert_person_sql = text("""
                            INSERT INTO omop.person (
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
                        new_person_id = result.fetchone()[0]
                        provided_person_ids.add(new_person_id)

                        # Link new person to dataset
                        insert_person_dataset_sql = text("""
                            INSERT INTO candig.person_in_dataset (person_id, dataset_id)
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
                delete_person_dataset_sql = text("""
                    DELETE FROM candig.person_in_dataset 
                    WHERE person_id = ANY(:person_ids) AND dataset_id = :dataset_id
                """)
                await session.execute(
                    delete_person_dataset_sql, 
                    {"person_ids": list(persons_to_delete), "dataset_id": id}
                )

                # Delete the persons from omop.person table
                delete_persons_sql = text("""
                    DELETE FROM omop.person 
                    WHERE person_id = ANY(:person_ids)
                """)
                await session.execute(
                    delete_persons_sql, 
                    {"person_ids": list(persons_to_delete)}
                )

            await session.commit()

            # Return the updated dataset
            dataset = {
                "id": existing_dataset.id,
                "source_value": existing_dataset.source_value,
                "info": existing_dataset.info,
            }
            return dataset, 200

        except ProblemException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in dataset.put_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while updating the dataset in the database.",
            )


async def delete_by_id(id: int):
    """
    Delete a dataset and its associate persons
    """
    async for session in get_db_session():
        try:
            dataset_to_delete = await session.get(Dataset, id)

            if dataset_to_delete:
                # Get all person_ids associated with this dataset
                person_in_dataset_stmt = select(PersonInDataset.person_id).where(
                    PersonInDataset.dataset_id == id
                )
                person_result = await session.execute(person_in_dataset_stmt)
                person_ids = [row[0] for row in person_result.fetchall()]

                # Delete from person_in_dataset table
                person_in_dataset_delete_stmt = select(PersonInDataset).where(
                    PersonInDataset.dataset_id == id
                )
                person_in_dataset_records = await session.execute(
                    person_in_dataset_delete_stmt
                )
                for record in person_in_dataset_records.scalars():
                    await session.delete(record)

                # Delete persons
                if person_ids:
                    delete_persons_sql = text("""
                        DELETE FROM omop.person 
                        WHERE person_id = ANY(:person_ids)
                    """)
                    await session.execute(
                        delete_persons_sql, {"person_ids": person_ids}
                    )

                # Delete the dataset
                await session.delete(dataset_to_delete)
                await session.commit()
                return {"message": "Operation completed successfully."}, 200
            else:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with ID '{id}' not found.",
                )
        except ProblemException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in dataset.delete_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while deleting the dataset from the database.",
            )


async def get_info(id: int):
    """Gets dataset info"""

    stmt = select(Dataset.info).where(Dataset.id == id)

    async for session in get_db_session():
        try:
            result = await session.execute(stmt)
            record = result.one_or_none()

            if not record:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            info = record.info
            if isinstance(info, str):
                info = json.loads(info)

            return info, 200
        except ProblemException:
            raise
        except Exception as e:
            logger.error(f"Database Error in dataset.get_info: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching the dataset from the database.",
            )


async def patch_info(id: int, body: dict):
    """
    Updates dataset info
    """

    async for session in get_db_session():
        try:
            existing_dataset = await session.get(Dataset, id)

            if not existing_dataset:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with id {id} not found",
                )

            existing_dataset.info = body if body else {}
            await session.commit()

            info = existing_dataset.info
            if isinstance(info, str):
                info = json.loads(info)

            return info, 200

        except ProblemException:
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Database Error in dataset.patch_info: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while updating the dataset info in the database",
            )


async def statistics():
    """
    Gets summary statistics for all datasets
    """

    # Get total dataset count and person counts per dataset
    stmt = (
        select(
            Dataset.id,
            func.count(PersonInDataset.person_id).label("person_count"),
        )
        .join(
            PersonInDataset,
            Dataset.id == PersonInDataset.dataset_id,
            isouter=True,
        )
        .group_by(Dataset.id)
    )

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


async def statistics_by_id(id: int):
    """
    Gets summary statistics for a specific dataset
    """

    stmt = (
        select(
            Dataset.id,
            func.count(PersonInDataset.person_id).label("person_count"),
        )
        .join(
            PersonInDataset,
            Dataset.id == PersonInDataset.dataset_id,
            isouter=True,
        )
        .where(Dataset.id == id)
        .group_by(Dataset.id)
    )

    async for session in get_db_session():
        try:
            result = await session.execute(stmt)
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
