# CanDIG API

_Currently a work in progress. Not yet part of any CanDIG stable release._ 

This repo implements a top-level API that provides access to all CanDIG data services, including clinical data in [OMOP](https://www.ohdsi.org/data-standardization/) and blob data in an object store. 

Implemeted using connextion and SQLAlchemy. 

## API schemas

There are three OpenAPI schemas, both under development:

* [schema.yml](schema.yml) - implements basic CRUD operations on clinical data objects (Datasets and Persons)
* [beacon-schema.yml](beacon-schema.yml) - implements a [GA4GH Beacon v2](https://www.ga4gh.org/product/beacon-api/) API for data discovery currently supporting clinical data querying and eventually will include genomic querying. 
* [authz-schema.yml](authz-schema.yml) - implements authorization related endpoints such as user management and dataset authorizations

## Under construction

Following sections to be updated when we are ready to integrate into a full CanDIG stack. 

## Acknowledgements

* A large proportion of the Beacon work was adapted from Barcelona Supercomputing Centre (BSC)'s implementation at https://gitlab.bsc.es/impact-data/impd-beacon_omopcdm

