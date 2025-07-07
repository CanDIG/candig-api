# CanDIG API

_Currently a work in progress. Not yet part of any CanDIG stable release._ 

This repo will hold a top-level API that provides access to all CanDIG data services, including clinical data in [OMOP](https://www.ohdsi.org/data-standardization/) and blob data in an object store. 

Will implement a [GA4GH Beacon v2](https://www.ga4gh.org/product/beacon-api/) API for data discovery. 

## Branch structure

The default branch is `develop` and the `stable` branch indicates a stable production release.

All development should be done on a fork or branch from the develop branch. Releases of new code to the 'stable' branch occur on an adhoc basis.

## Microservice specific files

_Microservice setup not started_

If you are setting up a new microservice that will be a part of the CanDIGv2 stack, you will most likely need to edit the files below, otherwise they can be deleted from the repo.

### Dockerfile

- Edit the Dockerfile with the correct names and paths that are relevant to your microservice.

- Add or remove the installed packages as needed

- Choose between using alpine or debian as the base operating system - we have found alpine can be slow for some applications

### uWSGI config file

If your service will be communicating with other services in the network using the web server gateway interface, you will need to edit the configuration file.

#### `uwsgi.ini`

This sets the configuration for uwsgi. You will need to add the name of the app and the port number as a minimum. The processes and [harakiri](https://uwsgi-docs.readthedocs.io/en/latest/Glossary.html) values can also be updated based on your needs.

### Github Actions

Templates for two Github actions ymls are in the [`.github/workflows/`](.github/workflows) directory and should be edited to suit the needs of the microservice. 

#### `dispatch-actions.yml`

This action automatically makes a PR to the main [CanDIGv2 repo stack](https://github.com/CanDIG/CanDIGv2) to update the submodule each time a PR is merged into develop.

Edit this file with the appropriate submodule path on line 26.

#### `test.yml`

This action assumes you have setup tests in the repo using [pytest](https://docs.pytest.org/en/7.4.x/). 

It automatically runs `pytest` on the repo each time a commit is pushed into the remote repo. 

