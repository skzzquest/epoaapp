# epoa-app: EPOA application tools

[![Build](https://img.shields.io/github/checks-status/smkent/epoa-app/main?label=build)][gh-actions]
[![codecov](https://codecov.io/gh/smkent/epoa-app/branch/main/graph/badge.svg)][codecov]
[![GitHub stars](https://img.shields.io/github/stars/smkent/epoa-app?style=social)][repo]

## Setup

* Make sure Google Chrome is installed and `google-chrome` can be invoked on the
  command line
* Install [poetry][poetry] with pipx (`pipx install poetry`) or
  pip (`pip install --user poetry`)
* Run `poetry install`
* Download copy of spreadsheet in Excel format
* Create a coniguration file at `~/.epoaapp.yaml`:

```yaml
# Your name (used for zip file naming)
name: "Darth Vader"

# Evidence directory
dir: path/to/evidence/directory

# Excel spreadsheet of roles to apply to
spreadsheet: path/to/epoa/spreadsheet.xlsx

# Tab in spreadsheet to use for roles
# Spreadsheet tab should have columns:
#   Company
#   Role Posting URL
#   Role title
#   Role Location
#   WA jurisdiction if remote
#   Date Applied
#   Date Provided to Legal
#   Notes/evidence
spreadsheet_tab: "Applications (Vader)"

# Resume used when applying for roles
# A copy will be saved in each role's evidence directory
resume: path/to/Darth-Vader-resume.pdf

# (optional) Compensation word search override (below values are the default)
#
# This is a case-insensitive list of words searched in the saved job posting PDF
# as a sanity check
words:
- compensation
- salary
- usd
- $
```

## Workflow overview

* List roles and company info in `epoa.xlsx`.
  * Each role requires a company, role title, and role URL.
  * Leave date applied blank.

* Run `poetry run epoaapp apply`.

For each role:

* Review automatically saved job posting PDF to ensure no compensation range is
  present
* Open role URL in browser, confirm no compensation range is present
* For each page of application form, complete the page and print to PDF in your
  browser
  * Enable headers/footers and background colors/images when saving to PDF to
    create accurate, timestamped evidence
* Print application confirmation page to PDF in browser
* Print any confirmation email to PDF in mail client
* Verify all needed evidence is present:
  * Job posting (PDF)
  * All filled pages of application form (PDFs)
  * Application confirmation (PDF)
  * Submitted resume (PDF)
  * Application confirmation email (PDF) (if available)
* Enter current date in spreadsheet **Date Applied** column

Evidence submission:

* Run `poetry run epoaapp zip -d <batch_start_date>` to create evidence zip file
  * Use the date after the previous sent zip file as `batch_start_date`
* Back up copy of zip file to additional storage location
* If zip file within email size limit, email zip file to legal
* If zip file over email size limit:
  * Upload to and share via NextCloud with password
  * Provide URL and password to legal

## Development

### [Poetry][poetry] installation

Via [`pipx`][pipx]:

```console
pip install pipx
pipx install poetry
pipx inject poetry poetry-dynamic-versioning poetry-pre-commit-plugin
```

Via `pip`:

```console
pip install poetry
poetry self add poetry-dynamic-versioning poetry-pre-commit-plugin
```

### Development tasks

* Setup: `poetry install`
* Run static checks: `poetry run poe lint` or
  `poetry run pre-commit run --all-files`
* Run static checks and tests: `poetry run poe test`

---

Created from [smkent/cookie-python][cookie-python] using
[cookiecutter][cookiecutter]

[codecov]: https://codecov.io/gh/smkent/epoa-app
[cookie-python]: https://github.com/smkent/cookie-python
[cookiecutter]: https://github.com/cookiecutter/cookiecutter
[gh-actions]: https://github.com/smkent/epoa-app/actions?query=branch%3Amain
[pipx]: https://pypa.github.io/pipx/
[poetry]: https://python-poetry.org/docs/#installation
[repo]: https://github.com/smkent/epoa-app
