from datetime import date
from uuid import uuid4

import pytest

from src.database.insert_operations import (
    create_condition_occurrence,
    create_drug_exposure,
    create_episode,
    create_episode_event,
    create_measurement,
    create_observation,
    create_person,
    create_procedure_occurrence,
)
from tests.testcontainer.conftest import insert_concept
from src.api.phenopacket_operations import get_medical_actions

async def create_base_person(session):
    person = await create_person(
        session,
        {
            "gender_concept_id": 8507,
            "year_of_birth": 1990,
            "month_of_birth": 1,
            "day_of_birth": 1,
            "person_source_value": f"MA_{uuid4().hex[:8]}",
        },
    )
    return person["person_id"]


async def test_get_medical_actions_drug_treatment(db_session):

    person_id = await create_base_person(db_session)

    # Concept rows required for ontology lookup
    await insert_concept(
        db_session,
        45590880,
        "Malignant neoplasm of gallbladder",
        vocabulary_id="ICD10",
        code="C23",
    )
    await insert_concept(
        db_session,
        40491905,
        "Forensic intent",
        vocabulary_id="SNOMED",
        code="447295008",
    )
    await insert_concept(
        db_session,
        36310520,
        "No Evidence of this Cancer",
        vocabulary_id="LOINC",
        code="LA4566-1",
    )
    await insert_concept(
        db_session,
        42426830,
        "Tamoxifen",
        vocabulary_id="RxNorm",
        code="42426830",
    )

    # Disease First Occurrence episode -> condition_occurrence
    disease_ep = await create_episode(
        db_session, {"person_id": person_id, "episode_concept_id": 32528}
    )
    condition = await create_condition_occurrence(
        db_session,
        {
            "person_id": person_id,
            "condition_concept_id": 45590880,
            "condition_start_date": date(2019, 6, 1),
        },
    )
    await create_episode_event(
        db_session,
        {
            "episode_id": disease_ep["episode_id"],
            "event_id": condition["condition_occurrence_id"],
            "episode_event_field_concept_id": 1147127,
        },
    )

    # Treatment regimen episode
    treat_ep = await create_episode(
        db_session, {"person_id": person_id, "episode_concept_id": 32531}
    )
    # Link CO to regimen episode so get_treatment_targets returns target for TREAT_EP
    await create_episode_event(
        db_session,
        {
            "episode_id": treat_ep["episode_id"],
            "event_id": condition["condition_occurrence_id"],
            "episode_event_field_concept_id": 1147127,
        },
    )

    # Intent and response observations (obs_event_id = TREAT_EP makes TREAT_EP an "episode")
    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4133895,
            "value_as_concept_id": 40491905,
            "observation_event_id": treat_ep["episode_id"],
        },
    )
    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4082405,
            "value_as_concept_id": 36310520,
            "observation_event_id": treat_ep["episode_id"],
        },
    )

    # Cancer Drug Treatment episode, linked to regimen via field 798885
    drug_ep = await create_episode(
        db_session, {"person_id": person_id, "episode_concept_id": 32941}
    )
    await create_episode_event(
        db_session,
        {
            "episode_id": treat_ep["episode_id"],
            "event_id": drug_ep["episode_id"],
            "episode_event_field_concept_id": 798885,
        },
    )

    # drug_exposure linked to DRUG_EP via field 1147094 (PRESCRIPTION = drug_type 32838)
    drug_exposure = await create_drug_exposure(
        db_session,
        {
            "person_id": person_id,
            "drug_concept_id": 42426830,
            "drug_type_concept_id": 32838,
            "drug_exposure_start_date": date(2020, 1, 1),
            "drug_exposure_end_date": date(2020, 6, 1),
        },
    )
    await create_episode_event(
        db_session,
        {
            "episode_id": drug_ep["episode_id"],
            "event_id": drug_exposure["drug_exposure_id"],
            "episode_event_field_concept_id": 1147094,
        },
    )

    await db_session.flush()

    medical_actions = await get_medical_actions(person_id)

    assert medical_actions is not None
    assert len(medical_actions) == 1

    ma = medical_actions[0]

    assert ma.treatment is not None
    assert ma.treatment.agent.id == "RxNorm:42426830"
    assert ma.treatment.agent.label == "Tamoxifen"

    assert ma.treatment.route_of_administration.id == "SNOMED:261665006"
    assert ma.treatment.route_of_administration.label == "Unknown"

    assert ma.treatment_intent.id == "SNOMED:447295008"
    assert ma.treatment_intent.label == "Forensic intent"

    assert ma.response_to_treatment.id == "LOINC:LA4566-1"
    assert ma.response_to_treatment.label == "No Evidence of this Cancer"

    assert ma.treatment_target.id == "ICD10:C23"
    assert ma.treatment_target.label == "Malignant neoplasm of gallbladder"



async def test_get_medical_actions_cumulative_dose(db_session):

    person_id = await create_base_person(db_session)

    await insert_concept(
        db_session,
        42426831,
        "Carboplatin",
        vocabulary_id="RxNorm",
        code="42426831",
    )
    # mg/m2 unit concept
    await insert_concept(
        db_session,
        4223319,
        "mg/m2",
        vocabulary_id="SNOMED",
        code="404216004",
    )
    await insert_concept(
        db_session,
        40491906,
        "Curative intent",
        vocabulary_id="SNOMED",
        code="373808002",
    )

    treat_ep = await create_episode(
        db_session, {"person_id": person_id, "episode_concept_id": 32531}
    )
    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4133895,
            "value_as_concept_id": 40491906,
            "observation_event_id": treat_ep["episode_id"],
        },
    )

    drug_ep = await create_episode(
        db_session, {"person_id": person_id, "episode_concept_id": 32941}
    )
    await create_episode_event(
        db_session,
        {
            "episode_id": treat_ep["episode_id"],
            "event_id": drug_ep["episode_id"],
            "episode_event_field_concept_id": 798885,
        },
    )

    drug_exposure = await create_drug_exposure(
        db_session,
        {
            "person_id": person_id,
            "drug_concept_id": 42426831,
            "drug_type_concept_id": 32833,
            "quantity": 55.7,
            "dose_unit_source_value": "mg/m2",
            "drug_exposure_start_date": date(2021, 3, 1),
        },
    )
    await create_episode_event(
        db_session,
        {
            "episode_id": drug_ep["episode_id"],
            "event_id": drug_exposure["drug_exposure_id"],
            "episode_event_field_concept_id": 1147094,
        },
    )

    await db_session.flush()

    medical_actions = await get_medical_actions(person_id)

    assert medical_actions is not None
    assert len(medical_actions) >= 1

    ma = medical_actions[0]
    assert ma.treatment is not None
    assert ma.treatment.agent.id == "RxNorm:42426831"

    assert ma.treatment.cumulative_dose is not None
    assert ma.treatment.cumulative_dose.value == pytest.approx(55.7)
    assert ma.treatment.cumulative_dose.unit.id == "SNOMED:404216004"
    assert ma.treatment.cumulative_dose.unit.label == "mg/m2"



async def test_get_medical_actions_procedure(db_session):

    person_id = await create_base_person(db_session)

    await insert_concept(
        db_session,
        4281521,
        "Excision of breast with excision of regional lymph nodes",
        vocabulary_id="SNOMED",
        code="66398006",
    )
    await insert_concept(
        db_session,
        44497885,
        "Overlapping lesion of female genital organs",
        vocabulary_id="SNOMED",
        code="C57.8",
    )
    await insert_concept(
        db_session,
        40491908,
        "Curative - procedure intent",
        vocabulary_id="SNOMED",
        code="373847000",
    )

    surgery_ep = await create_episode(
        db_session, {"person_id": person_id, "episode_concept_id": 32939}
    )
    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4133895,
            "value_as_concept_id": 40491908,
            "observation_event_id": surgery_ep["episode_id"],
        },
    )

    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4181646,
            "value_as_concept_id": 44497885,
            "observation_event_id": surgery_ep["episode_id"],
            "obs_event_field_concept_id": 798885,
        },
    )

    procedure = await create_procedure_occurrence(
        db_session,
        {
            "person_id": person_id,
            "procedure_concept_id": 4281521,
            "procedure_date": date(2020, 2, 20),
        },
    )
    await create_episode_event(
        db_session,
        {
            "episode_id": surgery_ep["episode_id"],
            "event_id": procedure["procedure_occurrence_id"],
            "episode_event_field_concept_id": 1147082,
        },
    )

    await db_session.flush()

    medical_actions = await get_medical_actions(person_id)

    assert medical_actions is not None
    assert len(medical_actions) >= 1

    proc_ma = next((ma for ma in medical_actions if ma.HasField("procedure")), None)
    assert proc_ma is not None

    # Procedure code
    assert proc_ma.procedure.code.id == "SNOMED:66398006"
    assert (
        proc_ma.procedure.code.label
        == "Excision of breast with excision of regional lymph nodes"
    )

    # Body site
    assert proc_ma.procedure.body_site.id == "SNOMED:C57.8"
    assert (
        proc_ma.procedure.body_site.label
        == "Overlapping lesion of female genital organs"
    )

    # Performed date
    assert proc_ma.procedure.performed is not None
    performed_dt = proc_ma.procedure.performed.timestamp.ToDatetime()
    assert performed_dt.date() == date(2020, 2, 20)

    # Intent is present
    assert proc_ma.treatment_intent.id == "SNOMED:373847000"



async def test_get_medical_actions_radiation_therapy(db_session):

    person_id = await create_base_person(db_session)

    await insert_concept(
        db_session,
        607996,
        "External beam radiation therapy using photons",
        vocabulary_id="SNOMED",
        code="1156506007",
    )
    await insert_concept(
        db_session,
        36717353,
        "Structure of bone of left femur",
        vocabulary_id="SNOMED",
        code="722738000",
    )
    await insert_concept(
        db_session,
        40491910,
        "Radical radiotherapy intent",
        vocabulary_id="SNOMED",
        code="373846009",
    )

    # Radiotherapy episode with modality concept
    rt_ep = await create_episode(
        db_session,
        {
            "person_id": person_id,
            "episode_concept_id": 32940,
            "episode_object_concept_id": 607996,
        },
    )

    treat_ep = await create_episode(
        db_session, {"person_id": person_id, "episode_concept_id": 32531}
    )
    # episode_event
    await create_episode_event(
        db_session,
        {
            "episode_id": treat_ep["episode_id"],
            "event_id": rt_ep["episode_id"],
            "episode_event_field_concept_id": 798885,
        },
    )

    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4133895,
            "value_as_concept_id": 40491910,
            "observation_event_id": treat_ep["episode_id"],
        },
    )

    await create_observation(
        db_session,
        {
            "person_id": person_id,
            "observation_concept_id": 4181646,
            "value_as_concept_id": 36717353,
            "observation_event_id": rt_ep["episode_id"],
        },
    )

    # Total radiation dose: 60
    await create_measurement(
        db_session,
        {
            "person_id": person_id,
            "measurement_concept_id": 40483776,
            "value_as_number": 60.0,
        },
    )
    # Number of fractions: 25  (concept 4037631)
    await create_measurement(
        db_session,
        {
            "person_id": person_id,
            "measurement_concept_id": 4037631,
            "value_as_number": 25.0,
        },
    )

    await db_session.flush()

    medical_actions = await get_medical_actions(person_id)

    assert medical_actions is not None

    rt_ma = next(
        (ma for ma in medical_actions if ma.HasField("radiation_therapy")), None
    )
    assert rt_ma is not None

    rt = rt_ma.radiation_therapy

    # Modality
    assert rt.modality.id == "SNOMED:1156506007"
    assert rt.modality.label == "External beam radiation therapy using photons"

    # Body site
    assert rt.body_site.id == "SNOMED:722738000"
    assert rt.body_site.label == "Structure of bone of left femur"

    # Dosage
    assert rt.dosage == 60

    # Fractions
    assert rt.fractions == 25

    # Intent
    assert rt_ma.treatment_intent.id == "SNOMED:373846009"
