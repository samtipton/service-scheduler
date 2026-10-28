# Resulting-count objective

Replace today’s frozen share catch-up with an LP that scores **the month it actually produces**, in **jobs**, with **`TaskPreference.value` used once**.

Depends on [scheduler-cleanup.md](scheduler-cleanup.md) and [pluggable-objective.md](pluggable-objective.md). Keep current constraints. Keep today’s `set_objective_function` as `CatchUpShareObjective` for A/B. Default in production stays the old formula until a [year-sandbox](year-sandbox.md) run looks better.

## What’s wrong with the current `lpSum`

```
(get_ideal_average * TaskPreference.value - get_adjusted_actual_average) * self.x[(date_task, user)]
```

`get_ideal_average` / `get_adjusted_actual_average` come from `AssignmentStats` (lifetime shares) and **do not change** when `self.x` is 1. Bob behind on six tasks can take six jobs in one month; each job still adds the same parenthetical (`constrain_total_assignments` cap 7). `p` is applied in `ideal` and again as a multiplier, so `p > 1` is a share compared to a number that is not a share. New people with `actual_average ≈ 0` look infinitely behind (`get_adjusted_actual_average` jitter only).

## Proposed

Window: `Assignment` rows in the 12 months before `schedule.date`, plus this month’s `self.date_tasks`. Eligible means `TaskPreference.value > 0`.

```
slots_past(t)     = Assignment count for task t in the window
slots_month(t)    = number of self.date_tasks with that task
slots_window(t)   = slots_past + slots_month
count_so_far(u,t) = Assignment count for (u, t) in the window
p(u,t)            = TaskPreference.value
target(u,t)       = (p(u,t) / Σ_v p(v,t)) * slots_window(t)
end_count(u,t)    = count_so_far(u,t) + Σ self.x[(dt, u)]  for dt.task_id == t
```

If `User.date_joined` is inside the window, use only slots after that date in `slots_window` / `count_so_far` for that user.

```
load_end(u)     = Σ_t end_count(u,t)
load_target(u)  = Σ_t target(u,t)
load_weight     = 0.01   # secondary term only; per-task L1 stays dominant
```

## Objective function

`LpMinimize` (today’s solver is `LpMaximize`). Code will live in `ResultingCountObjective.expression`, called from `Scheduler` instead of the current `lpSum`.

```
minimize
  Σ_{u,t} |end_count(u,t) − target(u,t)|
  + load_weight Σ_u |load_end(u) − load_target(u)|
```

`end_count` includes this month’s `self.x`. Assigning Bob to a `date_task` of task `t` adds 1 to `end_count(Bob, t)` and to `load_end(Bob)`. If he was behind, the absolute value drops; if he was at or past target, it rises.

PuLP has no `abs` on integer expressions. Linearize with slacks (`over`, `under`, `load_over`, `load_under` ≥ 0):

```
end_count(u,t) − target(u,t) = over(u,t) − under(u,t)
load_end(u) − load_target(u) = load_over(u) − load_under(u)

minimize
  Σ_{u,t} (over(u,t) + under(u,t))
  + load_weight Σ_u (load_over(u) + load_under(u))
```

That `minimize` line is the new objective. `load_weight` (0.01) is not a preference or a share. It is a small multiplier so CBC almost always improves per-task job counts first, and only uses total-load L1 to break ties (eight even song leaders → pick the four with fewer jobs overall). Constraints (one person per slot, exclusions, consecutive week, locks, abundance) stay on `self.x` as they are today.

**Catch-up constraint** (not part of the objective): `Σ_dt self.x[(dt,u)] ≤ ceil(Σ_t (p/Σp)*slots_month(t)) + 1`, still capped by existing `max_assignments = 7`. The secondary `load_weight` term is what spreads 4–6 vs 1–2 when per-task L1 is indifferent (8 song leaders all even → four must go +1).

**New people:** if they have no window `Assignment`s, set `count_so_far = target * slots_past / slots_window` (at target for the past). Drop `_adjusted_average_cache` jitter for this objective. First calendar month: also cap total `self.x` at 3.

Do not read `AssignmentStats` for this objective.

## Why this is better

| Current | This |
|---|---|
| Lifetime `actual_average` / `ideal_average` | Jobs in a 12-month window |
| `p` in `ideal` and again on the term | `p` only in `target` |
| Term frozen; sixth job scores like the first | `end_count` includes this month’s `self.x` |
| New `actual ≈ 0` → flood + jitter | Start even + first-month cap |
| 4–6 vs 1–2 across tasks | Secondary L1 on load + catch-up cap |
| One missed rare job looks like a big share (`/N`) | One job behind is one job on every task |

Fairness drift from manual edits still exists (those `Assignment`s are in `count_so_far`) but ages out of the window.

**Round-robin:** constraints are unchanged. Per-task `|end_count − target|` is least-served-first on each eligible task over the window (equal `p` → equal counts). It is not a cyclic name list. One month will not run every person through every pref; the catch-up cap is what stops dumping a year’s owed turns into one month.

A 1-task man on a crowded role is due few jobs at `p = 1`. Raise `TaskPreference.value` if that church wants him more often. Do not add a presence-floor constraint.

## Datalist sort (assignment cells)

Today `MonthView.get` orders `<datalist>` options by `assignment_delta` (most under-assigned first). Enter picks the first match (`autocompleteDatalist` in `schedule.js`).

With this objective, sort eligible users for task `t` by **`count_so_far(u,t) − target(u,t)` ascending** — same window and `target` as the LP. Most jobs-behind first. New people with virtual even history have difference `0` (middle of the list, not the top). Missing counts: `count_so_far = 0`.

Share one ranking helper with `ResultingCountObjective` so the dropdown and the solver cannot drift. Compute at page render; do not live-reorder after autosave until reload (same as today).

When `CatchUpShareObjective` is still selected, keep current `assignment_delta` sort.

## Done when

`ResultingCountObjective` is selectable next to `CatchUpShareObjective`. Tiny real-month tests: 8 people / 4 song-leader slots → four distinct people; a user behind on six tasks does not get six jobs in one month; `p = 2` vs `p = 1` yields about 2× jobs over a sandbox year, not a permanent “owed” share. Datalist for a task lists the most jobs-behind eligible user first.
