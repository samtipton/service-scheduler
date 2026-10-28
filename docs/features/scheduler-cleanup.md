# Scheduler cleanup

Do this before changing the objective. Goal: one place to swap fairness math, history as Assignment counts, tests that actually solve a month.

## Split `Scheduler`

Today `__init__` loads data, builds variables, sets the objective, and adds constraints. Break into:

- Load: users, tasks, prefs, date-tasks, history **counts** from `Assignment` (not `AssignmentStats`)
- Variables: eligible `(date_task, user)` binaries
- Constraints: keep current rules as named methods; `Scheduler(..., constraint_names=...)` so [objective-experiment-ui.md](objective-experiment-ui.md) can run with/without a rule
- Objective: a function that returns a PuLP expression (see pluggable-objective.md)
- Solve / extract

Leave UI, PDF, and seed commands alone.

## History

At solve time: `count(user, task)` over a window (default all-time). Drop the solver’s dependency on `AssignmentStats`. Keep the table for now so production still runs; stop *requiring* it.

## Tests

Replace mocked `SchedulerTestCase` with a tiny real month: 2–3 people, 1–2 tasks, 4 weeks, known prefs. Assert who is assigned under the current objective, then under a stub objective. Include the abundance case: 8 eligible, 4 slots → at most one each.

## Also strip

Empty `constrain_assign_only_eligible_people`. Root leftover `settings.py`. Duplicate `get_service_day` later, not in this slice.

## Done when

`python manage.py test schedules.services` solves a real LP. Swapping the objective is a single module, not a rewrite of constraints.
