from unittest.mock import AsyncMock, patch
from typing import Any, cast

import pytest
from google.protobuf.timestamp_pb2 import Timestamp
from phenopackets import (
    Biosample,
    Disease,
    Individual,
    Measurement,
    MedicalAction,
    MetaData,
    OntologyClass,
    Procedure,
    Resource,
    VitalStatus,
)

from src.api.phenopacket_operations import get_by_id

PATCH_IS_ACTION_ALLOWED = "src.api.phenopacket_operations.is_action_allowed"
PATCH_IS_PERSON_IN_DATASET = "src.api.phenopacket_operations.is_person_in_dataset"
PATCH_GET_SUBJECT = "src.api.phenopacket_operations.get_subject"
PATCH_GET_DISEASES = "src.api.phenopacket_operations.get_diseases"
PATCH_GET_MEDICAL_ACTIONS = "src.api.phenopacket_operations.get_medical_actions"
PATCH_GET_BIOSAMPLES = "src.api.phenopacket_operations.get_biosamples"
PATCH_GET_MEASUREMENTS = "src.api.phenopacket_operations.get_measurements"
PATCH_GET_META_DATA = "src.api.phenopacket_operations.get_meta_data"


@pytest.mark.asyncio
@patch(PATCH_IS_ACTION_ALLOWED, return_value=True)
@patch(PATCH_IS_PERSON_IN_DATASET, new_callable=AsyncMock, return_value=True)
@patch(PATCH_GET_SUBJECT, new_callable=AsyncMock)
@patch(PATCH_GET_DISEASES, new_callable=AsyncMock)
@patch(PATCH_GET_MEDICAL_ACTIONS, new_callable=AsyncMock)
@patch(PATCH_GET_BIOSAMPLES, new_callable=AsyncMock)
@patch(PATCH_GET_MEASUREMENTS, new_callable=AsyncMock)
@patch(PATCH_GET_META_DATA)
async def test_get_by_id_returns_full_phenopacket_schema(
    mock_meta_data,
    mock_measurements,
    mock_biosamples,
    mock_medical_actions,
    mock_diseases,
    mock_subject,
    mock_is_person_in_dataset,
    mock_is_action_allowed,
):
    subject = Individual(
        id="PATIENT_001",
        alternate_ids=["DONOR_001", "EXT_001"],
        sex="FEMALE",
        taxonomy=OntologyClass(id="SNOMED:337915000", label="Homo sapiens (organism)"),
        vital_status=VitalStatus(
            status=VitalStatus.DECEASED, survival_time_in_days=365
        ),
    )

    disease = Disease(
        term=OntologyClass(id="ICD10:C50", label="Malignant neoplasm of breast"),
        excluded=False,
    )

    biosample = Biosample(
        id="SAMPLE_001",
        individual_id="PATIENT_001",
        sampled_tissue=OntologyClass(id="UBERON:0001911", label="mammary gland"),
    )

    measurement = Measurement(
        assay=OntologyClass(id="LOINC:8302-2", label="Body height"),
    )

    medical_action = MedicalAction(
        procedure=Procedure(
            code=OntologyClass(id="NCIT:C28743", label="Biopsy"),
            performed=None,
        )
    )

    ts = Timestamp()
    ts.FromJsonString("2024-01-01T00:00:00Z")
    meta_data = MetaData(
        created=ts,
        created_by="DHDP",
        submitted_by="DHDP",
        phenopacket_schema_version="2.0.0",
        resources=[
            Resource(
                id="SNOMED",
                name="Systemized Nomenclature of Medicine",
                namespace_prefix="SNOMED",
                url="https://bioportal.bioontology.org/ontologies/SNOMEDCT",
                version="2025-02-01",
                iri_prefix="http://purl.bioontology.org/ontology/SNOMEDCT/",
            ),
            Resource(
                id="ICD10",
                name="International Classification of Diseases 10",
                namespace_prefix="ICD10",
                url="https://www.who.int/classifications/icd/en/",
                version="2024",
                iri_prefix="http://purl.bioontology.org/ontology/ICD10CM/",
            ),
        ],
    )

    mock_subject.return_value = (subject, 200)
    mock_diseases.return_value = ([disease], 200)
    mock_medical_actions.return_value = [medical_action]
    mock_biosamples.return_value = ([biosample], 200)
    mock_measurements.return_value = [measurement]
    mock_meta_data.return_value = meta_data

    result = cast(dict[str, Any], await get_by_id("dataset_1", 1))

    # Validate top-level Phenopacket schema fields
    assert "id" in result
    assert "subject" in result
    assert "diseases" in result
    assert "biosamples" in result
    assert "measurements" in result
    assert "medical_actions" in result
    assert "meta_data" in result

    # Validate subject schema
    assert result["subject"]["id"] == "PATIENT_001"
    assert result["subject"]["alternate_ids"] == ["DONOR_001", "EXT_001"]
    assert result["subject"]["sex"] == "FEMALE"
    assert "taxonomy" in result["subject"]
    assert result["subject"]["taxonomy"]["id"] == "SNOMED:337915000"
    assert result["subject"]["taxonomy"]["label"] == "Homo sapiens (organism)"
    assert result["subject"]["vital_status"]["status"] == "DECEASED"
    assert result["subject"]["vital_status"]["survival_time_in_days"] == 365

    # Validate diseases schema
    assert len(result["diseases"]) == 1
    assert result["diseases"][0]["term"]["id"] == "ICD10:C50"
    assert result["diseases"][0]["term"]["label"] == "Malignant neoplasm of breast"
    assert result["diseases"][0].get("excluded", False) is False

    # Validate biosamples schema
    assert len(result["biosamples"]) == 1
    assert result["biosamples"][0]["id"] == "SAMPLE_001"
    assert result["biosamples"][0]["individual_id"] == "PATIENT_001"
    assert result["biosamples"][0]["sampled_tissue"]["id"] == "UBERON:0001911"
    assert result["biosamples"][0]["sampled_tissue"]["label"] == "mammary gland"

    # Validate measurements schema
    assert len(result["measurements"]) == 1
    assert result["measurements"][0]["assay"]["id"] == "LOINC:8302-2"
    assert result["measurements"][0]["assay"]["label"] == "Body height"

    assert result["meta_data"]["created"] == "2024-01-01T00:00:00Z"
    assert result["meta_data"]["created_by"] == "DHDP"
    assert result["meta_data"]["submitted_by"] == "DHDP"
    assert result["meta_data"]["phenopacket_schema_version"] == "2.0.0"
    assert len(result["meta_data"]["resources"]) == 2
    assert result["meta_data"]["resources"][0]["id"] == "SNOMED"
    assert (
        result["meta_data"]["resources"][0]["name"]
        == "Systemized Nomenclature of Medicine"
    )
    assert result["meta_data"]["resources"][0]["namespace_prefix"] == "SNOMED"
    assert (
        result["meta_data"]["resources"][0]["url"]
        == "https://bioportal.bioontology.org/ontologies/SNOMEDCT"
    )
    assert result["meta_data"]["resources"][0]["version"] == "2025-02-01"
    assert (
        result["meta_data"]["resources"][0]["iri_prefix"]
        == "http://purl.bioontology.org/ontology/SNOMEDCT/"
    )
    assert result["meta_data"]["resources"][1]["id"] == "ICD10"
