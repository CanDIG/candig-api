"""Beacon Configuration."""
from datetime import datetime

#
# Beacon general info
#
beacon_id = 'bsc.omop.impact.beacon-test'  # ID of the Beacon
beacon_name = 'BSC OMOP-CDM Beacon'  # Name of the Beacon service
api_version = 'v2.0.0'  # Version of the Beacon implementation
uri = 'http://localhost:5050/api'

#
# Beacon granularity
# possible values: "record", "count", "boolean"
#
default_beacon_granularity = "record"
max_beacon_granularity = "record"

#
#  Organization info
#
org_id = 'BSC'  # Id of the organization
org_name = 'Barcelona Supercomputing Center'  # Full name
org_description = ('INB/ELIXIR-ES group from the BSC')
org_adress = ('Plaça Eusebi Güell, 1-3. 08034 Barcelona,  Spain')
org_welcome_url = 'https://www.bsc.es/'
org_contact_url = 'mailto:salvador.capella@bsc.es'
org_logo_url = 'https://temu.bsc.es/assets/images/BSC-blue-small.png'
org_info = ''

#
# Project info
#
description = ('This Beacon is a development funded by IMPaCT-Data where the data is queried from a OMOP-CDM relational database on-the-fly')
version = 'v2.0'
welcome_url = ''
alternative_url = ''
create_datetime = '2023-06-21T12:00:00.000000'
update_datetime = datetime.now()
# update_datetime will be created when initializing the beacon, using the ISO 8601 format

#
# Service
#
service_type = 'org.ga4gh:beacon:1.0.0'  # service type
service_url = ''
entry_point = False
is_open = True
documentation_url = 'https://github.com/EGA-archive/beacon-2.x/'  # Documentation of the service
environment = 'test'  # Environment (production, development or testing/staging deployments)

# GA4GH
ga4gh_service_type_group = 'org.ga4gh'
ga4gh_service_type_artifact = 'beacon'
ga4gh_service_type_version = '1.0'

# Beacon handovers
beacon_handovers = [
    {
        'handoverType': {
            'id': 'NCIT:C176263',
            'label': 'Synthetic Data'
        },
        'url': 'https://www.ohdsi.org/data-standardization/'
    }
]

# Maximum Limit query
MAX_LIMIT = 50

#
# Database connection
#
database_host = '127.0.0.1'
database_port = 27017
database_user = 'root'
database_password = 'example'
database_name = 'beacon'
database_auth_source = 'admin'
# database_schema = 'public' # comma-separated list of schemas
# database_app_name = 'beacon-appname' # Useful to track connections

#
# Web server configuration
# Note: a Unix Socket path is used when behind a server, not host:port
#
beacon_host = '0.0.0.0'
beacon_port = 5050
beacon_tls_enabled = False
beacon_tls_client = False
beacon_cert = '/etc/ega/server.cert'
beacon_key = '/etc/ega/server.key'
CA_cert = '/etc/ega/CA.cert'

#
# Permissions server configuration
#
permissions_url = 'http://beacon-permissions'

#
# IdP endpoints (OpenID Connect/Oauth2)
#
# or use Elixir AAI (see https://elixir-europe.org/services/compute/aai)
#
idp_client_id = 'beacon'
idp_client_secret = 'b26ca0f9-1137-4bee-b453-ee51eefbe7ba'  # same as in the test IdP
idp_scope = 'profile openid'

idp_authorize = 'http://idp/auth/realms/Beacon/protocol/openid-connect/auth'
idp_access_token = 'http://idp/auth/realms/Beacon/protocol/openid-connect/token'
idp_introspection = 'http://idp/auth/realms/Beacon/protocol/openid-connect/token/introspect'
idp_user_info = 'http://idp/auth/realms/Beacon/protocol/openid-connect/userinfo'
idp_logout = 'http://idp/auth/realms/Beacon/protocol/openid-connect/logout'

idp_redirect_uri = 'http://beacon:5050/login'

#
# UI
#
autocomplete_limit = 16
autocomplete_ellipsis = '...'

#
# Ontologies
#
ontologies_folder = "deploy/ontologies/"
