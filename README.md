# CanDIG Repository Template
An example for what should be in any CanDIG repository.  In progress. Not at all ready for use. 

## Branch structure

All CanDIG repositories follow a branch pattern where the default branch is `develop` and the `stable` branch indicates a stable production release.

Generally all active development is done on a fork or branch from the develop branch. Releases of new code to the 'stable' branch occur on an adhoc basis.

## Files to edit:

### README-template.md 

1. Adjust all the references to 'Project Name' with the name of your repo/project
1. Choose which badges you would like to display and edit the URLs so that they pick up the right status
1. Use the headings as a guide and tailor the information to your code base
1. Add additional sections as needed
1. When complete, delete the existing README.md in this directory and change the name of the README-template.md to README.md

### `.gitignore`

A template `.gitignore` file is included with common file types one wouldn't want to commit to a git repository. 

Please edit with any other specific files or folders that may appear in your project that should not be pushed to GitHub.

An extensive list of `.gitignore` templates can be found in this repo: [github/gitignore](https://github.com/github/gitignore)

### Pull Request template

The default PR template used for this repo is [pull_request_template.md](.github/pull_request_template.md). 

This template contains recommended fields for standard PRs to the develop branch of the repo. It can be tailored with any specific sections that may be useful for your project.

Releases, or PRs to the stable branch should use the [stable_pr_template.md](.github/PULL_REQUEST_TEMPLATE/stable_pr_template.md) and the process on Confluence.  

## Microservice specific files:

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


## Acknowledgements

Thanks to [@scottydocs/README-template.md](https://github.com/scottydocs/README-template.md/tree/master) for providing a great `README` template that we adapted for our purposes.
