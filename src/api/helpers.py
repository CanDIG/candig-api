import re

from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import (
    raise_bad_request,
    raise_integrity_error,
    raise_problem_exception,
)
from src.database.db_add_tables import Dataset
from src.database.db_operations import get_db_session
from src.database.insert_operations import (
    create_condition_occurrence,
    create_dataset,
    create_death,
    create_drug_exposure,
    create_episode,
    create_episode_event,
    create_fact_relationship,
    create_measurement,
    create_observation,
    create_person,
    create_person_in_dataset,
    create_procedure_occurrence,
    create_specimen,
    create_visit_occurrence,
)

logger = CanDIGLogger(__file__)


# ==============================================================================
# Configuration for each OMOP table
# ==============================================================================
TABLE_CONFIG = {
    "dataset": {
        "pk": "id",
        "fk_map": {},
        "create_func": create_dataset,
    },
    "person": {
        "pk": "person_id",
        "fk_map": {},
        "create_func": create_person,
    },
    "person_dataset": {
        "pk": None,
        "fk_map": {"dataset_id": "dataset_id", "person_id": "person_id"},
        "create_func": create_person_in_dataset,
    },
    "observation": {
        "pk": "observation_id",
        "fk_map": {
            "person_id": "person_id",
            "observation_event_id": "observation_event_id",
        },
        "create_func": create_observation,
    },
    "death": {
        "pk": None,  # Death table's PK is the person_id FK.
        "fk_map": {"person_id": "person_id"},
        "create_func": create_death,
    },
    "condition_occurrence": {
        "pk": "condition_occurrence_id",
        "fk_map": {"person_id": "person_id"},
        "create_func": create_condition_occurrence,
    },
    "episode": {
        "pk": "episode_id",
        "fk_map": {"person_id": "person_id"},
        "create_func": create_episode,
    },
    "episode_event": {
        "pk": None,
        "fk_map": {"episode_id": "episode_id", "event_id": "event_id"},
        "create_func": create_episode_event,
    },
    "measurement": {
        "pk": "measurement_id",
        "fk_map": {
            "person_id": "person_id",
            "measurement_event_id": "measurement_event_id",
        },
        "create_func": create_measurement,
    },
    "specimen": {
        "pk": "specimen_id",
        "fk_map": {"person_id": "person_id"},
        "create_func": create_specimen,
    },
    "procedure_occurrence": {
        "pk": "procedure_occurrence_id",
        "fk_map": {"person_id": "person_id"},
        "create_func": create_procedure_occurrence,
    },
    "drug_exposure": {
        "pk": "drug_exposure_id",
        "fk_map": {"person_id": "person_id"},
        "create_func": create_drug_exposure,
    },
    "fact_relationship": {
        "pk": None,
        "fk_map": {"fact_id_1": "fact_id_1", "fact_id_2": "fact_id_2"},
        "create_func": create_fact_relationship,
    },
    "visit_occurrence": {
        "pk": "visit_occurrence_id",
        "fk_map": {"person_id": "person_id"},
        "create_func": create_visit_occurrence,
    },
}


# ==============================================================================
# IdMapping during ingest
# ==============================================================================
class IdMapper:
    """A class to map temporary IDs from a payload to permanent database IDs."""

    def __init__(self):
        self.id_map = {}

    def create_key(self, id_obj: dict) -> str:
        """Create a unique string key from an id_map object."""
        return f"{id_obj['source_system']}|{id_obj['source_value']}|{id_obj['source_desc']}|{id_obj['target_desc']}"

    def store_id(self, id_obj: dict, actual_id: int):
        """Store the mapping between an id_map object and an actual database ID."""
        key = self.create_key(id_obj)
        self.id_map[key] = actual_id

    def get_id(self, id_obj: dict) -> int | None:
        """Retrieve the actual database ID for an id_map object."""
        key = self.create_key(id_obj)
        return self.id_map.get(key)


# ==============================================================================
# Create object in OMOP
# ==============================================================================
async def create_record(
    session: AsyncSession,
    id_mapper: IdMapper,
    record_field: dict,
    table_name: str,
) -> dict:
    """
    Function to process and create a single OMOP record.
    """
    config = TABLE_CONFIG[table_name]
    record_data = record_field.get("omop_record", {})

    # 1. Extract the temporary ID object for the primary key, if it exists
    pk_field = config.get("pk")
    id_obj = None
    if pk_field:
        id_obj = record_data.pop(pk_field, None)

    # 2. Resolve all foreign keys using the id_mapper
    for fk_field_name in config["fk_map"]:
        if fk_field_name in record_data:
            fk_id_obj = record_data[fk_field_name]
            actual_fk_id = id_mapper.get_id(fk_id_obj)
            if actual_fk_id is None:
                raise ProblemException(
                    status=400,
                    title="Bad Request",
                    detail=(
                        f"Could not resolve foreign key for '{fk_field_name}' in table '{table_name}'. "
                        f"Ensure the referenced entity is created first. "
                        f"Missing reference: {fk_id_obj}"
                    ),
                )
            record_data[fk_field_name] = actual_fk_id

    # 3. Call the specific create function for this table
    create_function = config["create_func"]
    new_record = await create_function(session, record_data)

    # 4. Store the mapping for the new primary key
    if pk_field and id_obj:
        new_pk_value = new_record[pk_field]
        id_mapper.store_id(id_obj, new_pk_value)

    # 5. Prepare the record for the final return object
    new_record["omop_table"] = table_name
    return new_record


# ==============================================================================
# Insert donor with clinical data
# ==============================================================================
async def ingest_donor_with_clinical_data(
    session: AsyncSession, donor_data: dict
):
    """
    Insert a single donor with related clinical data
    """
    return_objs = []
    id_mapper = IdMapper()
    PATTERNS = {
        "donor": r"^\$\.donors\[\d+\]$",
        "primary_diagnosis": r"^\$\.donors\[\d+\].primary_diagnoses\[\d+\]$",
        "specimen": r"^\$\.donors\[\d+\].primary_diagnoses\[\d+\].specimens\[\d+\]$",
        "treatment": r"^\$\.donors\[\d+\].primary_diagnoses\[\d+\].treatments\[\d+\]$",
        "systemic_therapy": r"^\$\.donors\[\d+\].primary_diagnoses\[\d+\].treatments\[\d+\].systemic_therapies\[\d+\]$",
        "surgery": r"^\$\.donors\[\d+\].primary_diagnoses\[\d+\].treatments\[\d+\].surgeries\[\d+\]$",
        "radiation": r"^\$\.donors\[\d+\].primary_diagnoses\[\d+\].treatments\[\d+\].radiations\[\d+\]$",
        "followup": r"^\$\.donors\[\d+\].primary_diagnoses\[\d+\].treatments\[\d+\].followups\[\d+\]$",
        "biomarker": r"^\$\.donors\[\d+\].biomarkers\[\d+\]$",
    }

    new_dataset_id = None
    for key in donor_data.keys():
        items = donor_data[key]
        if re.match(PATTERNS["donor"], key):
            # First pass: Find and create the dataset
            for field in items:
                if field.get("omop_table") == "dataset" and not field.get(
                    "skip_errors"
                ):
                    # Check if dataset already exists in the database by source_value
                    dataset_record = field.get("omop_record")
                    source_value = dataset_record.get("source_value")

                    # Query database for existing dataset
                    existing_dataset_stmt = select(Dataset).where(
                        Dataset.source_value == source_value
                    )
                    existing_dataset_result = await session.execute(
                        existing_dataset_stmt
                    )
                    existing_dataset = existing_dataset_result.scalar_one_or_none()

                    if existing_dataset:
                        # Use existing dataset
                        new_dataset_id = existing_dataset.id
                        id_mapper.store_id(dataset_record.get("id"), new_dataset_id)
                        return_objs.append(
                            {
                                "id": existing_dataset.id,
                                "source_value": existing_dataset.source_value,
                                "info": existing_dataset.info,
                                "omop_table": "dataset",
                            }
                        )
                    else:
                        # Create new dataset
                        new_dataset = await create_record(
                            session, id_mapper, field, "dataset"
                        )
                        new_dataset_id = new_dataset["id"]
                        new_dataset["omop_table"] = "dataset"
                        return_objs.append(new_dataset)
                    break

            if new_dataset_id is None:
                await raise_bad_request("dataset")

            new_person_id = None
            for field in items:
                if field.get("omop_table") == "person" and not field.get("skip_errors"):
                    new_person = await create_record(
                        session, id_mapper, field, "person"
                    )
                    new_person_id = new_person["person_id"]
                    return_objs.append(new_person)
                    break

            if new_person_id is None:
                await raise_bad_request("person")

            # Second pass: Process all other tables at the donor level
            for field in items:
                table_name = field.get("omop_table")
                if (
                    table_name != "person"
                    and table_name != "dataset"
                    and table_name in TABLE_CONFIG
                    and not field.get("skip_errors")
                ):
                    new_record = await create_record(
                        session, id_mapper, field, table_name
                    )
                    return_objs.append(new_record)

        else:  # process other tables
            # Check if the key matches any patterns (excluding donor)
            is_known_pattern = any(
                re.match(pattern, key)
                for name, pattern in PATTERNS.items()
                if name not in ["donor", "dataset"]
            )
            if is_known_pattern:
                for field in items:
                    table_name = field.get("omop_table")
                    if table_name in TABLE_CONFIG and not field.get("skip_errors"):
                        new_record = await create_record(
                            session, id_mapper, field, table_name
                        )
                        return_objs.append(new_record)


async def handle_single_donor_data_ingestion(body: dict):
    """
    Ingest single donor's data structure.
    """
    async for session in get_db_session():
        try:
            records = await ingest_donor_with_clinical_data(session, body)
            await session.commit()
            logger.info("Successfully created all records and committed transaction.")
            return {"records": records}, 201

        except ProblemException:
            await session.rollback()
            raise
        except IntegrityError as e:
            await session.rollback()
            await raise_integrity_error(e)
        except Exception as e:
            await session.rollback()
            await raise_problem_exception(e)
