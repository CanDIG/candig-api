import asyncio
import json
from datetime import date, datetime, timezone

from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from google.protobuf.json_format import MessageToJson
from google.protobuf.timestamp_pb2 import Timestamp
from phenopackets import (
    Biosample,
    Disease,
    Individual,
    Measurement,
    MedicalAction,
    MetaData,
    OntologyClass,
    Phenopacket,
    Procedure,
    Quantity,
    RadiationTherapy,
    Resource,
    TimeElement,
    Treatment,
    Value,
    VitalStatus,
)
from sqlalchemy import text

from src.api.auth import is_action_allowed

from ..config import settings  # Import settings
from ..database.db_operations import get_db_session

logger = CanDIGLogger(__file__)


def get_phenopacket_timestamp(datetime_value):
    """
    Convert OMOP datetime or date to Phenopacket TimeElement with Timestamp.
    """
    if datetime_value is None:
        return None

    # Convert to datetime if it's a date
    if isinstance(datetime_value, date) and not isinstance(datetime_value, datetime):
        dt = datetime.combine(datetime_value, datetime.min.time())
    else:
        dt = datetime_value

    if dt.date() == date(1800, 1, 1):
        return None

    # Create protobuf Timestamp
    timestamp = Timestamp()
    timestamp.FromDatetime(dt)
    return TimeElement(timestamp=timestamp)


async def get_by_id(dataset_id: str, id: int):
    """
    Returns a Phenopacket object with all fields from v2.0.0 schema
    """
    if not is_action_allowed(dataset=dataset_id):
        return {
            "error": f"User is not authorized to get person in dataset {dataset_id}"
        }, 403

    # check if dataset has this person
    if not await is_person_in_dataset(dataset_id, id):
        return {"error": f"Person {id} not in dataset {dataset_id}"}, 403

    person_id = id
    (
        (subject, _),
        (diseases, _),
        medical_actions,
        (biosamples, _),
        measurements,
    ) = await asyncio.gather(
        get_subject(person_id),
        get_diseases(person_id),
        get_medical_actions(person_id),
        get_biosamples(person_id),
        get_measurements(person_id),
    )

    meta_data = get_meta_data()

    phenopacket = Phenopacket(
        id=str(person_id),
        subject=subject,
        diseases=diseases,
        medical_actions=medical_actions,
        biosamples=biosamples,
        measurements=measurements,
        meta_data=meta_data,
    )

    phenopacket_as_dict = json.loads(
        MessageToJson(phenopacket, preserving_proto_field_name=True, indent=0)
    )

    return phenopacket_as_dict


async def get_medical_actions(person_id: int):
    # TODO: need to group/link each
    # treatment_targets
    # instead of getting only 1
    (
        response_to_treatments,
        treatment_intents,
        treatment_targets,
        treatment_agents,
        procedures,
        radiation_therapies,
    ) = await asyncio.gather(
        get_medical_action_by_field(person_id, "response_to_treatment"),
        get_medical_action_by_field(person_id, "treatment_intent"),
        get_treatment_targets(person_id),
        get_treatment_agents(person_id),
        get_procedures(person_id),
        get_radiation_therapies(person_id),
    )

    if not response_to_treatments:
        if not (treatment_agents or procedures or radiation_therapies):
            return None
        return None

    if not (treatment_agents or procedures or radiation_therapies):
        return None

    medical_actions = []

    # Use first target for now since we can't figure out the link
    treatment_target = treatment_targets[0] if treatment_targets else None

    episodes = list(
        set(list(response_to_treatments.keys()) + list(treatment_intents.keys()))
    )

    # Create combinations of each treatment type with each response
    for episode in episodes:
        # get intent and response linked to the episode, return No value if not in dict
        try:
            this_intent = treatment_intents[episode]
        except KeyError as e:
            this_intent = OntologyClass(id="SNOMED:408094002", label="No value")
        try:
            this_response = response_to_treatments[episode]
        except KeyError as e:
            this_response = OntologyClass(id="SNOMED:408094002", label="No value")
        # Combine treatment agents with responses
        for agent in treatment_agents:
            medical_action = MedicalAction(
                treatment=agent,
                treatment_target=treatment_target,
                treatment_intent=this_intent,
                response_to_treatment=this_response,
            )
            medical_actions.append(medical_action)

        # Combine procedures with responses
        for procedure in procedures:
            medical_action = MedicalAction(
                procedure=procedure,
                treatment_target=treatment_target,
                treatment_intent=this_intent,
                response_to_treatment=this_response,
            )
            medical_actions.append(medical_action)

        # Combine radiation therapies with responses
        for radiation in radiation_therapies:
            medical_action = MedicalAction(
                radiation_therapy=radiation,
                treatment_target=treatment_target,
                treatment_intent=this_intent,
                response_to_treatment=this_response,
            )
            medical_actions.append(medical_action)

    return medical_actions if medical_actions else None


async def get_concept_by_id_or_ancestor(
    person_id: int,
    omop_object: str,
    filtering_field: str,
    concept_value_field: str,
    concept_ids: list[str],
    ancestor_concept_ids: list[str],
) -> list[dict]:
    """
    Get ontologies from a specific omop object filtered by concept and ancestor concept ids
    """
    raw_sql = text(f"""
    SELECT DISTINCT
        m.{concept_value_field} as concept_id
    FROM {settings.CDM_SCHEMA}.{omop_object} AS m
    WHERE m.person_id = :person_id
        AND (
                m.{filtering_field} IN (
                SELECT descendant_concept_id FROM {settings.CDM_SCHEMA}.concept_ancestor
                WHERE ancestor_concept_id IN ({",".join([str(x) for x in ancestor_concept_ids])})) 
                OR m.value_as_concept_id IN ({",".join([str(x) for x in concept_ids])})
            )
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies
            found_concept_ids = [row.concept_id for row in rows]
            ontology_map = await get_ontologies(found_concept_ids)

            # Convert rows to list of OntologyClass objects
            measurements = [ontology_map.get(row.concept_id) for row in rows]

            # Filter out None values if conversion failed
            return [m for m in measurements if m is not None]

        except TypeError as e:
            print(e)
        except Exception as e:
            logger.error(f"Database Error in get_concept_by_id_or_ancestor: {str(e)}")
            return []

    return []


async def get_diseases(person_id: int):
    """
    To populate the diseases object in Phenopackets:

    Get term, onset, resolution, primary_site for a person by joining their 'Disease First Occurrence'
    episode (concept_id=32528) with its linked condition_occurrence tables via the episode_event table,
    join with 'Primary site Cancer' (concept_id=3011717) observation to get the primary site.

    Then look up clinical_tnm stages, laterality and disease_stages.

    Combine all retrieved information into disease object(s)

    Optimized with concurrent queries.
    """
    diseases_map = settings.MAPPING_JSON["diseases"]

    raw_sql = text(f"""
    SELECT 
        condition_occurrence.condition_concept_id as term,
        condition_occurrence.condition_start_date as onset,
        condition_occurrence.condition_end_date as resolution,
        primary_site_obs.value_as_concept_id as primary_site_concept_id
    FROM {settings.CDM_SCHEMA}.episode episode
    INNER JOIN {settings.CDM_SCHEMA}.episode_event episode_event
        ON episode.episode_id = episode_event.episode_id
        AND episode_event.episode_event_field_concept_id = 1147127
    INNER JOIN {settings.CDM_SCHEMA}.condition_occurrence condition_occurrence
        ON episode_event.event_id = condition_occurrence.condition_occurrence_id
    LEFT JOIN {settings.CDM_SCHEMA}.observation primary_site_obs
        ON primary_site_obs.person_id = :person_id
        AND primary_site_obs.observation_concept_id 
        IN({",".join(map(str, diseases_map["primary_site"]["concept_ids"]))})
    WHERE episode.person_id = :person_id
        AND episode.episode_concept_id = {diseases_map["term"]["grouping_concept_id"]}
    """)

    (clinical_tnm_finding_list, laterality_list, disease_stages) = await asyncio.gather(
        # get ontologies for clinical tnm measurements [cT category, cM category, cN category]
        get_measurement_concepts(
            person_id, diseases_map["clinical_tnm_finding"]["concept_ids"]
        ),
        # get ontologies for Laterality measurements
        get_measurement_concepts(person_id, diseases_map["laterality"]["concept_ids"]),
        get_concept_by_id_or_ancestor(
            person_id,
            diseases_map["disease_stage"]["omop_object"],
            diseases_map["disease_stage"]["filtering_field"],
            diseases_map["disease_stage"]["concept_value_field"],
            diseases_map["disease_stage"]["concept_ids"],
            diseases_map["disease_stage"]["ancestor_ids"],
        ),
    )

    # laterality should be a single object, not a list
    laterality = laterality_list[0] if laterality_list else None

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            concept_ids = [row.term for row in rows] + [
                row.primary_site_concept_id for row in rows
            ]
            ontology_map = await get_ontologies(concept_ids)

            diseases = []
            for row in rows:
                disease = Disease(
                    term=ontology_map.get(row.term),
                    onset=get_phenopacket_timestamp(row.onset),
                    resolution=get_phenopacket_timestamp(row.resolution),
                    disease_stage=disease_stages,
                    clinical_tnm_finding=clinical_tnm_finding_list,
                    primary_site=ontology_map.get(row.primary_site_concept_id),
                    laterality=laterality,
                )
                diseases.append(disease)

            return diseases, 200

        except Exception as e:
            logger.error(f"Database Error in get_diseases: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching disease information from the database.",
            )

    raise ProblemException(
        status=500,
        title="Database Error",
        detail="Unable to establish database session.",
    )


async def get_measurement_concepts(
    person_id: int, measurement_concept_ids: list[int]
) -> list[dict]:
    """
    Lookup measurements based on a list of concept ids and return as a list of mapped ontologies
    """
    concept_ids_str = ",".join(map(str, measurement_concept_ids))

    raw_sql = text(f"""
    SELECT 
        measurement.measurement_id,
        measurement.person_id,
        measurement.value_as_concept_id,
        concept.vocabulary_id,
        concept.concept_code,
        concept.concept_name
    FROM {settings.CDM_SCHEMA}.measurement measurement
    INNER JOIN {settings.CDM_SCHEMA}.person person
        ON measurement.person_id = person.person_id
    LEFT JOIN {settings.CDM_SCHEMA}.concept concept
        ON measurement.value_as_concept_id = concept.concept_id
    WHERE measurement.person_id = :person_id
        AND measurement.value_as_concept_id IS NOT NULL
        AND measurement.measurement_concept_id IN ({concept_ids_str})
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Convert rows to list of OntologyClass objects
            concepts = []
            for row in rows:
                if row.vocabulary_id and row.concept_code and row.concept_name:
                    ontology = OntologyClass(
                        id=f"{row.vocabulary_id}:{row.concept_code}",
                        label=row.concept_name,
                    )
                    concepts.append(ontology)

            return concepts

        except Exception as e:
            logger.error(f"Database Error in get_measurement_concepts: {str(e)}")
            return []

    return []


async def get_biosamples_measurements(person_id: int) -> dict:
    bm_map = settings.MAPPING_JSON["biosamples"]["measurements"]
    biosample_measurements = {}
    for mapping in bm_map:
        concept_ids_str = ",".join(map(str, mapping["concept_ids"]))
        raw_sql = text(f"""
        SELECT 
            {mapping["omop_object"]}.{mapping["omop_object"]}_id as obj_id,
            {mapping["omop_object"]}.person_id,
            {mapping["omop_object"]}.{mapping["filtering_field"]} as measurement_type_concept_id,
            {mapping["omop_object"]}.{mapping["concept_value_field"]} as measurement_value_concept_id,
            {mapping["omop_object"]}.{mapping["date_field"]} as date,
            {mapping["grouping_omop_object"]}.{mapping["grouping_omop_object"]}_id as group_id
        FROM {settings.CDM_SCHEMA}.{mapping["omop_object"]} {mapping["omop_object"]}
        LEFT JOIN {settings.CDM_SCHEMA}.{mapping["grouping_omop_object"]} {mapping["grouping_omop_object"]}
        ON {mapping["omop_object"]}.{mapping["grouping_field"]}={mapping["grouping_omop_object"]}.{mapping["grouping_omop_object"]}_id
        WHERE {mapping["omop_object"]}.person_id = :person_id
            AND {mapping["omop_object"]}.{mapping["concept_value_field"]} IS NOT NULL
            AND {mapping["omop_object"]}.{mapping["filtering_field"]} IN ({concept_ids_str})
        """)

        async for session in get_db_session():
            try:
                result = await session.execute(raw_sql, {"person_id": person_id})
                rows = result.fetchall()

                concept_ids = [row.measurement_type_concept_id for row in rows] + [
                    row.measurement_value_concept_id for row in rows
                ]
                ontology_map = await get_ontologies(concept_ids)

                # Convert rows to list of OntologyClass objects
                for row in rows:
                    if row.measurement_value_concept_id:
                        measurement_value = ontology_map.get(
                            row.measurement_value_concept_id
                        )
                        type_value = ontology_map.get(row.measurement_type_concept_id)
                        date_value = row.date
                        if measurement_value:
                            measurement = Measurement(
                                assay=type_value,
                                value=Value(ontology_class=measurement_value),
                                time_observed=get_phenopacket_timestamp(date_value),
                            )
                            try:
                                biosample_measurements[row.group_id].append(measurement)
                            except KeyError as e:
                                biosample_measurements[row.group_id] = [measurement]
                return biosample_measurements

            except Exception as e:
                logger.error(f"Database Error in get_biosamples_measurements: {str(e)}")
                return {}
    return {}


async def get_biosamples(person_id: int):
    """
    Query from OMOP specimen table joined on person_id.
    Returns a list of biosample objects.
    """
    biosamples_map = settings.MAPPING_JSON["biosamples"]

    pathological_tnm_finding = await get_measurement_concepts(
        person_id, biosamples_map["pathological_tnm_finding"]["concept_ids"]
    )

    biosamples_measurements = await get_biosamples_measurements(person_id)

    raw_sql = text(f"""
        SELECT 
            specimen.specimen_id as id,
            specimen.anatomic_site_concept_id as sampled_tissue,
            specimen.specimen_date as time_of_collection,
            hist_obs.value_as_concept_id as histological_diagnosis,
            tumor_obs.value_as_concept_id as tumor_grade,
            proc_obs.value_as_concept_id as sample_processing,
            storage_obs.value_as_concept_id as sample_storage                   
        FROM {settings.CDM_SCHEMA}.specimen specimen
        LEFT JOIN {settings.CDM_SCHEMA}.observation hist_obs
            ON hist_obs.obs_event_field_concept_id = 1147049
            AND hist_obs.observation_event_id = specimen.specimen_id
            AND hist_obs.observation_concept_id 
            IN ({",".join(map(str, biosamples_map["histological_diagnosis"]["concept_ids"]))})
        LEFT JOIN {settings.CDM_SCHEMA}.observation tumor_obs
            ON tumor_obs.obs_event_field_concept_id = 1147049
            AND tumor_obs.observation_event_id = specimen.specimen_id
            AND tumor_obs.observation_concept_id 
            IN ({",".join(map(str, biosamples_map["tumor_grade"]["concept_ids"]))})
        LEFT JOIN {settings.CDM_SCHEMA}.observation proc_obs
            ON proc_obs.obs_event_field_concept_id = 1147049
            AND proc_obs.observation_event_id = specimen.specimen_id
            AND proc_obs.observation_concept_id 
            IN ({",".join(map(str, biosamples_map["sample_processing"]["concept_ids"]))})
        LEFT JOIN {settings.CDM_SCHEMA}.observation storage_obs
            ON storage_obs.obs_event_field_concept_id = 1147049
            AND storage_obs.observation_event_id = specimen.specimen_id
            AND storage_obs.observation_concept_id 
            IN ({",".join(map(str, biosamples_map["sample_storage"]["concept_ids"]))})
        WHERE specimen.person_id = :person_id
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            concept_ids = []
            for row in rows:
                concept_ids.extend(
                    [
                        row.sampled_tissue,
                        row.histological_diagnosis,
                        row.tumor_grade,
                        row.sample_processing,
                        row.sample_storage,
                    ]
                )

            ontology_map = await get_ontologies(concept_ids)

            biosamples = []
            for row in rows:
                biosample = Biosample(
                    id=str(row.id),
                    individual_id=str(person_id),
                    sampled_tissue=ontology_map.get(row.sampled_tissue),
                    taxonomy=OntologyClass(
                        id="SNOMED:337915000", label="Homo sapiens (organism)"
                    ),
                    time_of_collection=get_phenopacket_timestamp(
                        row.time_of_collection
                    ),
                    histological_diagnosis=ontology_map.get(row.histological_diagnosis),
                    tumor_grade=ontology_map.get(row.tumor_grade),
                    pathological_tnm_finding=pathological_tnm_finding,
                    sample_processing=ontology_map.get(row.sample_processing),
                    sample_storage=ontology_map.get(row.sample_storage),
                )

                if row.id in biosamples_measurements.keys():
                    biosample.measurements.extend(biosamples_measurements[row.id])

                biosamples.append(biosample)

            return biosamples, 200

        except Exception as e:
            logger.error(f"Database Error in get_biosample: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching biosample information from the database.",
            )

    raise ProblemException(
        status=500,
        title="Database Error",
        detail="Unable to establish database session.",
    )


async def get_subject(id: int):
    """
    Get all metadata for the phenopackets subject object
    """
    raw_sql = text(f"""
            SELECT 
                person.person_id as id,
                person.gender_concept_id as sex_concept_id,
                person.year_of_birth,
                person.month_of_birth,
                person.day_of_birth,
                person.person_source_value as alternate_ids,
                gender_obs.value_as_concept_id as gender_concept_id,
                death.death_date as time_of_death,
                death.cause_concept_id as cause_of_death_concept_id,
                disease_first_occurrence.condition_start_date as disease_first_occurrence_date
                        
            FROM {settings.CDM_SCHEMA}.person person
            LEFT JOIN {settings.CDM_SCHEMA}.observation gender_obs 
                ON gender_obs.person_id = :person_id
                AND gender_obs.observation_concept_id = 37171290
            LEFT JOIN {settings.CDM_SCHEMA}.death death 
                ON death.person_id = :person_id
            LEFT JOIN {settings.CDM_SCHEMA}.episode episode
                ON episode.person_id = :person_id
                AND episode.episode_concept_id = 32528
            LEFT JOIN {settings.CDM_SCHEMA}.episode_event episode_event
                ON episode.episode_id = episode_event.episode_id
                AND episode_event.episode_event_field_concept_id = 1147127
            LEFT JOIN {settings.CDM_SCHEMA}.condition_occurrence disease_first_occurrence
                ON episode_event.event_id = disease_first_occurrence.condition_occurrence_id
            WHERE person.person_id = :person_id
            LIMIT 1
        """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": id})
            row = result.fetchone()

            if not row:
                raise ProblemException(
                    status=404,
                    title="Not Found",
                    detail=f"Person with id {id} not found.",
                )

            # Batch fetch ontologies for subject
            ontology_map = await get_ontologies(
                [row.gender_concept_id, row.cause_of_death_concept_id]
            )

            subject = Individual(
                id=str(row.id),
                alternate_ids=[row.alternate_ids],
                date_of_birth=get_birth_timestamp(
                    row.year_of_birth, row.month_of_birth, row.day_of_birth
                ),
                sex=get_sex_status(row.sex_concept_id),
                gender=ontology_map.get(row.gender_concept_id),
                taxonomy=OntologyClass(
                    id="SNOMED:337915000", label="Homo sapiens (organism)"
                ),
                vital_status=VitalStatus(
                    status=get_death_status(row.time_of_death),
                    time_of_death=get_phenopacket_timestamp(row.time_of_death),
                    cause_of_death=ontology_map.get(row.cause_of_death_concept_id),
                    survival_time_in_days=get_survival_time(
                        row.disease_first_occurrence_date, row.time_of_death
                    ),
                ),
            )

            return subject, 200

        except ProblemException:
            raise
        except Exception as e:
            logger.error(f"Database Error in person.get_by_id: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while fetching person information from the database.",
            )

    # If no session was available
    raise ProblemException(
        status=500,
        title="Database Error",
        detail="Unable to establish database session.",
    )


def get_birth_timestamp(year, month, day):
    """
    Convert birth year/month/day to protobuf Timestamp.
    """
    if not year or year == 1800:
        return None

    # Default to 1 if month or day is missing
    month = month if month else 1
    day = day if day else 1

    # Create datetime and convert to protobuf Timestamp
    birth_datetime = datetime(year, month, day, 0, 0)
    timestamp = Timestamp()
    timestamp.FromDatetime(birth_datetime)
    return timestamp


def get_sex_status(gender_concept_id):
    """
    Convert OMOP gender concept to Phenopacket sex enum.
    """
    if gender_concept_id == 8507:
        return "MALE"
    elif gender_concept_id == 8532:
        return "FEMALE"
    elif gender_concept_id == 8521:
        return "OTHER_SEX"

    return "UNKNOWN_SEX"


def get_death_status(death_date):
    if death_date:
        return "DECEASED"
    return "ALIVE"


def get_survival_time(disease_first_occurrence_date, death_date):
    """
    Calculate survival time in days from disease first occurrence to death.
    """
    if not disease_first_occurrence_date or not death_date:
        return None

    # Handle both date and datetime objects
    if isinstance(disease_first_occurrence_date, datetime):
        start_date = disease_first_occurrence_date.date()
    else:
        start_date = disease_first_occurrence_date

    if isinstance(death_date, datetime):
        end_date = death_date.date()
    else:
        end_date = death_date

    if start_date == date(1800, 1, 1) or end_date == date(1800, 1, 1):
        return None

    # Calculate difference in days
    delta = end_date - start_date
    return delta.days


async def get_ontologies(concept_ids: list):
    if not concept_ids:
        return {}

    # Remove None values and duplicates
    valid_ids = list(set([cid for cid in concept_ids if cid is not None]))

    if not valid_ids:
        return {}

    # Create placeholders for the IN clause
    placeholders = ",".join([f":id_{i}" for i in range(len(valid_ids))])

    raw_sql = text(f"""
        SELECT 
            concept_id,
            vocabulary_id,
            concept_code,
            concept_name
        FROM {settings.CDM_SCHEMA}.concept
        WHERE concept_id IN ({placeholders})
    """)

    # Create parameter dictionary
    params = {f"id_{i}": int(cid) for i, cid in enumerate(valid_ids)}

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, params)
            rows = result.fetchall()

            ontology_map = {}

            for row in rows:
                if row.concept_id == 0:
                    ontology_map[row.concept_id] = OntologyClass(
                        id="SNOMED:408094002",
                        label="No value",
                    )
                else:
                    ontology_map[row.concept_id] = OntologyClass(
                        id=f"{row.vocabulary_id}:{row.concept_code}",
                        label=row.concept_name,
                    )

            return ontology_map
        except Exception as e:
            logger.error(f"Error fetching concepts in batch: {str(e)}")
            return {}

    return {}


async def get_medical_action_by_field(person_id: int, field: str) -> dict:
    """
    Get medical action information based on field mapping grouped by episode ids

    Return is a dict with episode ids as keys and field mapping as an ontology
    {episode_id_1: {id: "ontology_curie", label: "ontology label"},
     episode_id_2: {id: "ontology_curie", label: "ontology label"}}
    """
    ma_map = settings.MAPPING_JSON["medical_actions"][field]
    raw_sql = text(f"""
        SELECT DISTINCT
            {ma_map["omop_object"]}.{ma_map["concept_value_field"]} as medical_action_concept_id,
            {ma_map["omop_object"]}.{ma_map["grouping_field"]} as episode_id
        FROM {settings.CDM_SCHEMA}.observation observation
        WHERE {ma_map["omop_object"]}.person_id = :person_id
            AND {ma_map["omop_object"]}.{ma_map["filtering_field"]} IN ({",".join([str(x) for x in ma_map["concept_ids"]])})
            AND {ma_map["omop_object"]}.{ma_map["concept_value_field"]} IS NOT NULL
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies
            concept_ids = [row.medical_action_concept_id for row in rows]
            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of OntologyClass objects
            medical_action = {}
            for row in rows:
                medical_action_ontology = ontology_map.get(
                    row.medical_action_concept_id
                )
                if medical_action_ontology:
                    medical_action[row.episode_id] = medical_action_ontology
                else:
                    medical_action[row.episode_id] = OntologyClass(
                        id="SNOMED:408094002", label="No value"
                    )

            # Filter out None values if conversion failed
            return medical_action

        except Exception as e:
            logger.error(f"Database Error in get_treatments: {str(e)}")
            return {}

    return {}


async def get_treatment_targets(person_id: int):
    """
    Get the ontology term for the condition_occurrence disease matching the mapped episode.

    Currently Disease First Occurrence (concept id: 32528)
    """
    ma_map = settings.MAPPING_JSON["medical_actions"]

    raw_sql = text(f"""
        SELECT DISTINCT
            condition_occurrence.condition_concept_id as treatment_target_concept_id
        FROM {settings.CDM_SCHEMA}.episode episode
        INNER JOIN {settings.CDM_SCHEMA}.episode_event episode_event
            ON episode.episode_id = episode_event.episode_id
            AND episode_event.episode_event_field_concept_id = 1147127
        INNER JOIN {settings.CDM_SCHEMA}.condition_occurrence condition_occurrence
            ON episode_event.event_id = condition_occurrence.condition_occurrence_id
        WHERE episode.person_id = :person_id
            AND episode.episode_concept_id = {ma_map["treatment_target"]["grouping_concept_id"]}
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies
            concept_ids = [row.treatment_target_concept_id for row in rows]
            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of OntologyClass objects
            targets = [
                ontology_map.get(row.treatment_target_concept_id) for row in rows
            ]

            # Filter out None values if conversion failed
            return [t for t in targets if t is not None]

        except Exception as e:
            logger.error(f"Database Error in get_treatment_targets: {str(e)}")
            return []

    return []


async def get_treatment_agents(person_id: int):
    """
    Get all drug exposures that link to the mapped episode type and mapped drug exposure type

    Currently Cancer Drug Treatment (concept id 32941) episodes and EHR Order (concept id 32833) or EHR prescribed (32838) drug types

    If no concept mapping for the drug, attempts to parse the drug ontology from the drug_source_value.
    This is needed currently because we only map RxNorm to concepts currently.
    """
    tx_map = settings.MAPPING_JSON["medical_actions"]["action"]["treatment"]

    raw_sql = text(f"""
        SELECT DISTINCT
            drug_exposure.drug_concept_id,
            drug_exposure.dose_unit_source_value as quantity_unit,
            drug_exposure.quantity as quantity_value, 
            drug_exposure.drug_exposure_end_date as dose_intervals_end,
            drug_exposure.drug_exposure_start_date as dose_intervals_start,
            drug_exposure.dose_unit_source_value as dose_intervals_quantity_unit,
            drug_exposure.quantity as dose_intervals_quantity_value,
            drug_exposure.route_concept_id as route_concept_id,
            drug_exposure.drug_type_concept_id as drug_type_concept_id,
            drug_exposure.{tx_map["agent"]["source_value_field"]} as drug_source_value
        FROM {settings.CDM_SCHEMA}.episode episode
        INNER JOIN {settings.CDM_SCHEMA}.episode_event episode_event
            ON episode.episode_id = episode_event.episode_id
            AND episode_event.episode_event_field_concept_id = 1147094
        INNER JOIN {settings.CDM_SCHEMA}.drug_exposure drug_exposure
            ON episode_event.event_id = drug_exposure.drug_exposure_id
        WHERE episode.person_id = :person_id
            AND episode.episode_concept_id = {tx_map["agent"]["grouping_concept_id"]}
            AND drug_exposure.drug_concept_id IS NOT NULL
            AND drug_exposure.drug_type_concept_id 
            IN({",".join([str(x) for x in tx_map["agent"]["concept_ids"]])})
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies for both drug_concept_id and route_concept_id
            concept_ids = [row.drug_concept_id for row in rows] + list(
                map(
                    int, list(tx_map["cumulative_dose"]["unit"]["concept_map"].values())
                )
            )
            # Add route_concept_ids that are not None
            concept_ids.extend(
                [
                    row.route_concept_id
                    for row in rows
                    if row.route_concept_id is not None
                ]
            )
            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of treatment agent objects
            treatment_agents = []
            for row in rows:
                if row.drug_concept_id == 0 and "|" in row.drug_source_value:
                    split_drug = row.drug_source_value.split("|")
                    if split_drug[0] == "NCI Thesaurus":
                        split_drug[0] = "NCIT"
                    agent = OntologyClass(
                        id=":".join(split_drug[:2]), label=split_drug[2]
                    )
                else:
                    agent = ontology_map.get(row.drug_concept_id)
                if agent:
                    if row.drug_type_concept_id == 32838:
                        treatment_agent = {"agent": agent, "drug_type": "PRESCRIPTION"}
                    else:
                        treatment_agent = {
                            "agent": agent,
                            "drug_type": "UNKNOWN_DRUG_TYPE",
                        }

                    # Add route_of_administration
                    if row.route_concept_id is not None:
                        route = ontology_map.get(row.route_concept_id)
                        if route:
                            treatment_agent["route_of_administration"] = route
                        else:
                            treatment_agent["route_of_administration"] = OntologyClass(
                                id="SNOMED:261665006", label="Unknown"
                            )
                    else:
                        treatment_agent["route_of_administration"] = OntologyClass(
                            id="SNOMED:261665006", label="Unknown"
                        )

                    # If drug exposure is from 'EHR Order' drug type, include cumulative dose
                    if (
                        row.drug_type_concept_id
                        in tx_map["cumulative_dose"]["concept_ids"]
                        and row.quantity_value
                    ):
                        if (
                            row.quantity_unit
                            in tx_map["cumulative_dose"]["unit"]["concept_map"].keys()
                        ):
                            treatment_agent["cumulative_dose"] = Quantity(
                                value=row.quantity_value,
                                unit=ontology_map[
                                    tx_map["cumulative_dose"]["unit"]["concept_map"][
                                        row.quantity_unit
                                    ]
                                ],
                            )
                        elif row.quantity_value:
                            treatment_agent["cumulative_dose"] = Quantity(
                                value=row.quantity_value,
                                unit=OntologyClass(
                                    id="SNOMED:261665006", label="Unknown"
                                ),
                            )
                        else:
                            treatment_agent["cumulative_dose"] = None
                    else:
                        treatment_agent["cumulative_dose"] = None

                    # Add dose_intervals if we have the necessary data
                    # if row.dose_intervals_start or row.dose_intervals_end or row.dose_intervals_quantity_value:
                    #     dose_intervals = {}
                    #     treatment_agent["schedule_frequency"] = {
                    #         "id": "SNOMED:261665006",
                    #         "label": "Unknown"
                    #     }

                    #     # Add quantity if available
                    #     if row.dose_intervals_quantity_value is not None:
                    #         dose_intervals["quantity"] = {
                    #             "value": row.dose_intervals_quantity_value,
                    #             "unit": {}
                    #         }

                    #     # Add interval if start or end date is available
                    #     if row.dose_intervals_start or row.dose_intervals_end:
                    #         interval = {}
                    #         if row.dose_intervals_start:
                    #             interval["start"] = row.dose_intervals_start.isoformat()
                    #         if row.dose_intervals_end:
                    #             interval["end"] = row.dose_intervals_end.isoformat()
                    #         dose_intervals["interval"] = interval

                    #     if dose_intervals:
                    #         treatment_agent["dose_intervals"] = dose_intervals

                    treatment = Treatment(
                        agent=treatment_agent["agent"],
                        route_of_administration=treatment_agent[
                            "route_of_administration"
                        ],
                        drug_type=treatment_agent["drug_type"],
                        cumulative_dose=treatment_agent["cumulative_dose"],
                    )
                    treatment_agents.append(treatment)

            return treatment_agents

        except Exception as e:
            logger.error(f"Database Error in get_treatment_agents: {str(e)}")
            return []

    return []


async def get_procedures(person_id: int):
    """
    Get procedure_occurrence and site information grouped by episodes with mapped episode type via episode events.

    Currently maps to Cancer Surgery (concept id 32939) episodes and Procedure sites (concept id 4181646)

    If procedure_concept_id unmapped, attempt to parse procedure_source_value and use instead or uses concept_map as last resort for those with no mappings
    """
    procedure_map = settings.MAPPING_JSON["medical_actions"]["action"]["procedure"]
    # get surgery procedures:
    surgery_raw_sql = text(f"""
        SELECT DISTINCT
            procedure_occurrence.procedure_concept_id,
            procedure_occurrence.procedure_source_value,
            procedure_occurrence.procedure_date as performed,
            observation.value_as_concept_id as body_site_concept_id
        FROM {settings.CDM_SCHEMA}.episode episode
        INNER JOIN {settings.CDM_SCHEMA}.episode_event episode_event
            ON episode.episode_id = episode_event.episode_id
            AND episode_event.episode_event_field_concept_id = 1147082
        INNER JOIN {settings.CDM_SCHEMA}.procedure_occurrence procedure_occurrence
            ON episode_event.event_id = procedure_occurrence.procedure_occurrence_id
        LEFT JOIN {settings.CDM_SCHEMA}.observation observation
            ON observation.observation_event_id = episode.episode_id
            AND observation.observation_concept_id 
            IN({",".join([str(x) for x in procedure_map["body_site"]["concept_ids"]])})
            AND observation.obs_event_field_concept_id = 798885
        WHERE episode.person_id = :person_id
            AND episode.episode_concept_id = {procedure_map["code"]["grouping_concept_id"]}
    """)
    # get other procedures that don't map to treatment/radiation
    others_raw_sql = text(f"""
                          SELECT DISTINCT
                            procedure_occurrence.procedure_concept_id,
                            procedure_occurrence.procedure_source_value,
                            procedure_occurrence.procedure_date as performed
                          FROM {settings.CDM_SCHEMA}.{procedure_map["code"]["omop_object"]} procedure_occurrence
                          WHERE {procedure_map["code"]["omop_object"]}.person_id = :person_id
                          AND ({procedure_map["code"]["omop_object"]}.procedure_concept_id
                          IN({",".join(map(str, list(procedure_map["code"]["concept_ids"])))}) 
                          OR procedure_source_value='{list(procedure_map["code"]["concept_map"].keys())[0]}')""")

    async for session in get_db_session():
        try:
            surgery_result = await session.execute(
                surgery_raw_sql, {"person_id": person_id}
            )
            surgery_rows = surgery_result.fetchall()

            # Batch fetch ontologies for both procedure and body_site
            concept_ids = []
            for row in surgery_rows:
                concept_ids.extend([row.procedure_concept_id, row.body_site_concept_id])

            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of procedure objects
            procedures = []
            for row in surgery_rows:
                if row.procedure_concept_id == 0 and "|" in row.procedure_source_value:
                    split_procedure = row.procedure_source_value.split("|")
                    code = OntologyClass(
                        id=":".join(split_procedure[:2]), label=split_procedure[2]
                    )
                else:
                    code = ontology_map.get(row.procedure_concept_id)
                body_site = ontology_map.get(row.body_site_concept_id)
                performed = get_phenopacket_timestamp(row.performed)
                if code:
                    procedure = Procedure(
                        code=code, body_site=body_site, performed=performed
                    )
                    procedures.append(procedure)

            others_result = await session.execute(
                others_raw_sql, {"person_id": person_id}
            )
            other_rows = others_result.fetchall()

            concept_ids = []
            for row in other_rows:
                concept_ids.extend([row.procedure_concept_id])

            ontology_map = await get_ontologies(concept_ids)
            for row in other_rows:
                if (
                    row.procedure_concept_id == 0
                    and row.procedure_source_value
                    in procedure_map["code"]["concept_map"].keys()
                ):
                    code = OntologyClass(
                        id=procedure_map["code"]["concept_map"][
                            row.procedure_source_value
                        ]["id"],
                        label=procedure_map["code"]["concept_map"][
                            row.procedure_source_value
                        ]["label"],
                    )
                else:
                    code = ontology_map.get(row.procedure_concept_id)
                performed = get_phenopacket_timestamp(row.performed)
                if code:
                    procedure = Procedure(code=code, performed=performed)
                    procedures.append(procedure)

            return procedures

        except Exception as e:
            logger.error(f"Database Error in get_procedures: {str(e)}")
            return []

    return []


async def get_radiation_therapies(person_id: int):
    """
    Gets radiation therapy information from measurements and observations mapped to specific episodes

    Currently mapped to Cancer radiotherapy (32940) episodes with
        - Total radiation dose delivered (40483776) measurement
        - Fractions (4037631) measurement
        - Procedure site (4181646) observation
    """
    rt_map = settings.MAPPING_JSON["medical_actions"]["action"]["radiation_therapy"]
    raw_sql = text(f"""
        SELECT 
            episode.episode_object_concept_id as modality_concept_id,
            observation.value_as_concept_id as body_site_concept_id,
            dosage_measurement.value_as_number as dosage,
            fractions_measurement.value_as_number as fractions
        FROM {settings.CDM_SCHEMA}.episode episode
        LEFT JOIN {settings.CDM_SCHEMA}.observation observation
            ON observation.observation_event_id = episode.episode_id
            AND observation.observation_concept_id 
            IN({",".join([str(x) for x in rt_map["body_site"]["concept_ids"]])})
        LEFT JOIN {settings.CDM_SCHEMA}.measurement dosage_measurement
            ON dosage_measurement.person_id = episode.person_id
            AND dosage_measurement.measurement_concept_id 
            IN({",".join([str(x) for x in rt_map["dosage"]["concept_ids"]])})
        LEFT JOIN {settings.CDM_SCHEMA}.measurement fractions_measurement
            ON fractions_measurement.person_id = episode.person_id
            AND fractions_measurement.measurement_concept_id 
            IN({",".join([str(x) for x in rt_map["fractions"]["concept_ids"]])})
        WHERE episode.person_id = :person_id
            AND episode.episode_concept_id = {rt_map["grouping_concept_id"]}
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies
            concept_ids = []
            for row in rows:
                concept_ids.extend([row.modality_concept_id, row.body_site_concept_id])

            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of radiation therapy objects
            radiation_therapies = []
            for row in rows:
                modality = ontology_map.get(row.modality_concept_id)
                body_site = ontology_map.get(row.body_site_concept_id)

                # Only include radiation therapy if ALL required fields are present
                if (
                    modality
                    and body_site
                    and row.dosage is not None
                    and row.fractions is not None
                ):
                    therapy = RadiationTherapy(
                        modality=modality,
                        body_site=body_site,
                        dosage=int(row.dosage),
                        fractions=int(row.fractions),
                    )
                    radiation_therapies.append(therapy)

            return radiation_therapies

        except Exception as e:
            logger.error(f"Database Error in get_radiation_therapies: {str(e)}")
            return []

    return []


async def get_measurements(person_id: int):
    """
    Get measurements objects based on concept and ancestor mappings in concept_mappings.json

    Currently mapped to various measurements and observations
    """
    measurements = []
    for mapping in settings.MAPPING_JSON["measurements"]:
        raw_sql = None
        if mapping["omop_object"] == "observation":
            raw_sql = text(f"""
                SELECT DISTINCT
                    {mapping["omop_object"]}.{mapping["concept_value_field"]} as measurement_value_concept_id,
                    {mapping["omop_object"]}.{mapping["number_value_field"]} as measurement_value,
                    {mapping["omop_object"]}.{mapping["filtering_field"]} as measurement_type_concept_id,
                    {mapping["omop_object"]}.{mapping["date_field"]} as measurement_date,
                    {mapping["omop_object"]}.{mapping["unit_field"]} as measurement_unit_concept_id
                FROM {settings.CDM_SCHEMA}.{mapping["omop_object"]}
                WHERE {mapping["omop_object"]}.person_id = :person_id
                    AND {mapping["omop_object"]}.{mapping["filtering_field"]} 
                    IN({",".join([str(x) for x in mapping["concept_ids"]])})
            """)

        elif mapping["omop_object"] == "measurement":
            raw_sql = text(f"""
                SELECT DISTINCT
                    {mapping["omop_object"]}.{mapping["concept_value_field"]} as measurement_value_concept_id,
                    {mapping["omop_object"]}.{mapping["number_value_field"]} as measurement_value,
                    {mapping["omop_object"]}.{mapping["filtering_field"]} as measurement_type_concept_id,
                    {mapping["omop_object"]}.{mapping["date_field"]} as measurement_date,
                    {mapping["omop_object"]}.{mapping["unit_field"]} as measurement_unit_concept_id
                FROM {settings.CDM_SCHEMA}.{mapping["omop_object"]}
                WHERE {mapping["omop_object"]}.person_id = :person_id
                    AND ({mapping["filtering_field"]} IN (
                    SELECT descendant_concept_id FROM {settings.CDM_SCHEMA}.concept_ancestor
                    WHERE ancestor_concept_id IN ({",".join([str(x) for x in mapping["ancestor_ids"]])})))
            """)

        elif mapping["omop_object"] == "procedure_occurrence":
            raw_sql = text(f"""
                SELECT DISTINCT
                    {mapping["omop_object"]}.{mapping["concept_value_field"]} as measurement_value_concept_id,
                    {mapping["omop_object"]}.{mapping["concept_value_field"]} as measurement_value,
                    {mapping["omop_object"]}.{mapping["filtering_field"]} as measurement_type_concept_id,
                    {mapping["omop_object"]}.{mapping["date_field"]} as measurement_date,
                    {mapping["omop_object"]}.{mapping["concept_value_field"]} as measurement_unit_concept_id
                FROM {settings.CDM_SCHEMA}.{mapping["omop_object"]}
                WHERE {mapping["omop_object"]}.person_id = :person_id
                    AND ({mapping["filtering_field"]} 
                    IN (SELECT descendant_concept_id FROM {settings.CDM_SCHEMA}.concept_ancestor
                    WHERE ancestor_concept_id IN({",".join([str(x) for x in mapping["ancestor_ids"]])})) 
                    OR {mapping["filtering_field"]} IN({",".join([str(x) for x in mapping["concept_ids"]])}))
            """)
        else:
            logger.warning(
                f"Unsupported omop_object type: {mapping.get('omop_object')}"
            )
            continue

        async for session in get_db_session():
            try:
                result = await session.execute(raw_sql, {"person_id": person_id})
                rows = result.fetchall()

                # Batch fetch ontologies
                concept_ids = list(
                    set(
                        (
                            [row.measurement_value_concept_id for row in rows]
                            + [row.measurement_type_concept_id for row in rows]
                            + [row.measurement_unit_concept_id for row in rows]
                            + [4129922]
                        )
                    )
                )
                ontology_map = await get_ontologies(concept_ids)

                for row in rows:
                    if row.measurement_value_concept_id:
                        measurement_value = ontology_map.get(
                            row.measurement_value_concept_id
                        )
                        type_value = ontology_map.get(row.measurement_type_concept_id)
                        date_value = row.measurement_date
                        if measurement_value:
                            measurement = Measurement(
                                assay=type_value,
                                value=Value(ontology_class=measurement_value),
                                time_observed=get_phenopacket_timestamp(date_value),
                            )
                            measurements.append(measurement)
                    elif row.measurement_value:
                        type_value = ontology_map.get(row.measurement_type_concept_id)
                        unit_value = ontology_map.get(row.measurement_unit_concept_id)
                        if not unit_value:
                            unit_value = ontology_map.get(4129922)
                        measurement_value = row.measurement_value
                        date_value = row.measurement_date
                        if measurement_value:
                            measurement = Measurement(
                                assay=type_value,
                                value=Value(
                                    quantity=Quantity(
                                        unit=unit_value, value=measurement_value
                                    )
                                ),
                                time_observed=get_phenopacket_timestamp(date_value),
                            )
                            measurements.append(measurement)

            except Exception as e:
                logger.error(f"Database Error in get_measurements: {str(e)}")
                return None
    return measurements if measurements else None


def get_meta_data():
    # Create protobuf Timestamp for current time
    created_timestamp = Timestamp()
    created_timestamp.FromDatetime(datetime.now(timezone.utc))
    return MetaData(
        created=created_timestamp,
        created_by="DHDP",
        submitted_by="DHDP",
        phenopacket_schema_version="2.0.0",
        resources=[
            Resource(
                id="SNOMED",
                name="Systemized Nomenclature of Medicine",
                namespace_prefix="SNOMED",
                url="https://bioportal.bioontology.org/ontologies/SNOMEDCT",
                version="2025-02-01 SNOMED CT International Edition; 2025-03-01 SNOMED CT US Edition; 2025-04-09 SNOMED CT UK Edition",
                iri_prefix="http://purl.bioontology.org/ontology/SNOMEDCT/",
            ),
            Resource(
                id="ICD10",
                name="International Statistical Classification of Diseases and Related Health Problems 10th Revision",
                namespace_prefix="ICD10",
                url="https://bioportal.bioontology.org/ontologies/ICD10",
                version="2021 Release",
                iri_prefix="http://purl.bioontology.org/ontology/ICD10/",
            ),
            Resource(
                id="ICD10PCS",
                name="International Classification of Diseases, 10th Revision, Procedure Coding System",
                namespace_prefix="ICD10PCS",
                url="https://bioportal.bioontology.org/ontologies/ICD10PCS",
                version="ICD10PCS 2026",
                iri_prefix="http://purl.bioontology.org/ontology/ICD10PCS/",
            ),
            Resource(
                id="ICD9CM",
                name="International Classification of Diseases, Ninth Revision, Clinical Modification",
                namespace_prefix="ICD9CM",
                url="https://bioportal.bioontology.org/ontologies/ICD9CM",
                version="ICD9CM v32 master descriptions",
                iri_prefix="http://purl.bioontology.org/ontology/ICD9CM/",
            ),
            Resource(
                id="ICD9Proc",
                name="International Classification of Diseases, Ninth Revision, Procedure Codes",
                namespace_prefix="Not Applicable",
                url="Not Applicable",
                version="ICD9CM v32 master descriptions",
                iri_prefix="Not Applicable",
            ),
            Resource(
                id="ICDO3",
                name="International Classification of Diseases for Oncology, 3rd Edition",
                namespace_prefix="ICDO3",
                url="http://purl.obolibrary.org/obo/icdo.owl",
                version="ICDO3 SEER Site/Histology Released 06/2020",
                iri_prefix="http://purl.obolibrary.org/obo/ICDO_",
            ),
            Resource(
                id="LOINC",
                name="Logical Observation Identifiers Names and Codes",
                namespace_prefix="LOINC",
                url="https://bioportal.bioontology.org/ontologies/LOINC?p=summary",
                version="LOINC 2.80",
                iri_prefix="http://purl.bioontology.org/ontology/LNC/LP",
            ),
            Resource(
                id="NAACCR",
                name="North American Association of Central Cancer Registries",
                namespace_prefix="NAACCR",
                url="https://apps.naaccr.org/data-dictionary/data-dictionary",
                version="NAACCR v18",
                iri_prefix="https://apps.naaccr.org/data-dictionary/data-dictionary/version=26/data-item-view/item-number=",
            ),
            Resource(
                id="NCIt",
                name="National Cancer Institute Thesaurus",
                namespace_prefix="Thesaurus",
                url="http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                version="NCIt 20220509",
                iri_prefix="http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#",
            ),
            Resource(
                id="RxNorm",
                name="RxNorm",
                namespace_prefix="RxNorm",
                url="http://purl.bioontology.org/ontology/RXNORM/",
                version="RxNorm 20250602",
                iri_prefix="http://purl.bioontology.org/ontology/RXNORM/",
            ),
            Resource(
                id="PubChem",
                name="PubChem",
                namespace_prefix="PubChem",
                url="https://pubchem.ncbi.nlm.nih.gov/",
                version="PubChem 2026",
                iri_prefix="N/A",
            ),
            Resource(
                id="UMLS",
                name="Unified Medical Language System UMLS",
                namespace_prefix="UMLS",
                url="https://www.nlm.nih.gov/research/umls/index.html",
                version="UMLS 2026",
                iri_prefix="N/A",
            ),
            Resource(
                id="UCUM",
                name="Unified Code for Units of Measure",
                namespace_prefix="Not Applicable",
                url="https://ucum.org/ucum",
                version="Version 1.8.2",
                iri_prefix="Not Applicable",
            ),
            Resource(
                id="CancerModifier",
                name="Diagnostic Modifiers of Cancer (OMOP)",
                namespace_prefix="Cancer Modifier",
                url="https://www.ohdsi.org/data-standardization/",
                version="Cancer Modifier 20220909",
                iri_prefix="Not Applicable",
            ),
        ],
    )


def remove_empty_values(obj):
    """
    If any value is None, remove it from the object
    """
    if isinstance(obj, dict):
        cleaned = {k: remove_empty_values(v) for k, v in obj.items() if v is not None}
        # Remove empty lists and empty dicts
        return {k: v for k, v in cleaned.items() if v != [] and v != {}}
    elif isinstance(obj, list):
        cleaned = [remove_empty_values(item) for item in obj if item is not None]
        # Filter out empty lists and empty dicts from the list
        return [item for item in cleaned if item != [] and item != {}]
    else:
        return obj


async def is_person_in_dataset(dataset_id: str, person_id: int):
    raw_sql = text(f"""
        SELECT COUNT(*) as count
        FROM {settings.CANDIG_SCHEMA}.person_in_dataset
        WHERE dataset_id = :dataset_id
            AND person_id = :person_id
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(
                raw_sql, {"dataset_id": dataset_id, "person_id": person_id}
            )
            row = result.fetchone()

            if not row or row.count == 0:
                return False

            return True

        except Exception as e:
            logger.error(f"Database Error in is_person_id_in_dataset: {str(e)}")
            raise ProblemException(
                status=500,
                title="Database Error",
                detail="An error occurred while checking person in dataset.",
            )

    raise ProblemException(
        status=500,
        title="Database Error",
        detail="Unable to establish database session.",
    )
