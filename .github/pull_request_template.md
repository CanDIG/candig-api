<!--- This is a template for a standard PR against the default/develop branch of the repo, if you are making a stable release PR, replace "?expand=1" with "?template=stable_pr_template.md&title=v.X.X.X: [Release Description]" at the end of your URL in your browser above ^ --->

<!--- Please name your pull request with the Jira ticket reference (DIG-[0-9]*) it is fixing and a descriptive title --->

# Ticket(s)

- [DIG-](https://candig.atlassian.net/browse/DIG-)

# Description
<!--- Describe the change that was made and anything the reviewer should be aware of --->



# Related
<!--- List any related PRs or information here if any exist. --->

-

# To test
<!--- Describe what is needed to test the change --->


## Types of Change(s)

- [ ] 🪲 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to change)

If breaking, Which other services does it affect?

- [ ] authx
- [ ] data-portal
- [ ] ingest
- [ ] clinical ETL
- [ ] federation
- [ ] htsget-app
- [ ] katsu
- [ ] CanDIG OPA
- [ ] Query

<!--- If a breaking change, describe the impact the PR will have on the services selected above --->

## Has it been tested for:

- [ ] My change requires a change to the documentation
- [ ] I have updated the documentation accordingly
- [ ] Prettier linter doesn't return errors
- [ ] Locally tested
  - [ ] using stable release
  - [ ] using develop branches
- [ ] Dev server tested
- [ ] Production tested when merging into stable/production branch
