from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.phenopacket_operations import get_medical_actions

def make_mock_session(mock_rows):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def session_gen():
        yield mock_session

    return session_gen()


def make_mock_procedure_row(overrides=None):
    row = MagicMock()
    row.procedure_concept_id = 4281521
    row.procedure_source_value = ""
    row.performed = date(2020, 2, 20)
    row.body_site_concept_id = 0
    if overrides:
        for k, v in overrides.items():
            setattr(row, k, v)
    return row


def make_mock_drug_row(overrides=None):
    row = MagicMock()
    row.drug_concept_id = 42426830
    row.drug_source_value = ""
    row.route_concept_id = None
    row.drug_type_concept_id = 32838
    row.quantity_unit = "mg"
    row.quantity_value = 55.7
    row.dose_intervals_start = None
    row.dose_intervals_end = None
    row.dose_intervals_quantity_unit = "mg"
    row.dose_intervals_quantity_value = 55.7
    if overrides:
        for k, v in overrides.items():
            setattr(row, k, v)
    return row


def make_mock_radiation_row(overrides=None):
    row = MagicMock()
    row.modality_concept_id = 607996
    row.body_site_concept_id = 36717353
    row.dosage = 60
    row.fractions = 25
    if overrides:
        for k, v in overrides.items():
            setattr(row, k, v)
    return row


def make_ontology_map():
    from phenopackets import OntologyClass

    return {
        4281521: OntologyClass(
            id="SNOMED:66398006",
            label="Excision of breast with excision of regional lymph nodes",
        ),
        42426830: OntologyClass(id="RxNorm:42426830", label="Tamoxifen"),
        607996: OntologyClass(
            id="SNOMED:1156506007",
            label="External beam radiation therapy using photons",
        ),
        36717353: OntologyClass(
            id="SNOMED:722738000", label="Structure of bone of left femur"
        ),
        40491905: OntologyClass(id="SNOMED:447295008", label="Forensic intent"),
        36310520: OntologyClass(
            id="LOINC:LA4566-1", label="No Evidence of this Cancer"
        ),
        45590880: OntologyClass(
            id="ICD10:C23", label="Malignant neoplasm of gallbladder"
        ),
    }


def patch_all(
    mock_get_db_session,
    mock_get_ontologies,
    mock_response_to_treatments,
    mock_treatment_intents,
    mock_treatment_targets,
    mock_treatment_agents,
    mock_procedures,
    mock_radiation_therapies,
    *,
    response_to_treatments=None,
    treatment_intents=None,
    treatment_targets=None,
    treatment_agents=None,
    procedures=None,
    radiation_therapies=None,
):
    from phenopackets import OntologyClass, Procedure, RadiationTherapy, Treatment

    mock_get_ontologies.return_value = make_ontology_map()
    mock_get_db_session.return_value = make_mock_session([])

    mock_response_to_treatments.return_value = (
        response_to_treatments
        if response_to_treatments is not None
        else {1: OntologyClass(id="LOINC:LA4566-1", label="No Evidence of this Cancer")}
    )
    mock_treatment_intents.return_value = (
        treatment_intents
        if treatment_intents is not None
        else {1: OntologyClass(id="SNOMED:447295008", label="Forensic intent")}
    )
    mock_treatment_targets.return_value = (
        treatment_targets
        if treatment_targets is not None
        else [OntologyClass(id="ICD10:C23", label="Malignant neoplasm of gallbladder")]
    )
    mock_treatment_agents.return_value = (
        treatment_agents
        if treatment_agents is not None
        else [
            Treatment(
                agent=OntologyClass(id="RxNorm:42426830", label="Tamoxifen"),
                drug_type="PRESCRIPTION",
            )
        ]
    )
    mock_procedures.return_value = (
        procedures
        if procedures is not None
        else [
            Procedure(
                code=OntologyClass(
                    id="SNOMED:66398006",
                    label="Excision of breast with excision of regional lymph nodes",
                ),
            )
        ]
    )
    mock_radiation_therapies.return_value = (
        radiation_therapies if radiation_therapies is not None else []
    )


# ---------------------------------------------------------------------------
# 4.5  treatment agent combined with response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_radiation_therapies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_procedures", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_agents", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_targets", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_medical_action_by_field", new_callable=AsyncMock
)
async def test_treatment_agent_produces_medical_action(
    mock_by_field,
    mock_targets,
    mock_agents,
    mock_procedures,
    mock_radiation,
    mock_ontologies,
    mock_db,
):
    """A treatment agent + response -> one MedicalAction with treatment set."""
    from phenopackets import OntologyClass, Treatment

    response = OntologyClass(id="LOINC:LA4566-1", label="No Evidence of this Cancer")
    intent = OntologyClass(id="SNOMED:447295008", label="Forensic intent")
    target = OntologyClass(id="ICD10:C23", label="Malignant neoplasm of gallbladder")
    agent = OntologyClass(id="RxNorm:42426830", label="Tamoxifen")

    mock_by_field.side_effect = [{1: response}, {1: intent}]
    mock_targets.return_value = [target]
    mock_agents.return_value = [Treatment(agent=agent, drug_type="PRESCRIPTION")]
    mock_procedures.return_value = []
    mock_radiation.return_value = []
    mock_ontologies.return_value = {}
    mock_db.return_value = make_mock_session([])

    result = await get_medical_actions(1)

    assert result is not None
    assert len(result) == 1
    ma = result[0]
    assert ma.HasField("treatment")
    assert ma.treatment.agent.id == "RxNorm:42426830"
    assert ma.treatment.drug_type == 1  # PRESCRIPTION enum value
    assert ma.treatment_target.id == "ICD10:C23"
    assert ma.treatment_intent.id == "SNOMED:447295008"
    assert ma.response_to_treatment.id == "LOINC:LA4566-1"


# ---------------------------------------------------------------------------
# 4.4  procedure combined with response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_radiation_therapies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_procedures", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_agents", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_targets", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_medical_action_by_field", new_callable=AsyncMock
)
async def test_procedure_produces_medical_action(
    mock_by_field,
    mock_targets,
    mock_agents,
    mock_procedures,
    mock_radiation,
    mock_ontologies,
    mock_db,
):
    """A procedure + response → one MedicalAction with procedure set."""
    from phenopackets import OntologyClass, Procedure

    response = OntologyClass(id="LOINC:LA4566-1", label="No Evidence of this Cancer")
    intent = OntologyClass(id="SNOMED:447295008", label="Forensic intent")
    target = OntologyClass(id="ICD10:C23", label="Malignant neoplasm of gallbladder")
    code = OntologyClass(
        id="SNOMED:66398006",
        label="Excision of breast with excision of regional lymph nodes",
    )

    mock_by_field.side_effect = [{1: response}, {1: intent}]
    mock_targets.return_value = [target]
    mock_agents.return_value = []
    mock_procedures.return_value = [Procedure(code=code)]
    mock_radiation.return_value = []
    mock_ontologies.return_value = {}
    mock_db.return_value = make_mock_session([])

    result = await get_medical_actions(1)

    assert result is not None
    assert len(result) == 1
    ma = result[0]
    assert ma.HasField("procedure")
    assert ma.procedure.code.id == "SNOMED:66398006"
    assert ma.treatment_target.id == "ICD10:C23"
    assert ma.treatment_intent.id == "SNOMED:447295008"
    assert ma.response_to_treatment.id == "LOINC:LA4566-1"


# ---------------------------------------------------------------------------
# 4.6  radiation therapy combined with response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_radiation_therapies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_procedures", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_agents", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_targets", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_medical_action_by_field", new_callable=AsyncMock
)
async def test_radiation_therapy_produces_medical_action(
    mock_by_field,
    mock_targets,
    mock_agents,
    mock_procedures,
    mock_radiation,
    mock_ontologies,
    mock_db,
):
    """A radiation therapy + response → one MedicalAction with radiation_therapy set."""
    from phenopackets import OntologyClass, RadiationTherapy

    response = OntologyClass(id="LOINC:LA4566-1", label="No Evidence of this Cancer")
    intent = OntologyClass(id="SNOMED:447295008", label="Forensic intent")
    target = OntologyClass(id="ICD10:C23", label="Malignant neoplasm of gallbladder")
    modality = OntologyClass(
        id="SNOMED:1156506007", label="External beam radiation therapy using photons"
    )
    body_site = OntologyClass(
        id="SNOMED:722738000", label="Structure of bone of left femur"
    )

    mock_by_field.side_effect = [{1: response}, {1: intent}]
    mock_targets.return_value = [target]
    mock_agents.return_value = []
    mock_procedures.return_value = []
    mock_radiation.return_value = [
        RadiationTherapy(
            modality=modality, body_site=body_site, dosage=60, fractions=25
        )
    ]
    mock_ontologies.return_value = {}
    mock_db.return_value = make_mock_session([])

    result = await get_medical_actions(1)

    assert result is not None
    assert len(result) == 1
    ma = result[0]
    assert ma.HasField("radiation_therapy")
    assert ma.radiation_therapy.modality.id == "SNOMED:1156506007"
    assert ma.radiation_therapy.dosage == 60
    assert ma.radiation_therapy.fractions == 25
    assert ma.treatment_target.id == "ICD10:C23"


# ---------------------------------------------------------------------------
# 4.  Combinations – multiple action types × multiple episodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_radiation_therapies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_procedures", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_agents", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_targets", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_medical_action_by_field", new_callable=AsyncMock
)
async def test_multiple_action_types_produces_correct_count(
    mock_by_field,
    mock_targets,
    mock_agents,
    mock_procedures,
    mock_radiation,
    mock_ontologies,
    mock_db,
):
    """1 agent + 1 procedure + 1 radiation × 1 episode = 3 MedicalAction objects."""
    from phenopackets import OntologyClass, Procedure, RadiationTherapy, Treatment

    response = OntologyClass(id="LOINC:LA4566-1", label="No Evidence of this Cancer")
    intent = OntologyClass(id="SNOMED:447295008", label="Forensic intent")
    target = OntologyClass(id="ICD10:C23", label="Malignant neoplasm of gallbladder")

    mock_by_field.side_effect = [{1: response}, {1: intent}]
    mock_targets.return_value = [target]
    mock_agents.return_value = [
        Treatment(
            agent=OntologyClass(id="RxNorm:42426830", label="Tamoxifen"),
            drug_type="PRESCRIPTION",
        )
    ]
    mock_procedures.return_value = [
        Procedure(code=OntologyClass(id="SNOMED:66398006", label="Surgery"))
    ]
    mock_radiation.return_value = [
        RadiationTherapy(
            modality=OntologyClass(id="SNOMED:1156506007", label="External beam"),
            body_site=OntologyClass(id="SNOMED:722738000", label="Femur"),
            dosage=60,
            fractions=25,
        )
    ]
    mock_ontologies.return_value = {}
    mock_db.return_value = make_mock_session([])

    result = await get_medical_actions(1)

    assert result is not None
    # 1 episode × (1 agent + 1 procedure + 1 radiation) = 3
    assert len(result) == 3
    action_types = {"treatment", "procedure", "radiation_therapy"}
    found = {ma.WhichOneof("action") for ma in result}
    assert found == action_types


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_radiation_therapies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_procedures", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_agents", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_targets", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_medical_action_by_field", new_callable=AsyncMock
)
async def test_two_episodes_two_agents_produces_four_actions(
    mock_by_field,
    mock_targets,
    mock_agents,
    mock_procedures,
    mock_radiation,
    mock_ontologies,
    mock_db,
):
    """2 episodes × 2 agents = 4 MedicalAction objects."""
    from phenopackets import OntologyClass, Treatment

    r1 = OntologyClass(id="LOINC:LA4566-1", label="No Evidence of this Cancer")
    r2 = OntologyClass(id="LOINC:LA4567-9", label="Partial response")
    i1 = OntologyClass(id="SNOMED:447295008", label="Forensic intent")
    i2 = OntologyClass(id="SNOMED:123456789", label="Curative intent")

    mock_by_field.side_effect = [{1: r1, 2: r2}, {1: i1, 2: i2}]
    mock_targets.return_value = [
        OntologyClass(id="ICD10:C23", label="Malignant neoplasm of gallbladder")
    ]
    mock_agents.return_value = [
        Treatment(
            agent=OntologyClass(id="RxNorm:42426830", label="Tamoxifen"),
            drug_type="PRESCRIPTION",
        ),
        Treatment(
            agent=OntologyClass(id="RxNorm:99999999", label="Ipilimumab"),
            drug_type="PRESCRIPTION",
        ),
    ]
    mock_procedures.return_value = []
    mock_radiation.return_value = []
    mock_ontologies.return_value = {}
    mock_db.return_value = make_mock_session([])

    result = await get_medical_actions(1)

    assert result is not None
    # 2 episodes × 2 agents = 4
    assert len(result) == 4


# ---------------------------------------------------------------------------
# 4.2 / 4.3 – missing intent or response defaults to "No value"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_radiation_therapies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_procedures", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_agents", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_targets", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_medical_action_by_field", new_callable=AsyncMock
)
async def test_missing_intent_defaults_to_no_value(
    mock_by_field,
    mock_targets,
    mock_agents,
    mock_procedures,
    mock_radiation,
    mock_ontologies,
    mock_db,
):
    """Episode present in response but not in intent → intent defaults to 'No value'."""
    from phenopackets import OntologyClass, Treatment

    response = OntologyClass(id="LOINC:LA4566-1", label="No Evidence of this Cancer")

    # episode 1 has a response but NO intent
    mock_by_field.side_effect = [{1: response}, {}]
    mock_targets.return_value = [
        OntologyClass(id="ICD10:C23", label="Malignant neoplasm of gallbladder")
    ]
    mock_agents.return_value = [
        Treatment(
            agent=OntologyClass(id="RxNorm:42426830", label="Tamoxifen"),
            drug_type="PRESCRIPTION",
        )
    ]
    mock_procedures.return_value = []
    mock_radiation.return_value = []
    mock_ontologies.return_value = {}
    mock_db.return_value = make_mock_session([])

    result = await get_medical_actions(1)

    assert result is not None
    assert len(result) == 1
    assert result[0].treatment_intent.id == "SNOMED:408094002"
    assert result[0].treatment_intent.label == "No value"


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_radiation_therapies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_procedures", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_agents", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.get_treatment_targets", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_medical_action_by_field", new_callable=AsyncMock
)
async def test_missing_response_defaults_to_no_value(
    mock_by_field,
    mock_targets,
    mock_agents,
    mock_procedures,
    mock_radiation,
    mock_ontologies,
    mock_db,
):
    """Episode present in intent but not in response → response defaults to 'No value'."""
    from phenopackets import OntologyClass, Treatment

    intent = OntologyClass(id="SNOMED:447295008", label="Forensic intent")

    # episode 1 in intent only, no matching response
    mock_by_field.side_effect = [{}, {1: intent}]
    mock_targets.return_value = [
        OntologyClass(id="ICD10:C23", label="Malignant neoplasm of gallbladder")
    ]
    mock_agents.return_value = [
        Treatment(
            agent=OntologyClass(id="RxNorm:42426830", label="Tamoxifen"),
            drug_type="PRESCRIPTION",
        )
    ]
    mock_procedures.return_value = []
    mock_radiation.return_value = []
    mock_ontologies.return_value = {}
    mock_db.return_value = make_mock_session([])

    result = await get_medical_actions(1)

    assert result is not None
    assert len(result) == 1
    assert result[0].response_to_treatment.id == "SNOMED:408094002"
    assert result[0].response_to_treatment.label == "No value"
