from connexion.exceptions import ProblemException

from connexion.exceptions import ProblemException
from sqlalchemy import select, func

from ..database.db_add_table import Dataset, PersonInDataset

from ..database.db_operation import get_db_session


async def list_all():
    """Lists all datasets"""

    stmt = (
        select(
            Dataset.dataset_id,
            Dataset.dataset_source_value,
            func.count(PersonInDataset.person_id).label("person_count"),
        )
        .join(
            PersonInDataset,
            Dataset.dataset_id == PersonInDataset.dataset_id,
            isouter=True,
        )
        .group_by(Dataset.dataset_id)
        .order_by(Dataset.dataset_id)
    )

    async for session in get_db_session():
        try:
            result = await session.execute(stmt)
            records = result.all()

            datasets = [
                {
                    "id": record.dataset_id,
                    "source_value": record.dataset_source_value,
                    "count": record.person_count or 0
                }
                for record in records
            ]

            return datasets, 200
        except Exception as e:
            print(f"Database Error in dataset.list_all: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching datasets from the database.",
            )
    


async def get_by_id(id: str):
    """Gets a single dataset by ID"""

    stmt = (
        select(
            Dataset.dataset_id,
            func.count(PersonInDataset.person_id).label("person_count"),
        )
        .join(
            PersonInDataset,
            Dataset.dataset_id == PersonInDataset.dataset_id,
            isouter=True,
        )
        .where(Dataset.dataset_id == id)
        .group_by(Dataset.dataset_id)
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

            dataset = {"id": str(record.dataset_id), "count": record.person_count or 0}

            return dataset, 200
        except ProblemException:
            raise
        except Exception as e:
            print(f"Database Error in dataset.get_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching the dataset from the database.",
            )


# async def put_by_id(id: str, body: dict):
#     """
#     Create or update a dataset by ID
#     """

#     async for session in get_db_session():
#         try:
#             existing_dataset = await session.get(Dataset, id)

#             if existing_dataset:
#                 # update dataset info
#                 existing_dataset.info = body if body else {}
#                 # TODO: need to insert/update persons with related records
#                 await session.commit()

#             else:
#                 # create new dataset
#                 new_dataset = Dataset(dataset_id=id, info=body if body else {})
#                 session.add(new_dataset)
#                 await session.commit()

#             dataset = {"id": id, "info": body if body else {}}

#             return dataset, 200

#         except Exception as e:
#             await session.rollback()
#             print((f"Database Error in dataset.put_by_id: {str(e)}"))
#             raise ProblemException(
#                 status=500,
#                 title="Database Error",
#                 detail=" An error occurred while creating/updating the dataset in the database.",
#             )
async def put_by_id(id: str, body: dict):
    """
    Create or update a dataset by ID
    """
    from sqlalchemy import text
    from datetime import datetime

    async for session in get_db_session():
        try:
            existing_dataset = await session.get(Dataset, id)

            if existing_dataset:
                # update dataset info
                existing_dataset.info = body.get('info', {}) if body else {}
            else:
                # create new dataset
                new_dataset = Dataset(dataset_id=id, info=body.get('info', {}) if body else {})
                session.add(new_dataset)

            # Handle persons if they are included in the request body
            if body and 'persons' in body:
                persons = body['persons']
                
                # Insert persons and link them to the dataset
                for person_data in persons:
                    # Parse birth_datetime if provided
                    birth_datetime = None
                    if person_data.get('birth_datetime'):
                        birth_datetime = datetime.fromisoformat(person_data['birth_datetime'].replace('Z', '+00:00'))

                    # Insert person using raw SQL (person_id will be auto-generated)
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

                    # Prepare parameters for person insertion (excluding person_id)
                    person_params = {
                        "gender_concept_id": person_data.get('gender_concept_id'),
                        "year_of_birth": person_data.get('year_of_birth'),
                        "month_of_birth": person_data.get('month_of_birth'),
                        "day_of_birth": person_data.get('day_of_birth'),
                        "birth_datetime": birth_datetime,
                        "race_concept_id": person_data.get('race_concept_id'),
                        "ethnicity_concept_id": person_data.get('ethnicity_concept_id'),
                        "location_id": person_data.get('location_id'),
                        "provider_id": person_data.get('provider_id'),
                        "care_site_id": person_data.get('care_site_id'),
                        "person_source_value": person_data.get('person_source_value'),
                        "gender_source_value": person_data.get('gender_source_value'),
                        "gender_source_concept_id": person_data.get('gender_source_concept_id'),
                        "race_source_value": person_data.get('race_source_value'),
                        "race_source_concept_id": person_data.get('race_source_concept_id'),
                        "ethnicity_source_value": person_data.get('ethnicity_source_value'),
                        "ethnicity_source_concept_id": person_data.get('ethnicity_source_concept_id')
                    }

                    # Insert person and get the auto-generated person_id
                    result = await session.execute(insert_person_sql, person_params)
                    person_id = result.fetchone()[0]

                    # Link person to dataset using the auto-generated person_id
                    insert_person_dataset_sql = text("""
                        INSERT INTO candig_api.person_in_dataset (person_id, dataset_id)
                        VALUES (:person_id, :dataset_id)
                        ON CONFLICT (person_id, dataset_id) DO NOTHING
                    """)
                    
                    await session.execute(insert_person_dataset_sql, {
                        "person_id": person_id,
                        "dataset_id": id
                    })

            await session.commit()

            dataset = {"id": id, "info": body.get('info', {}) if body else {}}
            return dataset, 200

        except Exception as e:
            await session.rollback()
            print((f"Database Error in dataset.put_by_id: {str(e)}"))
            raise ProblemException(
                status=500,
                title="Database Error",
                detail=" An error occurred while creating/updating the dataset in the database.",
            )




async def delete_by_id(id: str):
    """
    Delete a dataset by its ID.
    """
    async for session in get_db_session():
        try:
            dataset_to_delete = await session.get(Dataset, id)

            if dataset_to_delete:
                await session.delete(dataset_to_delete)
                # TODO: delete all the related records like donors, event...
                await session.commit()
                return {"message": "Operation completed successfully."}, 200
            else:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Dataset with ID '{id}' not found.",
                )
        except ProblemException:
            raise
        except Exception as e:
            await session.rollback()
            print(f"Database Error in dataset.delete_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while deleting the dataset from the database.",
            )

    

async def get_info(id: str):
    """Gets dataset info by ID"""

    stmt = (
        select(
            Dataset.dataset_id,
            Dataset.info
        )
        .where(Dataset.dataset_id == id)
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

            dataset = {"id": str(record.dataset_id), "info": record.info}

            return dataset, 200
        except ProblemException:
            raise
        except Exception as e:
            print(f"Database Error in dataset.get_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching the dataset from the database.",
            )


async def patch_info(id: str, body: dict):
    """
    Updates dataset info by ID
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

            # Update the info field with the provided body
            existing_dataset.info = body if body else {}
            await session.commit()

            dataset = {"id": str(existing_dataset.dataset_id), "info": existing_dataset.info}
            
            return dataset, 200
        
        except ProblemException:
            raise
        except Exception as e:
            await session.rollback()
            print(f"Database Error in dataset.patch_info: {str(e)}")
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
            Dataset.dataset_id,
            func.count(PersonInDataset.person_id).label("person_count"),
        )
        .join(
            PersonInDataset,
            Dataset.dataset_id == PersonInDataset.dataset_id,
            isouter=True,
        )
        .group_by(Dataset.dataset_id)
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
                str(record.dataset_id): record.person_count or 0 
                for record in records
            }

            stats = {
                "person_count": total_person_count,
                "dataset_count": dataset_count,
                "persons_per_dataset": persons_per_dataset
            }

            return stats, 200
        except Exception as e:
            print(f"Database Error in dataset.statistics: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching dataset statistics from the database.",
            )
  

async def statistics_by_id(id: str):
    """
    Gets summary statistics for a specific dataset by ID
    """
    
    stmt = (
        select(
            Dataset.dataset_id,
            func.count(PersonInDataset.person_id).label("person_count"),
        )
        .join(
            PersonInDataset,
            Dataset.dataset_id == PersonInDataset.dataset_id,
            isouter=True,
        )
        .where(Dataset.dataset_id == id)
        .group_by(Dataset.dataset_id)
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

            stats = {
                "person_count": record.person_count or 0
            }

            return stats, 200
        except ProblemException:
            raise
        except Exception as e:
            print(f"Database Error in dataset.statistics_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching dataset statistics from the database.",
            )