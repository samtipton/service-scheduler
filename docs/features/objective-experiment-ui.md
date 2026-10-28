# Objective experiment UI

Off the production schedules list: pick an objective, generate 12 sequential months, read hard numbers on top, eyeball 12 month grids, delete the run. Isolation rules: [year-sandbox.md](year-sandbox.md). Objectives: [pluggable-objective.md](pluggable-objective.md).

Production `MonthListView` / `MonthView` stay official-only. Experiment schedules never appear in that list, never `is_official`, never enter production `Assignment` history.

## Navigation

From schedules list, link **Experiments** → `/experiments/` (not mixed into the production `<ul>`).

**Index:** table of runs (name, objective, start month, created, status). Buttons: New run, open results, **Clean this experiment up**.

**New run:** name, start month (`YYYY-MM`), objective (`CatchUpShareObjective` | `ResultingCountObjective`), seed from production history yes/no. Same people/`TaskPreference` snapshot for the run. Submit starts 12 solves in order: month *n* assignments are history for month *n+1*. Status: queued / month k of 12 / failed / ready. Failed month stops the chain and keeps months 1..k−1 for debug.

**Results** (`/experiments/<id>/`): metrics block first, then a **3×4 grid** of the 12 months. Each cell is a scaled, read-only render of the existing month table (reuse templates; no generate/save/clear). Click a cell → full-size experiment month (same `assignment_cell` UI is OK; edits optional v2). PDF not required.

**Clean this experiment up:** confirm, then delete the 12 `Schedule`s, their `Assignment`s, and the run row. Production row counts unchanged. No undo.

**Compare (v1):** on the index, select two ready runs → `/experiments/compare/?a=&b=`. One table, two columns, same KPIs as below. No 24-grid page.

## What to measure

All figures from **this run’s** `Assignment` rows plus the frozen prefs. No `AssignmentStats`. Targets for display use the ResultingCount meaning so both objectives are scored on the same ruler.

A **hole** is one `DateTask`: one cell to fill (one Sunday of `song_leader`, one weekly `usher`, …). `holes(t)` = how many such cells of task `t` exist in the 12 generated months (`len` of that task’s `date_tasks`).

```
target(u,t)    = (p(u,t) / Σ_v p(v,t)) × holes(t)
load_target(u) = Σ_t target(u,t)
fill_ratio(u)  = count(u) / load_target(u)    # 1.0 = exactly their share
residual(u)    = count(u) − load_target(u)
```

`p/Σp` is Bob’s **fraction** of that task. Times `holes(t)` turns it into an **expected job count**. 48 song-leader cells, 8 people at `p = 1` → `target = 6`, not `0.125`. `load_target` sums those expected counts across tasks he signed up for. People with `p = 0` omitted. Unfilled cells counted separately.

`fill_ratio ≈ 1` for a 1-task man and a 10-task man means each got their **share of the cells they can fill**. It does **not** mean they appear equally often. A 1-task song leader among 8 eligible people is due ~6 jobs a year; someone on 10 tasks may be due ~40. That is per-task fairness. The 1-task man will look “absent” on the grid even when `fill_ratio = 1`. That is real, not a KPI bug — see Presence.

### Load (eligibility-adjusted)

| KPI | Why |
|---|---|
| `fill_ratio` min, median, max, mean, stddev | Pile-on vs starvation **after** eligibility |
| Histogram of `fill_ratio` | 4–6 vs 1–2 that is not “they signed up for more” |
| `residual` min / max | Jobs above/below fair |
| Max `count` in any single month, and max `count / that month’s load_target` | Frozen-term dump vs a busy-but-fair month |
| Eligible people with 0 jobs and `load_target > 0` | True starvation |
| Same `fill_ratio` stats **stratified** by eligibility width: 1–2 tasks vs 3–6 vs 7+ | Confirms wide-roster people are not eating the year |

Raw jobs per person (min/median/max) stay on the page as a “what the grid looks like” footnote, not the comparison.

### Presence (1-task men on crowded tasks)

`fill_ratio` will call a specialist “fair” while he appears rarely if many others share his only task (Lord’s supper aid). Extra KPIs so we can see it. **No solver special case.** If those men should appear more, raise `TaskPreference.value` on that task (`p > 1`). Song leader (small pool) stays at `p = 1`.

| KPI | Why |
|---|---|
| Distinct dates served / service dates in the year | How often he is on the grid |
| Months with ≥ 1 job | Show up at all this month? |
| `crowd(u)` = eligible people on his tasks (for 1-task: size of that one pool) | Song leader vs Lord’s supper aid |
| Presence stats **stratified** by eligibility width and by `crowd` | Check whether a `p` bump moved the crowded 1-task rows |

### Per-task rotation

| KPI | Why |
|---|---|
| Σ \|count(u,t) − target(u,t)\| / n | Distance from fair jobs (CatchUpShare will usually lose; still the comparison) |
| Max \|count − target\| | Worst person-task |
| Unique people used per task | Rotation breadth |
| Mean jobs for `p ≥ 1.5` vs `p = 1` vs `0 < p < 1` | Whether preference is linear or squared |

### Constraints (must stay clean)

| KPI | Why |
|---|---|
| Unfilled holes | Solver gave up |
| Months with `LpStatus` infeasible | Hard fail |
| Consecutive same-task week violations | `constrain_month_boundary_assignments` / consecutive-week |
| Exclusion violations (same week) | `constrain_do_not_assign_excluded_tasks` |

### New people

If any `User.date_joined` falls in the 12 months (or a fixture flag): jobs in their first month vs later months. CatchUpShare should spike month 1; ResultingCount should not.

### Heatmaps (below KPIs, above the 12 grids)

- Person × month: job count and `fill_ratio` for that month
- Person × task: count, with target in the cell subtitle (`3 / 6`)
- People on heatmaps sorted by eligibility width, then name, so 1–2-task rows are not lost next to 12-task rows

## Eyeball

The 12 grids answer: does a month *look* like our congregation (same faces stacked, song leader repeating visually, empty cells). KPIs do not replace that. Two runs with similar MAD and different “feel” → trust the grids.

## Requirements

- Experiments nav is not the production schedule list.
- One run = one objective + 12 `kind=experiment` schedules, chained history, frozen prefs/people at start.
- Seed history optional; A/B of two objectives uses the same start month and the same seed choice.
- Results page: KPI block, two heatmaps, 12-grid, cleanup button.
- Cleanup deletes only that run. Official schedules, production `Assignment`s, and prefs unchanged (assert in a test).
- Compare page: two runs, KPI table only.
- Generate is server-side sequential (not 12 parallel solves sharing history). Progress visible. Timeout-friendly (one month per request or a management command + poll).
- v1: no live edit on mini grids; no charts.js required (HTML tables + CSS grid).
- UI and tests call the same `run_year(objective, start, seed, constraint_names)` helper. Do not fork generate logic.

## Headless e2e (`schedules.tests.test_year_experiment`)

Same 12-month runner, no browser. Purpose: when we add or drop a constraint, see how **each** registered objective moves on the KPI table. Long-term one objective remains; this test stays as its year-long regression.

**Fixture** (tiny, deterministic, not full `seed_data`): ~8 people, 2–3 tasks including an exclusion pair, mixed `p` (0, 0.5, 1, 2), one user with `date_joined` in month 1, enough weeks for abundance (8 eligible, 4 holes).

**Matrix:** every `Objective` class × a named constraint set. v1 constraint sets:

- `default` — all current `constrain_*` methods
- `no_consecutive` — default minus consecutive-week / month-boundary
- `no_exclusions` — default minus excluded-task pairs

`Scheduler` takes `constraint_names` (cleanup slice). Adding a new `constrain_*` means adding it to `default` and, if we care, a with/without pair.

**Hard asserts** (fail the build):

- Exclusion and consecutive-week violations = 0 when those constraints are in the set; they may be > 0 when omitted (proves the constraint did work)
- Infeasible months = 0 on `default`
- Production `Assignment` / official `Schedule` counts unchanged
- Cleanup of the run leaves zero experiment rows

**Recorded, not pass/fail vs the other objective:** the KPI dict (`fill_ratio` min/max/stddev, MAD to target, max month `fill_ratio`, new-person month-1 `fill_ratio`, unique people per task, plus raw job min/max as footnote). Write `tests/snapshots/year_experiment.json` or print a table on `-v`. When a constraint change moves a number, the snapshot diff is the report. Do **not** assert ResultingCount MAD < CatchUpShare MAD; that is the eyeball/compare UI until we delete CatchUpShare.

Test users, schedules, and assignments created by this e2e use the experiment markers in CONTEXT.md Database and must clean up in `tearDown` / `addCleanup`.

Run: `python manage.py test schedules.tests.test_year_experiment` (slower; keep off the mocked unit module). Optional `@tag("year")` so CI can skip.

## Done when

From Experiments, a CatchUpShare year and a ResultingCount year can both complete on seed data. Results show the KPI table and 12 grids. Compare shows both columns. Cleanup of one run leaves the other and production intact. Infeasible or empty months are visible in the constraint KPIs.

`test_year_experiment` runs `default` for both objectives on the tiny fixture, asserts constraint KPIs, and emits the KPI table. Dropping consecutive-week from the set makes that violation KPI rise.
