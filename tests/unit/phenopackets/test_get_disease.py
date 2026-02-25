from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.phenopacket_operations import get_diseases


def make_mock_session(mock_rows, extra_rows=None):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def session_gen():
        yield mock_session

    return session_gen()


def make_mock_disease_row(overrides=None):
    """
    Build a default mock row representing a disease from the SQL query in get_diseases.
    """
    row = MagicMock()
    row.term = 45590880
    row.onset = date(2019, 6, 1)
    row.resolution = date(2020, 1, 1)
    row.primary_site_concept_id = 44497844
    if overrides:
        for k, v in overrides.items():
            setattr(row, k, v)
    return row


def make_ontology_map(concept_ids):
    """
    Return a mock ontology map for the given concept IDs.
    """
    from phenopackets import OntologyClass

    ontology_map = {}
    labels = {
        45590880: ("ICD10", "C23", "Malignant neoplasm of gallbladder"),
        44497844: ("ICDO3", "C50", "Breast"),
        4164336: ("LOINC", "LA3608-2", "Tis"),
        4164182: ("LOINC", "LA4368-2", "N0"),
        4164466: ("LOINC", "LA3608-3", "M0"),
        35918306: ("Cancer Modifier", "OMOP4999911", "Left"),
        37163866: ("LOINC", "LA3668-6", "Stage B"),
    }
    for cid in concept_ids:
        if cid in labels:
            vocab, code, label = labels[cid]
            ontology_map[cid] = OntologyClass(id=f"{vocab}:{code}", label=label)
    return ontology_map


# ---------------------------------------------------------------------------
# 3.1  term  – condition_concept_id -> OntologyClass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_concept_by_id_or_ancestor",
    new_callable=AsyncMock,
)
async def test_disease_term_mapped(
    mock_get_ancestor, mock_get_measurement, mock_get_ontologies, mock_get_db_session
):
    """condition_concept_id is mapped to an OntologyClass term."""
    mock_get_ancestor.return_value = []
    mock_get_measurement.return_value = []
    mock_get_ontologies.return_value = make_ontology_map([45590880, 44497844])

    row = make_mock_disease_row()
    mock_get_db_session.return_value = make_mock_session([row])

    diseases, status_code = await get_diseases(1)

    assert status_code == 200
    assert len(diseases) == 1
    assert diseases[0].term.id == "ICD10:C23"
    assert diseases[0].term.label == "Malignant neoplasm of gallbladder"


# ---------------------------------------------------------------------------
# 3.2  onset – condition_start_date -> timestamp
# ---------------------------------------------------------------------------

ONSET_CASES = [
    pytest.param(
        {"onset": date(2019, 6, 1)},
        (2019, 6, 1),
        id="onset present -> timestamp 2019-06-01",
    ),
    pytest.param(
        {"onset": None},
        None,
        id="NULL onset -> no onset set",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,exp_date", ONSET_CASES)
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_concept_by_id_or_ancestor",
    new_callable=AsyncMock,
)
async def test_disease_onset(
    mock_get_ancestor,
    mock_get_measurement,
    mock_get_ontologies,
    mock_get_db_session,
    overrides,
    exp_date,
):
    mock_get_ancestor.return_value = []
    mock_get_measurement.return_value = []
    mock_get_ontologies.return_value = make_ontology_map([45590880, 44497844])

    row = make_mock_disease_row(overrides)
    mock_get_db_session.return_value = make_mock_session([row])

    diseases, status_code = await get_diseases(1)

    assert status_code == 200
    assert len(diseases) == 1

    if exp_date is None:
        assert (
            not diseases[0].onset.HasField("timestamp") if diseases[0].onset else True
        )
    else:
        onset_dt = diseases[0].onset.timestamp.ToDatetime()
        assert (onset_dt.year, onset_dt.month, onset_dt.day) == exp_date


# ---------------------------------------------------------------------------
# 3.3  resolution – condition_end_date -> timestamp
# ---------------------------------------------------------------------------

RESOLUTION_CASES = [
    pytest.param(
        {"resolution": date(2020, 1, 1)},
        (2020, 1, 1),
        id="resolution present -> timestamp 2020-01-01",
    ),
    pytest.param(
        {"resolution": None},
        None,
        id="NULL resolution -> no resolution set",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,exp_date", RESOLUTION_CASES)
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_concept_by_id_or_ancestor",
    new_callable=AsyncMock,
)
async def test_disease_resolution(
    mock_get_ancestor,
    mock_get_measurement,
    mock_get_ontologies,
    mock_get_db_session,
    overrides,
    exp_date,
):
    mock_get_ancestor.return_value = []
    mock_get_measurement.return_value = []
    mock_get_ontologies.return_value = make_ontology_map([45590880, 44497844])

    row = make_mock_disease_row(overrides)
    mock_get_db_session.return_value = make_mock_session([row])

    diseases, status_code = await get_diseases(1)

    assert status_code == 200
    assert len(diseases) == 1

    if exp_date is None:
        assert (
            not diseases[0].resolution.HasField("timestamp")
            if diseases[0].resolution
            else True
        )
    else:
        res_dt = diseases[0].resolution.timestamp.ToDatetime()
        assert (res_dt.year, res_dt.month, res_dt.day) == exp_date


# ---------------------------------------------------------------------------
# 3.4  primary_site – observation.value_as_concept_id -> OntologyClass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_concept_by_id_or_ancestor",
    new_callable=AsyncMock,
)
async def test_primary_site_mapped(
    mock_get_ancestor, mock_get_measurement, mock_get_ontologies, mock_get_db_session
):
    """primary_site_concept_id maps to an OntologyClass."""
    mock_get_ancestor.return_value = []
    mock_get_measurement.return_value = []
    mock_get_ontologies.return_value = make_ontology_map([45590880, 44497844])

    row = make_mock_disease_row({"primary_site_concept_id": 44497844})
    mock_get_db_session.return_value = make_mock_session([row])

    diseases, status_code = await get_diseases(1)

    assert status_code == 200
    assert diseases[0].primary_site.id == "ICDO3:C50"
    assert diseases[0].primary_site.label == "Breast"


# ---------------------------------------------------------------------------
# 3.5  disease_stage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_concept_by_id_or_ancestor",
    new_callable=AsyncMock,
)
async def test_disease_stage_populated(
    mock_get_ancestor, mock_get_measurement, mock_get_ontologies, mock_get_db_session
):
    """disease_stage list from get_concept_by_id_or_ancestor is propagated."""
    from phenopackets import OntologyClass

    stage = OntologyClass(id="LOINC:LA3668-6", label="Stage B")
    mock_get_ancestor.return_value = [stage]
    mock_get_measurement.return_value = []
    mock_get_ontologies.return_value = make_ontology_map([45590880, 44497844])

    row = make_mock_disease_row()
    mock_get_db_session.return_value = make_mock_session([row])

    diseases, status_code = await get_diseases(1)

    assert status_code == 200
    assert len(diseases[0].disease_stage) == 1
    assert diseases[0].disease_stage[0].id == "LOINC:LA3668-6"


# ---------------------------------------------------------------------------
# 3.6  clinical_tnm_finding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_concept_by_id_or_ancestor",
    new_callable=AsyncMock,
)
async def test_clinical_tnm_finding_populated(
    mock_get_ancestor, mock_get_measurement, mock_get_ontologies, mock_get_db_session
):
    """clinical_tnm_finding list is propagated to every disease object."""
    from phenopackets import OntologyClass

    tnm_t = OntologyClass(id="LOINC:LA3608-2", label="Tis")
    tnm_n = OntologyClass(id="LOINC:LA4368-2", label="N0")

    mock_get_ancestor.return_value = []
    # First call: clinical_tnm, second call: laterality
    mock_get_measurement.side_effect = [[tnm_t, tnm_n], []]
    mock_get_ontologies.return_value = make_ontology_map([45590880, 44497844])

    row = make_mock_disease_row()
    mock_get_db_session.return_value = make_mock_session([row])

    diseases, status_code = await get_diseases(1)

    assert status_code == 200
    assert len(diseases[0].clinical_tnm_finding) == 2
    ids = [t.id for t in diseases[0].clinical_tnm_finding]
    assert "LOINC:LA3608-2" in ids
    assert "LOINC:LA4368-2" in ids


# ---------------------------------------------------------------------------
# 3.7  laterality
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_concept_by_id_or_ancestor",
    new_callable=AsyncMock,
)
async def test_laterality_populated(
    mock_get_ancestor, mock_get_measurement, mock_get_ontologies, mock_get_db_session
):
    """laterality uses only the first element from the measurement list."""
    from phenopackets import OntologyClass

    left = OntologyClass(id="Cancer Modifier:OMOP4999911", label="Left")

    mock_get_ancestor.return_value = []
    mock_get_measurement.side_effect = [[], [left]]
    mock_get_ontologies.return_value = make_ontology_map([45590880, 44497844])

    row = make_mock_disease_row()
    mock_get_db_session.return_value = make_mock_session([row])

    diseases, status_code = await get_diseases(1)

    assert status_code == 200
    assert diseases[0].laterality.id == "Cancer Modifier:OMOP4999911"
    assert diseases[0].laterality.label == "Left"


# ---------------------------------------------------------------------------
# Multiple diseases for one person
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_concept_by_id_or_ancestor",
    new_callable=AsyncMock,
)
async def test_multiple_diseases(
    mock_get_ancestor, mock_get_measurement, mock_get_ontologies, mock_get_db_session
):
    """Multiple disease rows produce multiple Disease objects."""
    from phenopackets import OntologyClass

    mock_get_ancestor.return_value = []
    mock_get_measurement.return_value = []

    row1 = make_mock_disease_row()
    row2 = make_mock_disease_row(
        {
            "term": 45590881,
            "onset": date(2021, 3, 15),
            "resolution": None,
            "primary_site_concept_id": None,
        }
    )

    ontology_map = make_ontology_map([45590880, 44497844])
    ontology_map[45590881] = OntologyClass(
        id="ICD10:C50", label="Malignant neoplasm of breast"
    )
    mock_get_ontologies.return_value = ontology_map

    mock_get_db_session.return_value = make_mock_session([row1, row2])

    diseases, status_code = await get_diseases(1)

    assert status_code == 200
    assert len(diseases) == 2
