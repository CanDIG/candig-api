from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from phenopackets import OntologyClass

from src.api.phenopacket_operations import get_biosamples


def make_mock_session(mock_rows, mock_row_factory=None):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def session_gen():
        yield mock_session

    return session_gen()


def make_mock_biosample_row(overrides=None):
    """Build a default mock specimen row."""
    row = MagicMock()
    row.id = 88
    row.source_id = None
    row.sampled_tissue = 44497885
    row.time_of_collection = date(2023, 2, 15)
    row.histological_diagnosis = 44498902
    row.tumor_grade = 37164072
    row.sample_processing = 40480027
    row.sample_storage = 9177
    if overrides:
        for k, v in overrides.items():
            setattr(row, k, v)
    return row


SAMPLED_TISSUE_ONTOLOGY = OntologyClass(
    id="SNOMED:C57.8", label="Overlapping lesion of female genital organs"
)
HISTOLOGICAL_DIAGNOSIS_ONTOLOGY = OntologyClass(
    id="ICDO3:9726/3", label="Primary cutaneous gamma-delta T-cell lymphoma"
)
TUMOR_GRADE_ONTOLOGY = OntologyClass(id="SNOMED:1228845001", label="GX (AJCC)")
SAMPLE_PROCESSING_ONTOLOGY = OntologyClass(
    id="SNOMED:441652008", label="Formalin-fixed paraffin-embedded tissue specimen"
)
SAMPLE_STORAGE_ONTOLOGY = OntologyClass(id="SNOMED:74964007", label="Other")

DEFAULT_ONTOLOGY_MAP = {
    44497885: SAMPLED_TISSUE_ONTOLOGY,
    44498902: HISTOLOGICAL_DIAGNOSIS_ONTOLOGY,
    37164072: TUMOR_GRADE_ONTOLOGY,
    40480027: SAMPLE_PROCESSING_ONTOLOGY,
    9177: SAMPLE_STORAGE_ONTOLOGY,
}


# ---------------------------------------------------------------------------
# 2.3  sampled_tissue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_sampled_tissue_mapped(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    """sampled_tissue should be mapped from anatomic_site_concept_id."""
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row({"sampled_tissue": 44497885})
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert biosamples[0].sampled_tissue.id == "SNOMED:C57.8"
    assert (
        biosamples[0].sampled_tissue.label
        == "Overlapping lesion of female genital organs"
    )


# ---------------------------------------------------------------------------
# 2.5  time_of_collection
# ---------------------------------------------------------------------------

TIME_OF_COLLECTION_CASES = [
    pytest.param(
        {"time_of_collection": date(2023, 2, 15)},
        True,
        id="valid date -> timestamp set",
    ),
    pytest.param(
        {"time_of_collection": None},
        False,
        id="NULL date -> timestamp unset",
    ),
    pytest.param(
        {"time_of_collection": date(1800, 1, 1)},
        False,
        id="sentinel date 1800-01-01 -> timestamp unset",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,expect_set", TIME_OF_COLLECTION_CASES)
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_time_of_collection(
    mock_get_bm,
    mock_get_mc,
    mock_get_ontologies,
    mock_get_db_session,
    overrides,
    expect_set,
):
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row(overrides)
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    toc = biosamples[0].time_of_collection
    if expect_set:
        assert toc is not None and toc.HasField("timestamp"), (
            "time_of_collection should be a set TimeElement with timestamp"
        )
    else:
        assert toc is None or not toc.HasField("timestamp"), (
            "time_of_collection should be unset"
        )


# ---------------------------------------------------------------------------
# 2.6  histological_diagnosis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_histological_diagnosis_mapped(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row({"histological_diagnosis": 44498902})
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert biosamples[0].histological_diagnosis.id == "ICDO3:9726/3"
    assert (
        biosamples[0].histological_diagnosis.label
        == "Primary cutaneous gamma-delta T-cell lymphoma"
    )


# ---------------------------------------------------------------------------
# 2.7  tumor_grade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_tumor_grade_mapped(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row({"tumor_grade": 37164072})
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert biosamples[0].tumor_grade.id == "SNOMED:1228845001"
    assert biosamples[0].tumor_grade.label == "GX (AJCC)"


# ---------------------------------------------------------------------------
# 2.8  pathological_tnm_finding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_pathological_tnm_finding_populated(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    """pathological_tnm_finding should be populated from get_measurement_concepts."""
    tnm = [
        OntologyClass(id="LOINC:LA3624-9", label="T3"),
        OntologyClass(id="LOINC:LA4517-4", label="N2b"),
    ]
    mock_get_mc.return_value = tnm
    mock_get_bm.return_value = {}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row()
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert len(biosamples[0].pathological_tnm_finding) == 2
    assert biosamples[0].pathological_tnm_finding[0].id == "LOINC:LA3624-9"
    assert biosamples[0].pathological_tnm_finding[1].id == "LOINC:LA4517-4"


# ---------------------------------------------------------------------------
# 2.9  sample_processing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_sample_processing_mapped(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row({"sample_processing": 40480027})
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert biosamples[0].sample_processing.id == "SNOMED:441652008"
    assert (
        biosamples[0].sample_processing.label
        == "Formalin-fixed paraffin-embedded tissue specimen"
    )


# ---------------------------------------------------------------------------
# 2.10  sample_storage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_sample_storage_mapped(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row({"sample_storage": 9177})
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert biosamples[0].sample_storage.id == "SNOMED:74964007"
    assert biosamples[0].sample_storage.label == "Other"


# ---------------------------------------------------------------------------
# 2.11  measurements (biosample-level)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_biosample_measurements_attached(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    """Measurements linked to specimen_id should be attached to the biosample."""
    from phenopackets import Measurement
    from phenopackets import OntologyClass as OC

    specimen_id = 88
    real_measurement = Measurement(
        assay=OC(
            id="LOINC:85319-2",
            label="HER2 [Presence] in Breast cancer specimen by Immune stain",
        )
    )
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {specimen_id: [real_measurement]}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row({"id": specimen_id})
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert len(biosamples[0].measurements) == 1
    assert biosamples[0].measurements[0].assay.id == "LOINC:85319-2"


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_biosample_multiple_measurements_attached(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    """Multiple measurements linked to specimen_id should all be attached."""
    from phenopackets import Measurement
    from phenopackets import OntologyClass as OC

    specimen_id = 88
    measurements = [
        Measurement(assay=OC(id="LOINC:85319-2", label="HER2")),
        Measurement(assay=OC(id="LOINC:85318-4", label="HER2 [Presence] in Tissue")),
    ]
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {specimen_id: measurements}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row({"id": specimen_id})
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert len(biosamples[0].measurements) == 2


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_biosample_measurements_not_attached_for_other_specimen(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    """Measurements for a different specimen_id must not attach to this biosample."""
    from phenopackets import Measurement
    from phenopackets import OntologyClass as OC

    real_measurement = Measurement(assay=OC(id="LOINC:85319-2", label="HER2"))
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {999: [real_measurement]}  # different specimen id
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    row = make_mock_biosample_row({"id": 88})
    mock_get_db_session.return_value = make_mock_session([row])

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert len(biosamples[0].measurements) == 0


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_biosample_measurements_correct_specimen_among_multiple(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    """Only measurements matching the specimen_id should be attached to each biosample."""
    from phenopackets import Measurement
    from phenopackets import OntologyClass as OC

    m1 = Measurement(assay=OC(id="LOINC:111-1", label="Test 1"))
    m2 = Measurement(assay=OC(id="LOINC:222-2", label="Test 2"))
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {1: [m1], 2: [m2]}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    rows = [
        make_mock_biosample_row({"id": 1}),
        make_mock_biosample_row({"id": 2}),
    ]
    mock_get_db_session.return_value = make_mock_session(rows)

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert len(biosamples) == 2
    bs_by_id = {b.id: b for b in biosamples}
    assert len(bs_by_id["1"].measurements) == 1
    assert bs_by_id["1"].measurements[0].assay.id == "LOINC:111-1"
    assert len(bs_by_id["2"].measurements) == 1
    assert bs_by_id["2"].measurements[0].assay.id == "LOINC:222-2"


# ---------------------------------------------------------------------------
# multiple specimens -> multiple biosamples
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch(
    "src.api.phenopacket_operations.get_measurement_concepts", new_callable=AsyncMock
)
@patch(
    "src.api.phenopacket_operations.get_biosamples_measurements", new_callable=AsyncMock
)
async def test_multiple_specimens_returns_multiple_biosamples(
    mock_get_bm, mock_get_mc, mock_get_ontologies, mock_get_db_session
):
    """Each specimen row should produce one Biosample object."""
    mock_get_mc.return_value = []
    mock_get_bm.return_value = {}
    mock_get_ontologies.return_value = DEFAULT_ONTOLOGY_MAP
    rows = [
        make_mock_biosample_row({"id": 1}),
        make_mock_biosample_row({"id": 2}),
        make_mock_biosample_row({"id": 3}),
    ]
    mock_get_db_session.return_value = make_mock_session(rows)

    biosamples, status = await get_biosamples(1)

    assert status == 200
    assert len(biosamples) == 3
    assert {b.id for b in biosamples} == {"1", "2", "3"}
