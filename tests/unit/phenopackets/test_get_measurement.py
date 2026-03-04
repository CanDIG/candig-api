from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.phenopacket_operations import get_measurements

def make_mock_session(mock_rows):
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def session_gen():
        yield mock_session

    return session_gen()


def make_measurement_row(
    measurement_value_concept_id=None,
    measurement_value=None,
    measurement_type_concept_id=1001,
    measurement_date=date(2023, 1, 1),
    measurement_unit_concept_id=None,
):
    row = MagicMock()
    row.measurement_value_concept_id = measurement_value_concept_id
    row.measurement_value = measurement_value
    row.measurement_type_concept_id = measurement_type_concept_id
    row.measurement_date = measurement_date
    row.measurement_unit_concept_id = measurement_unit_concept_id
    return row


MINIMAL_MAPPING = [
    {
        "omop_object": "observation",
        "filtering_field": "observation_concept_id",
        "concept_value_field": "value_as_concept_id",
        "number_value_field": "value_as_number",
        "date_field": "observation_date",
        "unit_field": "unit_concept_id",
        "concept_ids": [111, 222],
        "ancestor_ids": [],
    }
]

@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.settings")
async def test_get_measurements_ontology_value(
    mock_settings, mock_get_ontologies, mock_get_db_session
):
    """
    When measurement_value_concept_id is set, Measurement.value should use
    Value(ontology_class=...).
    """
    from phenopackets import OntologyClass

    mock_settings.MAPPING_JSON = {"measurements": MINIMAL_MAPPING}
    mock_settings.CDM_SCHEMA = "omop"

    assay_ontology = OntologyClass(id="LOINC:12345", label="Some Assay")
    value_ontology = OntologyClass(id="SNOMED:67890", label="Some Value")

    mock_get_ontologies.return_value = {
        1001: assay_ontology,
        9001: value_ontology,
        4129922: OntologyClass(id="SNOMED:261665006", label="Unknown"),
    }

    row = make_measurement_row(measurement_value_concept_id=9001)
    mock_get_db_session.return_value = make_mock_session([row])

    result = await get_measurements(1)

    assert result is not None
    assert len(result) == 1
    measurement = result[0]
    assert measurement.value.HasField("ontology_class"), (
        "Expected value to use ontology_class field"
    )
    assert measurement.value.ontology_class == value_ontology
    assert measurement.assay == assay_ontology


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.settings")
async def test_get_measurements_numeric_value(
    mock_settings, mock_get_ontologies, mock_get_db_session
):
    """
    When measurement_value_concept_id is None but measurement_value (numeric) is set,
    Measurement.value should use Value(quantity=Quantity(...)).
    """
    from phenopackets import OntologyClass

    mock_settings.MAPPING_JSON = {"measurements": MINIMAL_MAPPING}
    mock_settings.CDM_SCHEMA = "omop"

    assay_ontology = OntologyClass(id="LOINC:12345", label="Some Assay")
    unit_ontology = OntologyClass(id="UCUM:mg", label="milligram")
    fallback_unit = OntologyClass(id="SNOMED:261665006", label="Unknown")

    mock_get_ontologies.return_value = {
        1001: assay_ontology,
        2002: unit_ontology,
        4129922: fallback_unit,
    }

    row = make_measurement_row(
        measurement_value_concept_id=None,
        measurement_value=42.0,
        measurement_unit_concept_id=2002,
    )
    mock_get_db_session.return_value = make_mock_session([row])

    result = await get_measurements(1)

    assert result is not None
    assert len(result) == 1
    measurement = result[0]
    assert measurement.value.HasField("quantity"), (
        "Expected value to use quantity field"
    )
    assert measurement.value.quantity.value == 42.0
    assert measurement.value.quantity.unit == unit_ontology


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.settings")
async def test_get_measurements_numeric_value_fallback_unit(
    mock_settings, mock_get_ontologies, mock_get_db_session
):
    """
    When measurement_unit_concept_id maps to nothing, fallback to concept 4129922 unit.
    """
    from phenopackets import OntologyClass

    mock_settings.MAPPING_JSON = {"measurements": MINIMAL_MAPPING}
    mock_settings.CDM_SCHEMA = "omop"

    fallback_unit = OntologyClass(id="SNOMED:261665006", label="Unknown")

    mock_get_ontologies.return_value = {
        1001: OntologyClass(id="LOINC:12345", label="Some Assay"),
        4129922: fallback_unit,
    }

    row = make_measurement_row(
        measurement_value_concept_id=None,
        measurement_value=5.5,
        measurement_unit_concept_id=9999,  # not in ontology_map
    )
    mock_get_db_session.return_value = make_mock_session([row])

    result = await get_measurements(1)

    assert result is not None
    assert len(result) == 1
    assert result[0].value.quantity.unit == fallback_unit


@pytest.mark.asyncio
@patch("src.api.phenopacket_operations.get_db_session")
@patch("src.api.phenopacket_operations.get_ontologies", new_callable=AsyncMock)
@patch("src.api.phenopacket_operations.settings")
async def test_get_measurements_multiple_mappings_aggregates_results(
    mock_settings, mock_get_ontologies, mock_get_db_session
):
    """
    With two mappings, results from both should be aggregated into one list.
    Each mapping triggers a separate get_db_session call.
    """
    from phenopackets import OntologyClass

    mapping_observation = {
        "omop_object": "observation",
        "filtering_field": "observation_concept_id",
        "concept_value_field": "value_as_concept_id",
        "number_value_field": "value_as_number",
        "date_field": "observation_date",
        "unit_field": "unit_concept_id",
        "concept_ids": [111],
        "ancestor_ids": [],
    }
    mapping_measurement = {
        "omop_object": "measurement",
        "filtering_field": "measurement_concept_id",
        "concept_value_field": "value_as_concept_id",
        "number_value_field": "value_as_number",
        "date_field": "measurement_date",
        "unit_field": "unit_concept_id",
        "concept_ids": [],
        "ancestor_ids": [999],
    }

    mock_settings.MAPPING_JSON = {
        "measurements": [mapping_observation, mapping_measurement]
    }
    mock_settings.CDM_SCHEMA = "omop"

    ontology_a = OntologyClass(id="LOINC:A", label="Assay A")
    value_a = OntologyClass(id="SNOMED:A", label="Value A")
    ontology_b = OntologyClass(id="LOINC:B", label="Assay B")
    value_b = OntologyClass(id="SNOMED:B", label="Value B")
    fallback = OntologyClass(id="SNOMED:261665006", label="Unknown")

    row_a = make_measurement_row(
        measurement_value_concept_id=8001, measurement_type_concept_id=1001
    )
    row_b = make_measurement_row(
        measurement_value_concept_id=8002, measurement_type_concept_id=1002
    )

    call_count = 0

    def session_factory():
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            return make_mock_session([row_a])
        else:
            return make_mock_session([row_b])

    mock_get_db_session.side_effect = lambda: session_factory()

    def ontology_side_effect(concept_ids):
        result = {4129922: fallback}
        if 8001 in (concept_ids or []):
            result.update({1001: ontology_a, 8001: value_a})
        if 8002 in (concept_ids or []):
            result.update({1002: ontology_b, 8002: value_b})
        return result

    mock_get_ontologies.side_effect = ontology_side_effect

    result = await get_measurements(1)

    assert result is not None
    assert len(result) == 2
