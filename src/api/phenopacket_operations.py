import asyncio
from datetime import date, datetime, timezone

from candigv2_logging.logging import CanDIGLogger
from connexion.exceptions import ProblemException
from sqlalchemy import text

from src.api.auth import is_action_allowed

from ..config import settings  # Import settings
from ..database.db_operations import get_db_session

logger = CanDIGLogger(__file__)


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
        (biosamples, _),
        (diseases, _),
        medical_actions,
        measurements,
    ) = await asyncio.gather(
        get_subject(person_id),
        get_biosamples(person_id),
        get_diseases(person_id),
        get_medical_actions(person_id),
        get_measurements(person_id),
    )

    meta_data = get_meta_data()

    phenopacket = {
        "id": str(person_id),
        "subject": subject,
        "measurements": measurements,
        "biosamples": biosamples,
        "diseases": diseases,
        "medical_actions": medical_actions,
        "metaData": meta_data,
    }

    return remove_empty_values(phenopacket)


async def get_medical_actions(person_id: int):
    # TODO: need to group/link each
    # response_to_treatments, treatment_intents, treatment_targets
    # instead of getting only 1
    (
        response_to_treatments,
        treatment_intents,
        treatment_targets,
        treatment_agents,
        procedures,
        radiation_therapies,
    ) = await asyncio.gather(
        get_treatment_responses(person_id),
        get_treatment_intents(person_id),
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

    # Use first intent/target for now since we can't figure out the link
    treatment_intent = treatment_intents[0] if treatment_intents else None
    treatment_target = treatment_targets[0] if treatment_targets else None

    # Create combinations of each treatment type with each response
    for response in response_to_treatments:
        # Combine treatment agents with responses
        for agent in treatment_agents:
            medical_action = {
                "action": agent,
                "treatment_target": treatment_target,
                "treatment_intent": treatment_intent,
                "response_to_treatment": response,
            }
            medical_actions.append(medical_action)

        # Combine procedures with responses
        for procedure in procedures:
            medical_action = {
                "action": procedure,
                "treatment_target": treatment_target,
                "treatment_intent": treatment_intent,
                "response_to_treatment": response,
            }
            medical_actions.append(medical_action)

        # Combine radiation therapies with responses
        for radiation in radiation_therapies:
            medical_action = {
                "action": radiation,
                "treatment_target": treatment_target,
                "treatment_intent": treatment_intent,
                "response_to_treatment": response,
            }
            medical_actions.append(medical_action)

    return medical_actions if medical_actions else None


async def get_disease_stages(person_id: int):
    raw_sql = text(f"""
    SELECT DISTINCT
        m.{settings.MAPPING_JSON['diseases']['disease_stage']['filtering_field']} as disease_stage_concept_id
    FROM {settings.CDM_SCHEMA}.{settings.MAPPING_JSON['diseases']['disease_stage']['omop_object']} AS m
    WHERE m.person_id = :person_id
        AND (
                m.{settings.MAPPING_JSON['diseases']['disease_stage']['filtering_field']} IN (
                SELECT descendant_concept_id FROM {settings.CDM_SCHEMA}.concept_ancestor
                WHERE ancestor_concept_id IN ({','.join([str(x) for x in settings.MAPPING_JSON['diseases']['disease_stage']['ancestor_ids']])})) 
                OR m.value_as_concept_id IN ({','.join([str(x) for x in settings.MAPPING_JSON['diseases']['disease_stage']['concept_ids']])})
            )
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies
            concept_ids = [row.disease_stage_concept_id for row in rows]
            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of OntologyClass objects
            measurements = [
                ontology_map.get(row.disease_stage_concept_id) for row in rows
            ]

            # Filter out None values if conversion failed
            return [m for m in measurements if m is not None]

        except Exception as e:
            logger.error(f"Database Error in _find_measurement: {str(e)}")
            return []

    return []


async def get_diseases(person_id: int):
    """
    Get diseases for a person from episode and condition_occurrence tables.
    Optimized with concurrent queries.
    """
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
        AND primary_site_obs.observation_concept_id = 3011717
    WHERE episode.person_id = :person_id
        AND episode.episode_concept_id = 32528
    """)

    (clinical_tnm_finding_list, laterality_list, disease_stages) = await asyncio.gather(
        get_tnm_findings(person_id, [4164336, 4164336, 4164466]),
        get_tnm_findings(person_id, [35918306]),
        get_disease_stages(person_id),
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
                disease = {
                    "term": ontology_map.get(row.term),
                    "onset": get_timestamp(row.onset),
                    "resolution": get_timestamp(row.resolution),
                    "disease_stage": disease_stages,
                    "clinical_tnm_finding": clinical_tnm_finding_list,
                    "primary_site": ontology_map.get(row.primary_site_concept_id),
                    "laterality": laterality,
                }
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


async def get_tnm_findings(person_id: int, measurement_concept_ids: list[int]):
    """
    Get pathological TNM findings
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
            tnm_findings = []
            for row in rows:
                if row.vocabulary_id and row.concept_code and row.concept_name:
                    ontology = {
                        "id": f"{row.vocabulary_id}:{row.concept_code}",
                        "label": row.concept_name,
                    }
                    tnm_findings.append(ontology)

            return tnm_findings

        except Exception as e:
            logger.error(f"Database Error in get_tnm_finding: {str(e)}")
            return []

    return []


async def get_biosamples(person_id: int):
    """
    Query from OMOP specimen table joined on person_id.
    Returns a list of biosample objects.
    """
    pathological_tnm_finding = await get_tnm_findings(
        person_id, [4293617, 4161174, 4154262]
    )

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
            AND hist_obs.observation_concept_id = 36716952
        LEFT JOIN {settings.CDM_SCHEMA}.observation tumor_obs
            ON tumor_obs.obs_event_field_concept_id = 1147049
            AND tumor_obs.observation_event_id = specimen.specimen_id
            AND tumor_obs.observation_concept_id = 4160340
        LEFT JOIN {settings.CDM_SCHEMA}.observation proc_obs
            ON proc_obs.obs_event_field_concept_id = 1147049
            AND proc_obs.observation_event_id = specimen.specimen_id
            AND proc_obs.observation_concept_id = 4243140
        LEFT JOIN {settings.CDM_SCHEMA}.observation storage_obs
            ON storage_obs.obs_event_field_concept_id = 1147049
            AND storage_obs.observation_event_id = specimen.specimen_id
            AND storage_obs.observation_concept_id = 37169821
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
                biosample = {
                    "id": str(row.id),
                    "individual_id": str(person_id),
                    "sampled_tissue": ontology_map.get(row.sampled_tissue),
                    "taxonomy": {
                        "id": "SNOMED:337915000",
                        "label": "Homo sapiens (organism)",
                    },
                    "time_of_collection": get_timestamp(row.time_of_collection),
                    "histological_diagnosis": ontology_map.get(
                        row.histological_diagnosis
                    ),
                    "tumor_grade": ontology_map.get(row.tumor_grade),
                    "pathological_tnm_finding": pathological_tnm_finding,
                    "sample_processing": ontology_map.get(row.sample_processing),
                    "sample_storage": ontology_map.get(row.sample_storage),
                }
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

            subject = {
                "id": str(row.id),
                "alternate_ids": [row.alternate_ids],
                "date_of_birth": get_birth_timestamp(
                    row.year_of_birth, row.month_of_birth, row.day_of_birth
                ),
                "sex": get_sex_status(row.sex_concept_id),
                "gender": ontology_map.get(row.gender_concept_id),
                "taxonomy": {
                    "id": "SNOMED:337915000",
                    "label": "Homo sapiens (organism)",
                },
                "vital_status": {
                    "status": get_death_status(row.time_of_death),
                    "time_of_death": get_timestamp(row.time_of_death),
                    "cause_of_death": ontology_map.get(row.cause_of_death_concept_id),
                    "survival_time_in_days": get_survival_time(
                        row.disease_first_occurrence_date, row.time_of_death
                    ),
                },
            }

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
    if not year:
        return None
    
    # Default to 1 if month or day is missing
    month = month if month else 1
    day = day if day else 1
    
    # Format as YYYY-MM-DD
    return f"{year:04d}-{month:02d}-{day:02d}"


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


def get_timestamp(datetime_value):
    """
    Convert OMOP datetime to Phenopacket Timestamp format.
    """
    if isinstance(datetime_value, datetime):
        if datetime_value.date() == date(1800, 1, 1):
            return None
        return {"iso8601timestamp": datetime_value.isoformat()}
    elif isinstance(datetime_value, date):
        if datetime_value == date(1800, 1, 1):
            return None
        return {"iso8601timestamp": datetime_value.isoformat()}

    return None


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

            return {
                row.concept_id: {
                    "id": f"{row.vocabulary_id}:{row.concept_code}",
                    "label": row.concept_name,
                }
                for row in rows
            }
        except Exception as e:
            logger.error(f"Error fetching concepts in batch: {str(e)}")
            return {}

    return {}


async def get_treatment_responses(person_id: int):
    raw_sql = text(f"""
        SELECT DISTINCT
            observation.value_as_concept_id as treatment_response_concept_id
        FROM {settings.CDM_SCHEMA}.observation observation
        WHERE observation.person_id = :person_id
            AND observation.observation_concept_id = 4082405
            AND observation.value_as_concept_id IS NOT NULL
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies
            concept_ids = [row.treatment_response_concept_id for row in rows]
            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of OntologyClass objects
            treatments = [
                ontology_map.get(row.treatment_response_concept_id) for row in rows
            ]

            # Filter out None values if conversion failed
            return [t for t in treatments if t is not None]

        except Exception as e:
            logger.error(f"Database Error in get_treatments: {str(e)}")
            return []

    return []

async def get_treatment_intents(person_id: int):
    raw_sql = text(f"""
        SELECT DISTINCT
            observation.value_as_concept_id as treatment_intent_concept_id
        FROM {settings.CDM_SCHEMA}.observation observation
        WHERE observation.person_id = :person_id
            AND observation.observation_concept_id = 4133895
            AND observation.value_as_concept_id IS NOT NULL
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies
            concept_ids = [row.treatment_intent_concept_id for row in rows]
            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of OntologyClass objects
            intents = [
                ontology_map.get(row.treatment_intent_concept_id) for row in rows
            ]

            # Filter out None values if conversion failed
            return [i for i in intents if i is not None]

        except Exception as e:
            logger.error(f"Database Error in get_treatment_intents: {str(e)}")
            return []

    return []

async def get_treatment_targets(person_id: int):
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
            AND episode.episode_concept_id = 32528
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
    raw_sql = text(f"""
        SELECT DISTINCT
            drug_exposure.drug_concept_id,
            drug_exposure.dose_unit_source_value as quantity_unit,
            drug_exposure.quantity as quantity_value, 
            drug_exposure.drug_exposure_end_date as dose_intervals_end,
            drug_exposure.drug_exposure_start_date as dose_intervals_start,
            drug_exposure.dose_unit_source_value as dose_intervals_quantity_unit,
            drug_exposure.quantity as dose_intervals_quantity_value,
            drug_exposure.route_concept_id as route_concept_id     
        FROM {settings.CDM_SCHEMA}.episode episode
        INNER JOIN {settings.CDM_SCHEMA}.episode_event episode_event
            ON episode.episode_id = episode_event.episode_id
            AND episode_event.episode_event_field_concept_id = 1147094
        INNER JOIN {settings.CDM_SCHEMA}.drug_exposure drug_exposure
            ON episode_event.event_id = drug_exposure.drug_exposure_id
        WHERE episode.person_id = :person_id
            AND episode.episode_concept_id = 32941
            AND drug_exposure.drug_concept_id IS NOT NULL
            AND drug_exposure.drug_type_concept_id = 32833
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies for both drug_concept_id and route_concept_id
            concept_ids = [row.drug_concept_id for row in rows]
            # Add route_concept_ids that are not None
            concept_ids.extend([row.route_concept_id for row in rows if row.route_concept_id is not None])
            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of treatment agent objects
            treatment_agents = []
            for row in rows:
                agent = ontology_map.get(row.drug_concept_id)
                if agent:
                    treatment_agent = {
                        "agent": agent,
                        "drug_type": "UNKNOWN_DRUG_TYPE"
                    }
                    
                    # Add route_of_administration
                    if row.route_concept_id is not None:
                        route = ontology_map.get(row.route_concept_id)
                        if route:
                            treatment_agent["route_of_administration"] = route
                        else:
                            treatment_agent["route_of_administration"] = {
                                "id": "SNOMED:261665006",
                                "label": "Unknown"
                            }
                    else:
                        treatment_agent["route_of_administration"] = {
                            "id": "SNOMED:261665006",
                            "label": "Unknown"
                        }
                    
                    # TODO: need to figureout quantity_unit ontology
                    # treatment_agent["cumulative_dose"] = {
                    #         "value": row.quantity_value,
                    #         "unit": row.quantity_unit 
                    # }
                    
                    # TODO: need to figureout quantity_unit ontology
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
                    
                    
                    treatment_agents.append(treatment_agent)

            return treatment_agents


        except Exception as e:
            logger.error(f"Database Error in get_drug_exposure: {str(e)}")
            return []

    return []


async def get_procedures(person_id: int):
    raw_sql = text(f"""
        SELECT DISTINCT
            procedure_occurrence.procedure_concept_id,
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
            AND observation.observation_concept_id = 4181646
            AND observation.obs_event_field_concept_id = 798885
        WHERE episode.person_id = :person_id
            AND episode.episode_concept_id = 32939
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies for both procedure and body_site
            concept_ids = []
            for row in rows:
                concept_ids.extend([row.procedure_concept_id, row.body_site_concept_id])
            
            ontology_map = await get_ontologies(concept_ids)

            # Convert rows to list of procedure objects
            procedures = []
            for row in rows:
                code = ontology_map.get(row.procedure_concept_id)
                body_site = ontology_map.get(row.body_site_concept_id)
                performed = get_timestamp(row.performed)
                if code:
                    procedure = {
                        "code": code,
                        "body_site": body_site,
                        "performed": performed
                    }
                    procedures.append(procedure)

            return procedures

        except Exception as e:
            logger.error(f"Database Error in get_procedures: {str(e)}")
            return []

    return []


async def get_radiation_therapies(person_id: int):
    raw_sql = text(f"""
        SELECT 
            episode.episode_object_concept_id as modality_concept_id,
            observation.value_as_concept_id as body_site_concept_id,
            dosage_measurement.value_as_number as dosage,
            fractions_measurement.value_as_number as fractions
        FROM {settings.CDM_SCHEMA}.episode episode
        LEFT JOIN {settings.CDM_SCHEMA}.observation observation
            ON observation.observation_event_id = episode.episode_id
            AND observation.observation_concept_id = 4181646
        LEFT JOIN {settings.CDM_SCHEMA}.measurement dosage_measurement
            ON dosage_measurement.person_id = episode.person_id
            AND dosage_measurement.measurement_concept_id = 40483776
        LEFT JOIN {settings.CDM_SCHEMA}.measurement fractions_measurement
            ON fractions_measurement.person_id = episode.person_id
            AND fractions_measurement.measurement_concept_id = 4037631
        WHERE episode.person_id = :person_id
            AND episode.episode_concept_id = 32940
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
                if modality and body_site and row.dosage is not None and row.fractions is not None:
                    therapy = {
                        "modality": modality,
                        "body_site": body_site,
                        "dosage": int(row.dosage),
                        "fractions": int(row.fractions),
                    }
                    radiation_therapies.append(therapy)

            return radiation_therapies

        except Exception as e:
            logger.error(f"Database Error in get_radiation_therapies: {str(e)}")
            return []

    return []


async def get_measurements(person_id: int):
    raw_sql = text(f"""
        SELECT DISTINCT
            observation.value_as_concept_id as measurement_value_concept_id
        FROM {settings.CDM_SCHEMA}.observation observation
        WHERE observation.person_id = :person_id
            AND observation.observation_concept_id = 43054909
    """)

    async for session in get_db_session():
        try:
            result = await session.execute(raw_sql, {"person_id": person_id})
            rows = result.fetchall()

            # Batch fetch ontologies
            concept_ids = [row.measurement_value_concept_id for row in rows]
            ontology_map = await get_ontologies(concept_ids)

            measurements = []
            for row in rows:
                measurement_value = ontology_map.get(row.measurement_value_concept_id)
                if measurement_value:
                    measurement = {
                        "assay": {"id": "LOINC:72166-2", "label": "Tobacco smoking status"},
                        "measurement_value": measurement_value,
                    }
                    measurements.append(measurement)

            return measurements if measurements else None

        except Exception as e:
            logger.error(f"Database Error in get_measurements: {str(e)}")
            return None

    return None


def get_meta_data():
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "created_by": "DHDP",
        "submitted_by": "DHDP",
        "phenopacket_schema_version": "2.0.0",
        "resources": [
            {
                "id": "SNOMED",
                "name": "Systemized Nomenclature of Medicine",
                "namespace_prefix": "SNOMED",
                "url": "https://bioportal.bioontology.org/ontologies/SNOMEDCT",
                "version": "2025-02-01 SNOMED CT International Edition; 2025-03-01 SNOMED CT US Edition; 2025-04-09 SNOMED CT UK Edition",
                "iri_prefix": "http://purl.bioontology.org/ontology/SNOMEDCT/",
            },
            {
                "id": "ICD10",
                "name": "International Statistical Classification of Diseases and Related Health Problems 10th Revision",
                "namespace_prefix": "ICD10",
                "url": "https://bioportal.bioontology.org/ontologies/ICD10",
                "version": "2021 Release",
                "iri_prefix": "http://purl.bioontology.org/ontology/ICD10/",
            },
            {
                "id": "ICD10PCS",
                "name": "International Classification of Diseases, 10th Revision, Procedure Coding System",
                "namespace_prefix": "ICD10PCS",
                "url": "https://bioportal.bioontology.org/ontologies/ICD10PCS",
                "version": "ICD10PCS 2026",
                "iri_prefix": "http://purl.bioontology.org/ontology/ICD10PCS/",
            },
            {
                "id": "ICD9CM",
                "name": "International Classification of Diseases, Ninth Revision, Clinical Modification",
                "namespace_prefix": "ICD9CM",
                "url": "https://bioportal.bioontology.org/ontologies/ICD9CM",
                "version": "ICD9CM v32 master descriptions",
                "iri_prefix": "http://purl.bioontology.org/ontology/ICD9CM/",
            },
            {
                "id": "ICD9Proc",
                "name": "International Classification of Diseases, Ninth Revision, Procedure Codes",
                "namespace_prefix": "Not Applicable",
                "url": "Not Applicable",
                "version": "ICD9CM v32 master descriptions",
                "iri_prefix": "Not Applicable",
            },
            {
                "id": "ICDO3",
                "name": "International Classification of Diseases for Oncology, 3rd Edition",
                "namespace_prefix": "ICDO",
                "url": "http://purl.obolibrary.org/obo/icdo.owl",
                "version": "ICDO3 SEER Site/Histology Released 06/2020",
                "iri_prefix": "http://purl.obolibrary.org/obo/ICDO_",
            },
            {
                "id": "LOINC",
                "name": "Logical Observation Identifiers Names and Codes",
                "namespace_prefix": "LP",
                "url": "https://bioportal.bioontology.org/ontologies/LOINC?p=summary",
                "version": "LOINC 2.80",
                "iri_prefix": "http://purl.bioontology.org/ontology/LNC/LP",
            },
            {
                "id": "NAACCR",
                "name": "North American Association of Central Cancer Registries",
                "namespace_prefix": "NAACCR",
                "url": "https://apps.naaccr.org/data-dictionary/data-dictionary",
                "version": "NAACCR v18",
                "iri_prefix": "https://apps.naaccr.org/data-dictionary/data-dictionary/version=26/data-item-view/item-number=",
            },
            {
                "id": "NCIt",
                "name": "National Cancer Institute Thesaurus",
                "namespace_prefix": "Thesaurus",
                "url": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "version": "NCIt 20220509",
                "iri_prefix": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#",
            },
            {
                "id": "RxNorm",
                "name": "RxNorm",
                "namespace_prefix": "rxnorm",
                "url": "http://purl.bioontology.org/ontology/RXNORM/",
                "version": "RxNorm 20250602",
                "iri_prefix": "http://purl.bioontology.org/ontology/RXNORM/",
            },
            {
                "id": "UCUM",
                "name": "Unified Code for Units of Measure",
                "namespace_prefix": "Not Applicable",
                "url": "https://ucum.org/ucum",
                "version": "Version 1.8.2",
                "iri_prefix": "Not Applicable",
            },
        ],
    }


def remove_empty_values(obj):
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
