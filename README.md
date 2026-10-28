# service-scheduler 
 A django app for creating and fine-tuning "fair" schedules using 
 * [PuLP](https://coin-or.github.io/pulp/) optimization 
 * Postgresql
 * pdfkit

## Install
```bash
pip install -r requirements.txt
```

## Tests

Use the project venv. Django creates and destroys a test database (`test_servicescheduler`).

```bash
source venv/bin/activate
python manage.py test
```

A subset:

```bash
python manage.py test schedules.services.tests
python manage.py test schedules.tests.DeleteScheduleViewTests
python manage.py test schedules.tests.DeleteScheduleViewTests.test_other_user_cannot_delete
```

CBC runs on the real LP tests in `schedules.services.tests` (a few seconds). Verbose: `python manage.py test -v2`.

## Compare objectives

Generate months with one or more fairness objectives and print a KPI table (fill ratio, MAD, starved people, song-job counts, new-person month 1). Uses a throwaway test database, not Sunday’s data. The table always prints.

Congregation-sized snapshot (anonymized names/emails in `schedules/fixtures/compare/live.sql`):

```bash
source venv/bin/activate
python manage.py compare_objectives FairJobs --dump
python manage.py compare_objectives CatchUpShare FairJobs --dump --months 6
```

Refresh that file from the local Sunday database (rewrites names, emails, and passwords):

```bash
python manage.py dump_compare_db
```

Tiny fake roster (`schedules/fixtures/compare/default.toml`) is faster and is what the year-compare test uses:

```bash
python manage.py compare_objectives
python manage.py compare_objectives FairJobs
python manage.py compare_objectives CatchUpShare FairJobs
python manage.py compare_objectives FairJobs --months 6
python manage.py compare_objectives FairJobs --world default
```

Copy that file to try another mix:

```bash
cp schedules/fixtures/compare/default.toml schedules/fixtures/compare/crowded.toml
# edit crowded.toml
python manage.py compare_objectives FairJobs --world crowded
```

`--dump` seeds the throwaway test database from `live.sql` and starts generating the month after the latest dumped assignment. Full-church CBC is slower than the tiny TOML world.

`--world` is a file stem in that folder, or a path to any `.toml`. Names can be the class (`FairJobsObjective`) or a unique substring (`FairJobs`). Default is both objectives, 12 months each.

What the fields mean: docstring at the top of `schedules/services/year_compare.py`. Constraint asserts (infeasible/unfilled/exclusions) still live in `python manage.py test schedules.services.test_year_compare`.

## Seed your data
add data to `core/fixtures`

_read scripts for now to understand data format for now_

```bash
./manage.py seed_data
```


## Models
![models](models.png?raw=true)
