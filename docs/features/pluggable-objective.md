# Pluggable objective

Experiment with fairness math without touching constraints. Current formula and English: CONTEXT.md.

## Why 4–6 vs 1–2

`get_ideal_average` and `get_adjusted_actual_average` are computed from history and do not change when `self.x` is 1. If Bob is behind on several tasks, every `date_task` of those tasks uses the same `(ideal * pref - adjusted_actual)` term. The LP can set many of those `self.x` to 1 in one month (`constrain_total_assignments` cap 7). Someone eligible for only 1–2 tasks can only get 1–2. That part is `get_eligiblity`.

Abundance is already handled per task: 8 song leaders, 4 Sunday slots → at most one song-lead each. The pile-on is **across tasks**, not repeats of the same task.

## Same hole count (song leader vs usher)

Sunday 10am song leader and weekly usher both have about four holes a month. The sum treats them the same way: four terms, each `(target − actual)` for whoever fills that hole. There is no extra “song leader is louder” effect between those two.

`get_ideal_average`, `TaskPreference.value`, and `get_adjusted_actual_average` depend on `(user, date_task.task_id)`, not on which Sunday `date_task` is. So Bob’s song-leader term is the same on all four Sundays. If all four `self.x[(date_task, Bob)]` are 1, that term is added four times. `constrain_do_not_over_assign_same_task` already forbids that when 8 people > 4 slots. Four different people add four (possibly different) terms — same as usher.

A task with *fewer* holes this month (true monthly role, or 4 Sundays vs 5 Wednesdays) contributes fewer terms. That is a small calendar effect, not the 4–6 vs 1–2 pile-on.

## Share gap vs count deficit

For one task with `p = 1`, they rank people the same: `ideal − actual = (p/Σp) − count/N = (target_count − count) / N`, and `N` is shared. Lifetime share is count deficit in disguise, divided by all-time volume, no year window.

They diverge when: (1) `p ≠ 1` (`target = ideal · p`, not `count/N`); (2) comparing *across* tasks (`N` differs, so one missed rare job looks like a bigger share than one missed common job); (3) this month’s picks do not reduce the gap inside the solve; (4) lifetime vs a 12-month window.

## First experiment

[resulting-count-objective.md](resulting-count-objective.md): minimize L1 of resulting job counts vs `p/Σp` targets, with this month’s `self.x` inside the count.

## Shape in code

```python
class Objective:
    def expression(self, x, ctx) -> pulp expression
```

`ctx` has counts, prefs, slots, window. Keep today’s formula as `CatchUpShareObjective` so we can A/B.

## Done when

UI or a flag picks an objective name. Year-sandbox runs can choose one. Production default stays the current formula until a run looks better on charts.
