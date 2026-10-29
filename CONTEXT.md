# Service Scheduler

Django app that assigns congregation men to recurring worship tasks with integer linear programming (PuLP/CBC). Fill each month fairly, rotate people through tasks they signed up for, keep history, respect exclusions.

**Stack:** Django 5.1 · PostgreSQL · PuLP/CBC · vanilla JS · pdfkit

Volunteers are login `User`s. Single congregation. Charts, multi-church isolation, publish-email, reminders, and load (who gets leftover jobs) are planned: `docs/features/`.

## Domain

- **Service** — recurring event (Sun 9:00, Sun 10:30, Wednesday, Weekly). `day_of_week` is 0=Sunday; `None` = week-level.
- **Task** — role on a service. Symmetric `excludes` (cannot hold both in the same week). Each task also excludes itself on save.
- **TaskRequires** — person-specific: when assigned `task`, also assign `requires` the same week. Skips that pair’s exclusion for this person only. Directional. Eligible (`p > 0`) for both.
- **TaskPreference** `p(u,t) ≥ 0` — `0` never assign, `(0,1)` below baseline, `1` baseline, `>1` want more. No upper bound. A 1-task man on a crowded role (e.g. Lord’s supper aid) who wants more Sundays raises `p` on that task. Small pools (song leader) stay at `p = 1` so one specialist is not over-represented. Church-specific; not a solver special case.
- **Schedule** — one month. Optional `base_schedule` (previous month). `is_official` is unused (to remove). History is Assignment rows.
- **Assignment** — person + task + datetime on a schedule. Source of truth for history and fairness.
- **AssignmentStats** — derived snapshot (`ideal_average`, `actual_average`, `assignment_delta`), M2M to schedules. Recalculated on assignment save. Lifetime share. FairJobs does not read it; Catch-up share datalist sort uses `assignment_delta`.

## Objective

Default: **FairJobs** (`FairJobsObjective`). Minimize how far each eligible person lands from their fair share of each task, over the past 12 months plus this month.

```
fair share(u,t) = p(u,t) / Σ_v p(v,t)  ×  (times t appears in that span)
end_count(u,t)  = jobs u already did of t in the window  +  this month’s assignments
```

CBC minimizes Σ |end_count − fair share| (plus a tiny total-load tie-break). Preference is used once. New people start even. A catch-up cap stops a whole year’s owed jobs in one month.

Tasks that share `Task.rotation_group` are one family (song, prayer, Lord’s supper). Same-task consecutive week is still a hard rule. Across different tasks in the family, an extra job in two neighboring Sunday-start weeks (7 days) is a spill; CBC pays `rotation_weight` (default 2, same units as one job off fair share) per spill. Blank group means no family. A wider window is a later change. Code: `schedules/services/objectives.py`, `fairness.py`.

**Catch-up share** (`CatchUpShareObjective`) is frozen. Generate can still pick it. Maximize `(ideal · p − actual) · x` where `ideal = p/Σp`, so preference is applied twice. Fairness is lifetime share of that task (assignments before this month), not a 12-month window. New people with actual 0 look infinitely behind; jitter only if actual &lt; 5% of `ideal · p`.

## Constraints

Same hard rules for both objectives. Binary `x[(date_task, user)]` for each eligible pair.

| Rule | Effect |
|---|---|
| Fill every hole | Exactly one person per date-task |
| Eligible only | No variable if `p = 0` or inactive |
| Exclusions | Cannot hold two excluding tasks in the same Sunday-start week (`x_a + x_b ≤ 1`). Weekly holes pair with that week’s Sunday/Wednesday, not by list index. Skipped for a person who has `TaskRequires` on that pair. |
| TaskRequires | If this person takes `task`, they take `requires` that week (`x_task ≤ x_requires`). They can still hold `requires` alone. |
| Consecutive week | Same person, same task, two weeks in a row, including month boundary — skipped when the eligible pool is size 1 |
| Rotation family (FairJobs) | Soft: `Task.rotation_group`. Jobs of that family in two neighboring Sunday-start weeks: at most one, plus spill. Cost `rotation_weight` per extra job. Includes the previous month via `base_schedule`. |
| Per-task spread | At most one if people > slots; else each eligible person at least once, at most `⌈slots/people⌉` |
| Cap 7 | Max assignments per person this month |
| Locks | Current cells and previous-month `base_schedule` rows are extra ILP variables with `x == 1`. That `(task, user)` skips consecutive-week and per-task spread. |

CBC typically a few seconds. Persist is `"YYYY-M-D-task_id" → "Last, First"`.

## Frontend

Month grid: Django templates + `schedules/static/schedules/schedule.js`. One table; each hole is `<input class="assignment-input" list="{{ task.id }}">`. Datalist of eligible users by inverted name (`Last, First`), sorted by FairJobs `count_so_far − target` (Catch-up share uses `assignment_delta`). Enter autocompletes the first match. Unknown typed names are skipped on save.

Also: drag-swap, 400ms debounce plus pagehide flush of dirty cells, Generate (skeleton on empty cells), Legal-landscape PDF, per-person count panel, clear. Overlay in `month_schedule.html`. Unauthenticated `/schedules/` goes to `/login/`. Generate, update, clear, and PDF are `csrf_exempt`; `LoginRequiredMiddleware` still wraps `/schedules/`.

## Key files

- `schedules/services/scheduler.py` — ILP
- `schedules/services/objectives.py` — FairJobsObjective (default), CatchUpShareObjective (old)
- `schedules/services/fairness.py` — 12-month job counts / targets for FairJobs
- `schedules/models.py` — domain
- `schedules/views.py` / `static/schedules/schedule.js` — month UI
- `schedules/utils.py` and `schedules/templatetags/schedule_tags.py` — `get_service_day` (keep in sync)
- `users/models.py` — email login
- `core/` — seed-only (`core/management/commands/` from `core/fixtures/`)

## Commands

```
source venv/bin/activate && python manage.py test
source venv/bin/activate && python manage.py runserver
./manage.py seed_data
python manage.py dump_compare_db
python manage.py compare_objectives FairJobs --dump
```

## Database

Schema changes are **manual-approve only**. Do not run `makemigrations` or `migrate` unless the user has approved a written change. Propose the change first: fields, nullability, FKs, uniqueness, and what happens to existing rows — in the README Models section and the relevant `docs/features/*.md`. After approval, one named migration. No autogenerated pile-ups, no silent rollbacks.

Test rows must be **identifiable and deletable**: test users/emails with a reserved prefix (e.g. `test+…@`). Year comparison runs in the Django test database only (`schedules.services.test_year_compare`). Generated months are deleted by PK; dumped history `Assignment` rows stay.

See README.md Models, docs/features/.
