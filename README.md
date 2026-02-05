# CanDIG API

_Currently a work in progress. Not yet part of any CanDIG stable release._ 

This repo implements a top-level API that provides access to all CanDIG data services, including clinical data in [OMOP](https://www.ohdsi.org/data-standardization/) and blob data in an object store. 

Implemeted using connextion and SQLAlchemy.

## API schemas

There are two OpenAPI schemas, both under development:

* [schema.yml](schema.yml) implements basic CRUD operations on clinical data objects (Datasets and Persons)
* [beacon-schema.yml](beacon-schema.yml) will implement a [GA4GH Beacon v2](https://www.ga4gh.org/product/beacon-api/) API for data discovery across datatypes (clinical, genomic). 

## Branch structure

The default branch is `develop` and the `stable` branch indicates a stable production release.

All development should be done on a fork or branch from the develop branch. Releases of new code to the 'stable' branch occur on an adhoc basis.

## Under constructions

Following sections to be updated when we are ready to integrate into a full CanDIG stack. 

### Github Actions

Templates for two Github actions ymls are in the [`.github/workflows/`](.github/workflows) directory and should be edited to suit the needs of the microservice. 

#### `dispatch-actions.yml`

This action automatically makes a PR to the main [CanDIGv2 repo stack](https://github.com/CanDIG/CanDIGv2) to update the submodule each time a PR is merged into develop.

Edit this file with the appropriate submodule path on line 26.

#### `test.yml`

This action assumes you have setup tests in the repo using [pytest](https://docs.pytest.org/en/stable/). 

It automatically runs `pytest` on the repo each time a commit is pushed into the remote repo. 

## Acknowledgements

* A large proportion of the Beacon work was adapted from Barcelona Supercomputing Centre (BSC)'s implementation at https://gitlab.bsc.es/impact-data/impd-beacon_omopcdm

