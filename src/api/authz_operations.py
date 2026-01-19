import connexion
import os
import re
import urllib.parse
from datetime import datetime
import auth
import authx.auth
import tempfile
import json
from candigv2_logging.logging import CanDIGLogger


logger = CanDIGLogger(__file__)


app = connexion.AsyncApp(__name__)


# API endpoints
def get_service_info():
    return {
        "id": "org.candig.api.authz",
        "name": "CanDIG Authorization",
        "description": "Authorization endpoints for CanDIGv3",
        "organization": {
            "name": "CanDIG",
            "url": "https://www.distributedgenomics.ca"
        }
    }


####
# S3 credentials
####

async def add_s3_credential():
    data = await connexion.request.json()
    if not auth.is_action_allowed():
        return {"error": "Not authorized to store aws credentials"}, 403

    # test endpoint before storing:
    response, status_code = authx.auth.get_s3_url(object_id="None", s3_endpoint=data["endpoint"], bucket=data["bucket"], access_key=data["access_key"], secret_key=data["secret_key"])
    # we won't actually get an s3 url because we have no object:
    # we should expect the error to be a KeyError on the object_id of None.
    if status_code == 500 and "object_name: None" in response["error"]:
        response, status_code = authx.auth.store_aws_credential(endpoint=data["endpoint"], bucket=data["bucket"], access=data["access_key"], secret=data["secret_key"])
        return response, status_code
    return response, 400


@app.route('/s3-credential/endpoint/<path:endpoint_id>/bucket/<path:bucket_id>')
def get_s3_credential(endpoint_id, bucket_id):
    if not auth.is_action_allowed():
        return {"error": "Not authorized to view aws credentials"}, 403
    endpoint_cleaned = re.sub(r"\W", "_", endpoint_id)
    return authx.auth.get_aws_credential(endpoint=endpoint_cleaned, bucket=bucket_id)


@app.route('/s3-credential/endpoint/<path:endpoint_id>/bucket/<path:bucket_id>')
def delete_s3_credential(endpoint_id, bucket_id):
    if not auth.is_action_allowed():
        return {"error": "Not authorized to remove aws credentials"}, 403
    endpoint_cleaned = re.sub(r"\W", "_", endpoint_id)
    return authx.auth.remove_aws_credential(endpoint=endpoint_cleaned, bucket=bucket_id)


####
# Site roles
####

@app.route('/site-role/<path:role_type>')
def list_role(role_type):
    try:
        if not auth.is_action_allowed():
            return {"error": f"User not authorized to list site roles"}, 403

        result, status_code = auth.get_role_type(role_type)
        return result, status_code
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/site-role/<path:role_type>/user_id/<path:user_id>')
def is_user_in_role(role_type, user_id):
    try:
        if not auth.is_action_allowed():
            return {"error": f"User not authorized to list site roles"}, 403

        result, status_code = auth.get_role_type(role_type)
        if status_code == 200:
            return (user_id in result[role_type]), 200
        return result, status_code
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/site-role/<path:role_type>/user_id/<path:user_id>')
def add_user_to_role(role_type, user_id):
    try:
        if not auth.is_action_allowed():
            return {"error": f"User not authorized to add to site roles"}, 403

        result, status_code = auth.get_role_type(role_type)
        if status_code == 200:
            if user_id not in result[role_type]:
                result[role_type].append(user_id)
                result, status_code = auth.set_role_type(role_type, result[role_type])
        return result, status_code
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/site-role/<path:role_type>/user_id/<path:user_id>')
def remove_user_from_role(role_type, user_id):
    try:
        if not auth.is_action_allowed():
            return {"error": f"User not authorized to remove users from site roles"}, 403

        result, status_code = auth.get_role_type(role_type)
        if status_code == 200:
            if user_id in result[role_type]:
                if role_type == "admin" and len(result[role_type]) == 1:
                    return {"error": "You cannot remove the only site administrator. Add a new site admin before removing this user from the role."}
                result[role_type].remove(user_id)
                result, status_code = auth.set_role_type(role_type, result[role_type])
            else:
                return {"error": f"User {user_id} not found in role {role_type}"}, 404
        return result, status_code
    except Exception as e:
        return {"error": str(e)}, 500


####
# Dataset authorizations
####

def list_datasets():
    if not auth.is_action_allowed():
        return {"error": f"User not authorized to list datasets"}, 403

    response, status_code = auth.list_datasets()
    return response, status_code


async def add_dataset():
    dataset = await connexion.request.json()
    if not auth.is_action_allowed(dataset=dataset['dataset_id']):
        return {"error": f"User not authorized to add dataset {dataset['dataset_id']}"}, 403

    response, status_code = auth.add_dataset(dataset)
    if status_code == 200:
        response = response[dataset["dataset_id"]]
    check_default_site_admin(response)
    return response, status_code


@app.route('/dataset/<path:dataset_id>')
def get_dataset(dataset_id):
    if not auth.is_action_allowed(dataset=dataset_id):
        return {"error": f"User not authorized to get dataset {dataset_id}"}, 403

    response, status_code = auth.get_dataset(dataset_id)
    if status_code == 200:
        if "dac_authorizations" in response:
            response.pop("dac_authorizations")

    return response, status_code


@app.route('/dataset/<path:dataset_id>/dac_authorization')
def get_dataset_dacs(dataset_id):
    if not auth.is_action_allowed(dataset=dataset_id):
        return {"error": f"User not authorized to get dataset {dataset_id}"}, 403

    response, status_code = auth.get_dataset(dataset_id)
    dac_authz = {}

    if status_code == 200:
        if "dac_authorizations" in response:
            dac_authz = response.pop("dac_authorizations")

    return dac_authz, status_code


@app.route('/dataset/<path:dataset_id>')
def remove_dataset(dataset_id):
    if not auth.is_action_allowed(dataset=dataset_id):
        return {"error": "User not authorized to remove datasets"}, 403

    response = {"errors": {}}
    check_default_site_admin(response)

    opa_response, opa_status = auth.remove_dataset(dataset_id)
    logger.info(opa_response)
    if opa_status == 404:
        # htsget status is not included here because it doesn't have a 404 response
        return {"message": f"Dataset {dataset_id} not found"}, 404

    if opa_status != 200:
        response["errors"]["opa"] = {"message": opa_response, "status_code": opa_status}

    if len(response["errors"]) == 0:
        response.pop("errors")
        response["message"] = f"Dataset {dataset_id} successfully deleted"
        return response, 200

    return response, 500


####
# Pending users: approving a pending user creates a CanDIG-authorized user
####

def add_pending_user():
    token = connexion.request.headers['Authorization'].split("Bearer ")[1]

    response, status_code = auth.add_pending_user(token)
    return response, status_code


def list_pending_users():
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to list pending users"}, 403

    response, status_code = auth.list_pending_users()
    return {"results": response}, status_code


@app.route('/user/pending/<path:user_id>')
def is_user_pending(user_id):
    if not auth.is_action_allowed():
        return {"error": "User not authorized to list datasets for user"}, 403

    if user_id == "me":
        user_id = authx.auth.get_user_id(connexion.request)

    user_name = urllib.parse.unquote_plus(user_id)

    pending_users, status_code = auth.list_pending_users()
    if status_code == 200:
        return user_name in pending_users
    return False, 404


@app.route('/user/pending/<path:user_id>')
def approve_pending_user(user_id):
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to approve pending users"}, 403

    user_name = urllib.parse.unquote_plus(user_id)

    response, status_code = auth.approve_pending_user(user_name)
    return response, status_code


@app.route('/user/pending/<path:user_id>')
def reject_pending_user(user_id):
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to reject pending users"}, 403

    user_name = urllib.parse.unquote_plus(user_id)

    response, status_code = auth.reject_pending_user(user_name)
    return response, status_code


async def approve_pending_users():
    users = await connexion.request.json()
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to approve pending users"}, 403

    rejected = []
    approved = []
    for user_id in users:
        response, status_code = auth.approve_pending_user(user_id)
        if status_code != 200:
            rejected.append(user_id)
        else:
            approved.append(user_id)
    response = {}
    if len(approved) > 0:
        response["approved"] = approved
    if len(rejected) > 0:
        status_code = 401
        response["rejected"] = rejected
    return response, status_code


def clear_pending_users():
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to clear pending users"}, 403

    response, status_code = auth.clear_pending_users()
    return response, status_code


####
# Preapproved users: If a preapproved user requests to be pending, the user will automatically be approved as a CanDIG-authorized user
####

def list_preapproved_users():
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to list preapproved users"}, 403

    response, status_code = auth.list_preapproved_users()
    return {"results": response}, status_code


async def add_preapproved_users():
    users = await connexion.request.json()
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to add preapproved users"}, 403

    rejected = []
    for user_id in users:
        response, status_code = auth.add_preapproved_user(user_id)
        if status_code not in [200, 201]:
            rejected.append(user_id)
    if len(rejected) > 0:
        status_code = 401
        response = {"message": f"The following requested user IDs could not be added: {rejected}"}
    else:
        response = {"message": "Success"}
    return response, status_code


def clear_preapproved_users():
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to clear preapproved users"}, 403

    response, status_code = auth.clear_preapproved_users()
    return response, status_code


@app.route('/user/preapproved/<path:user_id>')
def get_preapproved_user(user_id):
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to get preapproved users"}, 403

    user_name = urllib.parse.unquote_plus(user_id)

    response, status_code = auth.get_preapproved_user(user_name)
    return response, status_code


@app.route('/user/preapproved/<path:user_id>')
def add_preapproved_user(user_id):
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to add preapproved users"}, 403

    user_name = urllib.parse.unquote_plus(user_id)

    response, status_code = auth.add_preapproved_user(user_name)
    return response, status_code


@app.route('/user/preapproved/<path:user_id>')
def remove_preapproved_user(user_id):
    if not authx.auth.is_site_admin(connexion.request):
        return {"error": f"User not authorized to remove preapproved users"}, 403

    user_name = urllib.parse.unquote_plus(user_id)

    response, status_code = auth.remove_preapproved_user(user_name)
    return response, status_code


####
# DAC authorization for users
####

@app.route('/user/<path:user_id>')
def list_authz_for_user(user_id):
    token = connexion.request.headers['Authorization'].split("Bearer ")[1]

    status_code = 0
    if not auth.is_action_allowed():
        return {"error": "User not authorized to list datasets for user"}, 403

    self_checkup = user_id == "me"
    if user_id == "me":
        user_id = authx.auth.get_user_id(connexion.request)

    user_result, status_code = auth.get_user(user_id)
    if status_code != 200:
        return user_result, status_code

    user_result["site_roles"] = []
    role_types, status_code = auth.list_role_types()
    if status_code == 200:
        for role_type in role_types:
            users, status_code = auth.get_role_type(role_type)
            if user_id in users[role_type]:
                user_result["site_roles"].append(role_type)

    user_result["dataset_authorizations"] = {}

    user_token = None
    user_key = None
    if self_checkup:
        user_token = token
    elif "sample_jwt" in user_result["userinfo"]:
        user_token = user_result["userinfo"].pop("sample_jwt")
    else:
        user_key = user_id
    opa_permissions, opa_status_code = authx.auth.get_opa_permissions(
        bearer_token=token,
        user_token=user_token,
        user_key=user_key
    )
    if opa_status_code == 200:
        user_result["dataset_authorizations"]["team_member"] = opa_permissions["debug"]["user_key_has_team_member_programs"]
        user_result["dataset_authorizations"]["dataset_curator"] = opa_permissions["debug"]["user_key_has_curator_programs"]

    user_result["dataset_authorizations"]["dac_authorizations"] = list(user_result.pop("dac_authorizations").values())
    user_result["userinfo"]["is_candig_authorized"] = opa_permissions["user_is_candig_authorized"]
    return user_result, status_code


@app.route('/user/<path:user_id>')
def revoke_authz_for_user(user_id):
    if not auth.is_action_allowed():
        return {"error": "User not authorized to revoke authorization for users"}, 403

    response, status_code = auth.remove_user(user_id)
    return response, status_code


@app.route('/user/<path:user_id>/dac_authorization')
async def add_dac_authz_for_user(user_id):
    dataset_body = await connexion.request.json()

    if "dict" in str(type(dataset_body)):
        # if the body was a dict, make it an array
        dataset_body = [dataset_body]

    user_dict, status_code = auth.get_user(user_id)
    if status_code != 200:
        user_dict = {
            "userinfo": {
                "user_name": user_id
            },
            "dac_authorizations": {}
        }

    all_datasets, status_code = auth.list_datasets()
    if status_code != 200:
        return all_datasets, status_code

    errors = []

    # check to see if any of the datasets are listed more than once
    datasets = list(map(lambda x: x['dataset_id'], dataset_body))
    if len(datasets) > len(set((datasets))):
        return {"error": "Duplicate datasets in request"}, 400

    for dataset_dict in dataset_body:
        dataset_id = dataset_dict["dataset_id"]
        if not auth.is_action_allowed(dataset=dataset_id):
            errors.append({dataset_id: "User not authorized to authorize datasets for user"})

        # we need to check to see if the dataset even exists in the system
        if dataset_id not in all_datasets:
            errors.append({dataset_id: f"Dataset {dataset_id} does not exist in {all_datasets}"})

        try:
            if datetime.fromisoformat(dataset_dict['end_date']) < datetime.fromisoformat(dataset_dict['start_date']):
                errors.append({dataset_id: f"Start date {dataset_dict['start_date']} cannot be later than end date {dataset_dict['end_date']}"})
            elif datetime.fromisoformat(dataset_dict['end_date']) == datetime.fromisoformat(dataset_dict['start_date']):
                errors.append({dataset_id: f"Start date {dataset_dict['start_date']} is the same as end date {dataset_dict['end_date']}"})
            elif datetime.fromisoformat(dataset_dict['end_date']) < datetime.now():
                errors.append({dataset_id: f"Start date {dataset_dict['start_date']} and end date {dataset_dict['end_date']} are in the past"})
        except Exception as e:
            errors.append({dataset_id: f"Date format error: {type(e)} {str(e)}"})
        user_dict["dac_authorizations"][dataset_id] = dataset_dict

        # add this dac to the dataset's authz
        dataset, status_code = auth.get_dataset(dataset_id)
        if status_code == 200:
            if "dac_authorizations" not in dataset:
                dataset["dac_authorizations"] = {}
            dataset["dac_authorizations"][user_id] = dataset_dict
            response, status_code = auth.add_dataset(dataset)
            logger.debug(response, status_code)
            if status_code != 200:
                errors.append({dataset_id: response})

    if len(errors) == 0:
        user_dict, status_code = auth.write_user(user_dict)
        if "sample_jwt" in user_dict["userinfo"]:
            user_dict["userinfo"].pop("sample_jwt")
        return user_dict, status_code
    return errors, 400


@app.route('/user/<path:user_id>/dac_authorization/<path:dataset_id>')
def get_dac_authz_for_user(user_id, dataset_id):
    if not auth.is_action_allowed():
        return {"error": "User not authorized to get datasets for user"}, 403

    user_dict, status_code = auth.get_user(user_id)
    if status_code != 200:
        return user_dict, status_code
    if "sample_jwt" in user_dict["userinfo"]:
        user_dict["userinfo"].pop("sample_jwt")
    for p in user_dict["dac_authorizations"]:
        if p == dataset_id:
            return p, 200
    return {"error": f"No dataset {dataset_id} found for user"}, status_code


@app.route('/user/<path:user_id>/authorize/<path:dataset_id>')
def remove_dac_authz_for_user(user_id, dataset_id):
    if not auth.is_action_allowed(dataset=dataset_id):
        return {"error": "User not authorized to remove datasets for user"}, 403

    user_dict, status_code = auth.get_user(user_id)
    if status_code != 200:
        return user_dict, status_code
    for p in user_dict["dac_authorizations"]:
        if p == dataset_id:
            user_dict["dac_authorizations"].pop(dataset_id)
            user_dict, status_code = auth.write_user(user_dict)
            if "sample_jwt" in user_dict["userinfo"]:
                user_dict["userinfo"].pop("sample_jwt")
            return user_dict, status_code
    return {"error": f"No dataset {dataset_id} found for user"}, status_code


@app.route('/get-token')
def get_token():
    # Attempt to grab the token via session_id
    if not hasattr(connexion.request, 'cookies'):
        return {'error': 'Unable to use the get-token endpoint without cookies'}, 200
    token = connexion.request.cookies['session_id']

    return {"token": token}, 200

    # Uncomment the below to exchange for a new token and return
    # that, instead
    # try:
    #    response = auth.get_refresh_token(token)
    #    if "error" in response:
    #        return {"error": response["error"]}, 500
    #    return {"token": response["refresh_token"]}, 200
    #except Exception as e:
    #    return {"error": str(e)}, 500


def check_default_site_admin(response):
    if auth.is_default_site_admin_set():
        if "warnings" not in response:
            response["warnings"] = []
        response["warnings"].append(f"Default site administrator {os.getenv('DEFAULT_SITE_ADMIN_USER')} is still configured. Use the /v1/authz/site-role/site_admin endpoint to set a different site admin.")
