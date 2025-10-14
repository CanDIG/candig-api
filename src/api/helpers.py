from src.database.insert_operations import (
    create_condition_occurrence,
    create_episode,
    create_episode_event,
    create_measurement,
    create_observation,
    create_person,
    create_specimen,
    create_procedure_occurrence,
    create_drug_exposure,
    create_fact_relationship,
    create_death,
    create_dataset,
    create_person_in_dataset,
)
from sqlalchemy.ext.asyncio import AsyncSession
from connexion.exceptions import ProblemException
import logging

logger = logging.getLogger(__name__)


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
}


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

    def get_id(self, id_obj: dict) -> int:
        """Retrieve the actual database ID for an id_map object."""
        key = self.create_key(id_obj)
        return self.id_map.get(key)


# ==============================================================================
# Record Processing Helper
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
