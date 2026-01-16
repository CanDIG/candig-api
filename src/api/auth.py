import authx.auth
import os
import re
import json
import urllib
from connexion import request

def is_default_site_admin_set():
    default_site_admin = os.getenv("DEFAULT_SITE_ADMIN_USER", "")
    if default_site_admin != "":
        result, status_code = authx.auth.get_service_store_secret("opa", key=f"site_roles")
        if status_code == 200:
            if 'admin' in result['site_roles']:
                return default_site_admin in ",".join(result['site_roles']['admin'])
        raise Exception(f"ERROR: Unable to list site administrators {result} {status_code}")
    return False


def get_refresh_token(token):
    client_secret = authx.auth.get_service_store_secret(service="keycloak", key="client-secret")
    return authx.auth.get_oauth_response(
        client_secret = client_secret,
        refresh_token=token
        )


def is_action_allowed(dataset=None):
    path = request.url.path
    method = request.method
    token = authx.auth.get_auth_token(request)
    return authx.auth.is_action_allowed_for_program(token, method=method, path=path, program=dataset)


def get_authorized_datasets():
    return authx.auth.get_opa_datasets(request)


######
# Datasets
######

def get_dataset(dataset_id):
    """
    Returns a DatasetAuthorization for the dataset_id
    Authorized only if the service requesting it is allowed to see Opa's vault secrets.
    """
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"programs/{dataset_id}")
    if status_code < 300:
        return response[dataset_id], status_code
    return {"message": f"{dataset_id} not found"}, status_code


def list_datasets():
    progs_response, status_code = authx.auth.get_service_store_secret("opa", key="programs")
    if status_code == 200:
        return progs_response['programs'], status_code
    return progs_response, status_code


def add_dataset(dataset_auth):
    """
    Creates or updates a DatasetAuthorization in Opa's vault service store for the dataset_id.
    Authorized only if the requesting service is allowed to write Opa's vault secrets.
    """
    dataset_id = dataset_auth["dataset_id"]
    response, status_code = get_dataset(dataset_id)
    if status_code < 300 or status_code == 404:
        # create or update the dataset itself
        dataset_auth["program_curators"] = list(map(lambda x: x.lower(), dataset_auth["dataset_curators"]))
        dataset_auth["team_members"] = list(map(lambda x: x.lower(), dataset_auth["team_members"]))

        # add the users to the preapproved user list
        for user_id in dataset_auth["team_members"]:
            # if the user isn't already approved, make sure they will be:
            response, status_code = add_preapproved_user(user_id)
        for user_id in dataset_auth["program_curators"]:
            # if the user isn't already approved, make sure they will be:
            response, status_code = add_preapproved_user(user_id)

        if "date_created" not in dataset_auth:
            from datetime import datetime
            dataset_auth["date_created"] = datetime.today().strftime('%Y-%m-%d')
        response, status_code = authx.auth.set_service_store_secret("opa", key=f"programs/{dataset_id}", value=json.dumps({dataset_id: dataset_auth}))
        if status_code < 300:
            # update the values for the dataset list
            response2, status_code = authx.auth.get_service_store_secret("opa", key="programs")

            if status_code == 200:
                # check to see if it's already here:
                if dataset_id not in response2['programs']:
                    response2['programs'].append(dataset_id)
            else:
                response2 = {'programs': [dataset_id]}
            response2, status_code = authx.auth.set_service_store_secret("opa", key="programs", value=json.dumps(response2))
            return response, status_code

    return {"message": f"{dataset_id} not added: {response}"}, status_code


def remove_dataset(dataset_id):
    """
    Removes the DatasetAuthorization in Opa's vault service store for the dataset_id.
    Authorized only if the requesting service is allowed to write Opa's vault service store.
    """
    response, status_code = get_dataset(dataset_id)
    if status_code == 404:
        return response, status_code
    if status_code < 300:
        # create or update the dataset itself
        response, status_code = authx.auth.delete_service_store_secret("opa", key=f"programs/{dataset_id}")

        # update the values for the dataset list
        response, status_code = authx.auth.get_service_store_secret("opa", key="programs")

        if status_code == 200:
            # check to see if it's here:
            if dataset_id in response['programs']:
                response['programs'].remove(dataset_id)
                response, status_code = authx.auth.set_service_store_secret("opa", key="programs", value=json.dumps(response))

        return {"success": f"{dataset_id} removed"}, status_code
    return {"message": f"{dataset_id} not removed"}, status_code


#####
# Site roles
#####

def list_role_types():
    result, status_code = authx.auth.get_service_store_secret("opa", key=f"site_roles")
    if status_code == 200:
        return list(result['site_roles'].keys()), 200
    return result, status_code


def get_role_type(role_type):
    result, status_code = authx.auth.get_service_store_secret("opa", key=f"site_roles")
    if status_code == 200:
        if role_type in list(result['site_roles'].keys()):
            return {role_type: result['site_roles'][role_type]}, 200
        return {"error": f"role type {role_type} does not exist"}, 404
    return result, status_code


def set_role_type(role_type, members):
    result, status_code = authx.auth.get_service_store_secret("opa", key=f"site_roles")
    if status_code == 200:
        if role_type in result['site_roles']:
            members = list(map(lambda x: x.lower(), members))
            for user_id in members:
                # if the user isn't already approved, make sure they will be:
                response, status_code = add_preapproved_user(user_id)

            result['site_roles'][role_type] = members
            result, status_code = authx.auth.set_service_store_secret("opa", key=f"site_roles", value=json.dumps(result))
            if status_code == 200:
                return result['site_roles'][role_type], status_code
        return {"error": f"role type {role_type} does not exist"}, 404
    return result, status_code


#####
# DAC authorization for users
#####

def write_user(user_dict):
    safe_name = urllib.parse.quote_plus(user_dict['userinfo']['user_name'])
    response, status_code = authx.auth.set_service_store_secret("opa", key=f"users/{safe_name}", value=json.dumps(user_dict))
    return response, status_code


def get_user(user_name):
    safe_name = urllib.parse.quote_plus(user_name)
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"users/{safe_name}")
    # return 404 if the user is not found
    if status_code == 404:
        response = {"error": f"User {user_name} is not an authorized CanDIG user"}
    return response, status_code


def get_self(token):
    user_name = authx.auth.get_user_id(None, token=token)
    if user_name is None:
        return {"error": "User token is not valid"}, 404
    response, status_code = get_user(user_name)
    return response, status_code


def remove_user(user_name):
    safe_name = urllib.parse.quote_plus(user_name)
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"users/{safe_name}")
    if status_code == 200:
        response, status_code = authx.auth.delete_service_store_secret("opa", key=f"users/{safe_name}")
        # if the user was preapproved, take them out of that list
        remove_preapproved_user(user_name)

        # remove the user from any site roles:
        site_roles, status_code = list_role_types()
        for role_type in site_roles:
            members, status_code = get_role_type(role_type)
            if user_name in members:
                members.remove(user_name)
                set_role_type(role_type, members)

        # remove the user from any dataset roles:
        datasets, status_code = list_datasets()
        for dataset_id in datasets:
            dataset, status_code = get_dataset(dataset_id)
            if user_name in dataset["dataset_curators"]:
                dataset["dataset_curators"].remove(user_name)
            if user_name in dataset["team_members"]:
                dataset["team_members"].remove(user_name)
            add_dataset(dataset)
        return {"message": f"User {user_name} was removed"}, 200
    return {"error": f"User {user_name} could not be removed"}, status_code


#####
# Pending user authorizations
#####

def add_pending_user(token):
    # NB: any user that has been authenticated by the IDP should be able to add themselves to the pending user list
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"pending_users")
    if status_code != 200:
        return response, status_code

    user_name = authx.auth.get_user_id(None, token=token)
    if user_name is None:
        return {"error": "Could not verify jwt or obtain user ID"}, 403

    user_dict, status_code = get_user(user_name)
    if status_code != 404:
        if "sample_jwt" not in user_dict["userinfo"]:
            user_dict["userinfo"]["sample_jwt"] = token
        else:
            return {"message": f"User {user_name} is already a CanDIG authorized user"}, 200
    else:
        user_dict = {
            "userinfo": {
                "user_name": user_name,
                "sample_jwt": token
            }
        }
    if user_name not in response["pending_users"]:
        response["pending_users"][user_name] = user_dict

        response, status_code = authx.auth.set_service_store_secret("opa", key=f"pending_users", value=json.dumps(response))

        if status_code == 200:
            preapproved_users, status_code = list_preapproved_users()
            if status_code == 200:
                if user_name in preapproved_users:
                    return approve_pending_user(user_name)
            return response, 201 # return 201 to indicate that the user was added to the list
    else:
        # return 200 to indicate OK but nothing was added
        return {"message": f"User {user_name} already pending"}, 200
    return response, status_code


def list_pending_users():
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"pending_users")
    if status_code == 200:
        response = list(response["pending_users"].keys())
    return response, status_code


def is_user_pending(token):
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"pending_users")
    if status_code == 200:
        user_name = authx.auth.get_user_id(None, token=token)
        response = user_name in response["pending_users"]
    else:
        response = False
    return response, status_code


def approve_pending_user(user_name):
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"pending_users")
    if status_code != 200:
        return response, status_code
    pending_users = response["pending_users"]
    if user_name in pending_users:
        user_dict = pending_users[user_name]
        if "dac_authorizations" not in user_dict:
            user_dict["dac_authorizations"] = {}
        response2, status_code = write_user(user_dict)
        if status_code == 200:
            pending_users.pop(user_name)
            response3, status_code = authx.auth.set_service_store_secret("opa", key=f"pending_users", value=json.dumps(response))
            return {"message": f"User {user_name} has been approved"}, status_code
        return response2, status_code
    else:
        return {"error": f"no pending user with ID {user_name}"}, 404


def reject_pending_user(user_name):
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"pending_users")
    if status_code != 200:
        return response, status_code
    pending_users = response["pending_users"]

    if user_name in pending_users:
        pending_users.pop(user_name)
        response, status_code = authx.auth.set_service_store_secret("opa", key=f"pending_users", value=json.dumps({"pending_users": pending_users}))

    else:
        return {"error": f"no pending user with ID {user_name}"}, 404
    return response, status_code


def clear_pending_users():
    response, status_code = authx.auth.set_service_store_secret("opa", key="pending_users", value=json.dumps({"pending_users": {}}))
    return response, status_code


#####
# Preapproved user authorizations
#####

def list_preapproved_users():
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"preapproved_users")
    if status_code == 200:
        response = response["preapproved_users"]
    return response, status_code


def clear_preapproved_users():
    response, status_code = authx.auth.set_service_store_secret("opa", key="preapproved_users", value=json.dumps({"preapproved_users": []}))
    return response, status_code


def get_preapproved_user(user_name):
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"preapproved_users")
    if status_code == 200:
        response = user_name in response["preapproved_users"]
    else:
        response = False
    return response, status_code


def add_preapproved_user(user_name):
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"preapproved_users")

    if user_name in response["preapproved_users"]:
        # return 200 to indicate OK but nothing was added
        return {"message": f"User {user_name} already preapproved"}, 200

    response["preapproved_users"].append(user_name)

    response, status_code = authx.auth.set_service_store_secret("opa", key=f"preapproved_users", value=json.dumps(response))
    if status_code == 200:
        return response, 201 # 201 created, to indicate that we added the user
    return response, status_code


def remove_preapproved_user(user_name):
    response, status_code = authx.auth.get_service_store_secret("opa", key=f"preapproved_users")
    if status_code != 200:
        return response, status_code
    preapproved_users = response["preapproved_users"]

    if user_name in preapproved_users:
        preapproved_users.remove(user_name)
        response, status_code = authx.auth.set_service_store_secret("opa", key=f"preapproved_users", value=json.dumps({"preapproved_users": preapproved_users}))

    else:
        return {"error": f"no preapproved user with ID {user_name}"}, 404
    return response, status_code
