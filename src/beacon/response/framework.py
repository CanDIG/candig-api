"""
Beacon Framework Configuration Endpoints.
"""

# import logging

from ...beacon import conf

# LOG = logging.getLogger(__name__)
from ...beacon.omop.schemas import DefaultSchemas

from ...beacon.utils.stream import json_stream


def get_entry_types():
    return {
        "biosample": {
            "id": "biosample",
            "name": "Biological Sample",
            "ontologyTermForThisType": {
                "id": "NCIT:C70699",
                "label": "Biospecimen"
            },
            "partOfSpecification": "Beacon v2.0.0",
            "description": "Any material sample taken from a biological entity for testing, diagnostic, propagation, treatment or research purposes, including a sample obtained from a living organism or taken from the biological object after halting of all its life functions. Biospecimen can contain one or more components including but not limited to cellular molecules, cells, tissues, organs, body fluids, embryos, and body excretory products. [ NCI ]",
            "defaultSchema": {
                "id": DefaultSchemas.BIOSAMPLES.value['schema'],
                "name": "Default schema for a biological sample",
                "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/biosamples/defaultSchema.json",
                "schemaVersion": "v2.0.0"
            },
            "additionallySupportedSchemas": []
        },
        "cohort": {
            "id": "cohort",
            "name": "Cohort",
            "ontologyTermForThisType": {
                "id": "NCIT:C61512",
                "label": "Cohort"
            },
            "partOfSpecification": "Beacon v2.0.0",
            "description": "A group of individuals, identified by a common characteristic. [ NCI ]",
            "defaultSchema": {
                "id": DefaultSchemas.COHORTS.value['schema'],
                "name": "Default schema for cohorts",
                "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/cohorts/defaultSchema.json",
                "schemaVersion": "v2.0.0"
            },
            "aCollectionOf": [{"id": "individual", "name": "Individuals"}],
            "additionalSupportedSchemas": []
        },
        "individual": {
            "id": "individual",
            "name": "Individual",
            "ontologyTermForThisType": {
                "id": "NCIT:C25190",
                "label": "Person"
            },
            "partOfSpecification": "Beacon v2.0.0",
            "description": "A human being. It could be a Patient, a Tissue Donor, a Participant, a Human Study Subject, etc.",
            "defaultSchema": {
                "id": DefaultSchemas.INDIVIDUALS.value['schema'],
                "name": "Default schema for an individual",
                "referenceToSchemaDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/individuals/defaultSchema.json",
                "schemaVersion": "v2.0.0"
            },
            "additionallySupportedSchemas": []
        },
    }


async def configuration(request):
    meta = {
        '$schema': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/framework/json/responses/sections/beaconInformationalResponseMeta.json',
        'beaconId': conf.beacon_id,
        'apiVersion': conf.api_version,
        'returnedSchemas': []
    }

    response = {
        '$schema': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/framework/json/configuration/beaconConfigurationSchema.json',
        'maturityAttributes': {
            'productionStatus': 'DEV'
        },
        'securityAttributes': {
            'defaultGranularity': 'record',
            'securityLevels': ['PUBLIC', 'REGISTERED', 'CONTROLLED']
        },
        'entryTypes': get_entry_types()
    }

    configuration_json = {
        '$schema': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/framework/json/responses/beaconConfigurationResponse.json',
        'meta': meta,
        'response': response
    }

    return await json_stream(request, configuration_json)


async def entry_types(request):
    meta = {
        'beaconId': conf.beacon_id,
        'apiVersion': conf.api_version,
        'returnedSchemas': []
    }

    response = {
        "entryTypes": get_entry_types()
    }

    entry_types_json = {
        'meta': meta,
        'response': response
    }

    return await json_stream(request, entry_types_json)

async def filtering_terms(request):

    filtering_terms_json = {}

    return await json_stream(request, filtering_terms_json)

async def beacon_map(request):
    meta = {
        '$schema': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/framework/json/responses/sections/beaconInformationalResponseMeta.json',
        'beaconId': conf.beacon_id,
        'apiVersion': conf.api_version,
        'returnedSchemas': []
    }

    response = {
        '$schema': 'https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/framework/json/configuration/beaconMapSchema.json',
        "endpointSets": {
            "biosample": {
                "entryType": "biosample",
                "openAPIEndpointsDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/biosamples/endpoints.json",
                "rootUrl": conf.uri + "/biosamples",
                "singleEntryUrl": conf.uri + "/biosamples/{id}",
                "filteringTermsUrl": conf.uri + "/biosamples/filtering_terms",
            },
            "cohort": {
                "entryType": "cohort",
                "openAPIEndpointsDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/cohorts/endpoints.json",
                "rootUrl": conf.uri + "/cohorts",
                "singleEntryUrl": conf.uri + "/cohorts/{id}",
                # "filteringTermsUrl": conf.uri + "/api/cohorts/{id}/filtering_terms",
            },
            "individual": {
                "entryType": "individual",
                "openAPIEndpointsDefinition": "https://raw.githubusercontent.com/ga4gh-beacon/beacon-v2/main/models/json/beacon-v2-default-model/individuals/endpoints.json",
                "rootUrl": conf.uri + "/individuals",
                "singleEntryUrl": conf.uri + "/individuals/{id}",
                "filteringTermsUrl": conf.uri + "/individuals/filtering_terms",
                # "endpoints": {
                #     "biosample": {
                #         "returnedEntryType": "biosample",
                #         "url": conf.uri + "/individuals/{id}/biosamples"
                #     },
                # }
            },
        }
    }

    beacon_map_json = {
        'meta': meta,
        'response': response
    }

    return await json_stream(request, beacon_map_json)
