"""Pluggable LP objectives. See CONTEXT.md."""

import math
import random
import re
from collections import defaultdict

from pulp import LpMaximize, LpMinimize, LpVariable, lpSum

from schedules.services.fairness import build_fairness_window


def adjacent_rotation_week_pairs(date_tasks):
    """Adjacent Sunday-start weeks that both have holes in the same family.

    Tasks with a blank rotation_group are ignored. Two weeks pair when their
    Sundays are 7 days apart. Each item is
    (group, earlier_week_date_tasks, later_week_date_tasks).
    """
    by_group_week = defaultdict(lambda: defaultdict(dict))
    for date_task in date_tasks:
        group = (getattr(date_task.task, "rotation_group", None) or "").strip()
        if not group:
            continue
        by_group_week[group][date_task.week_sunday][date_task] = date_task

    pairs = []
    for group, by_week in by_group_week.items():
        weeks = sorted(by_week)
        for earlier, later in zip(weeks, weeks[1:]):
            if (later - earlier).days == 7:
                pairs.append(
                    (group, list(by_week[earlier].values()), list(by_week[later].values()))
                )
    return pairs


def _lp_token(value) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_") or "x"


class CatchUpShareObjective:
    """Previous production objective. Frozen share catch-up. Kept for A/B."""

    name = "CatchUpShareObjective"
    sense = LpMaximize

    def __init__(self):
        self._adjusted_cache = {}

    def expression(self, x, ctx):
        return lpSum(
            (
                float(ctx.get_ideal_average(user, date_task))
                * ctx.user_task_preferences[user.pk][date_task.task_id].value
                - float(self._adjusted_actual(ctx, user, date_task))
            )
            * x[(date_task, user)]
            for user in ctx.users
            for date_task in ctx.date_tasks
            if ctx.is_eligible(user, date_task)
        )

    def _adjusted_actual(self, ctx, user, date_task):
        cache_key = (user.pk, date_task.task_id)
        if cache_key in self._adjusted_cache:
            return self._adjusted_cache[cache_key]

        actual = float(ctx.get_actual_average(user, date_task))
        ideal = float(ctx.get_ideal_average(user, date_task))
        preference = ctx.user_task_preferences[user.pk][date_task.task_id].value
        personal_target = ideal * preference
        threshold_value = personal_target * 0.05

        if actual < threshold_value:
            jitter_factor = 0.9 + random.uniform(0, 0.2)
            adjusted = actual + (personal_target - actual) * jitter_factor
            self._adjusted_cache[cache_key] = adjusted
            return adjusted

        self._adjusted_cache[cache_key] = actual
        return actual


class FairJobsObjective:
    """Score a month by how far each person lands from their fair share of each
    task, over the past 12 months plus this month. CBC picks the assignments.

    Fair share for (person, task):

        (their preference / sum of preferences for that task)
        × how many times that task appears in that span

    Preference is used once. Preference 2 is owed about twice as many of those
    jobs as preference 1.

    This function does not compute who gets which cell, and it does not compute
    over/under. It describes a puzzle for CBC:

      end_count — jobs they will have done after this month (history + this month)
      target    — their fair share over the same span
      over, under — solver variables, both ≥ 0
                    equality (always, exact): over − under = end_count − target
                    so over + under is the size of the miss; CBC sets the unused
                    side to 0 because a larger pair would score worse

    CBC minimizes the sum of over+under across every person and task. Hitting
    target costs 0; being 1 away costs 1; being 3 away costs 3. Misses are
    allowed — jobs are whole numbers, targets are often fractions — they just
    cost. Every job of gap costs the same, so helping someone 5 behind by one
    job is worth the same as helping someone 1 behind by one job.

    A tiny extra term (load_weight = 0.01) scores each person's total jobs the
    same way. It only breaks ties: eight even song leaders, four slots, pick
    the four with fewer jobs overall.

    Tasks that share Task.rotation_group are one family (song, prayer, Lord's
    supper). Same-task consecutive week stays a hard rule. Across
    different tasks in the family, two neighboring Sunday-start weeks may
    still both go to the same person. That extra family job is a spill.
    rotation_weight is the cost of one spill, in the same units as being one
    job off fair share. CBC may still spill when fairness or filling a hole
    costs more.

    People with no history are treated as already at their fair share for the
    past, so they start even. A hard cap stops anyone taking a whole year's
    owed jobs in one month.
    """

    name = "FairJobsObjective"
    sense = LpMinimize
    load_weight = 0.01  # keep per-task fairness first; total-load only breaks ties
    rotation_weight = 2.0  # cost of one extra family job in adjacent weeks

    def __init__(self, rotation_weight=None):
        if rotation_weight is not None:
            self.rotation_weight = rotation_weight

    def expression(self, x, ctx):
        window = build_fairness_window(ctx.schedule, ctx.services, ctx.users)
        ctx.fairness_window = window

        # One (person, task) pair for each eligible person on a task that has
        # cells this month. Those are the pairs the fairness score covers.
        pair_keys = [
            (user.pk, task.id)
            for user in ctx.users
            for task in ctx.tasks
            if ctx.is_eligible(user, task) and window.slots_month.get(task.id, 0) > 0
        ]
        if not pair_keys:
            return 0

        # Blanks CBC will fill. Both ≥ 0. Never assigned in Python.
        #   over  — jobs above target    under — jobs below target
        over = LpVariable.dicts("over", pair_keys, lowBound=0)
        under = LpVariable.dicts("under", pair_keys, lowBound=0)
        user_ids = [user.pk for user in ctx.users]
        # Same split, but for the person's total jobs across all their tasks.
        load_over = LpVariable.dicts("load_over", user_ids, lowBound=0)
        load_under = LpVariable.dicts("load_under", user_ids, lowBound=0)
        user_by_pk = {user.pk: user for user in ctx.users}

        end_count = {}
        for user_id, task_id in pair_keys:
            user = user_by_pk[user_id]
            # How many cells of this task we give them this month (0, 1, …).
            assigned = lpSum(
                x[(date_task, user)]
                for date_task in ctx.date_tasks
                if date_task.task_id == task_id and (date_task, user) in x
            )
            # Jobs they will have done after this month is filled.
            end_count[(user_id, task_id)] = (
                window.count_so_far.get((user_id, task_id), 0) + assigned
            )
            tgt = window.target.get((user_id, task_id), 0)
            # Name the gap. Equality, always, not a cap and not a score:
            #   over − under = end_count − target
            # Many pairs work: gap +2 → (2,0) or (3,1) or (100,98).
            # The return is what picks the tight pair and pushes end_count
            # toward target.
            ctx.prob += (
                end_count[(user_id, task_id)] - tgt
                == over[(user_id, task_id)] - under[(user_id, task_id)]
            )

        for user in ctx.users:
            # Same over/under naming of a gap, but for this person's *total*
            # jobs across all their tasks. load_end includes this month's
            # assignments (so lpSum); load_target is a fixed number (so sum).
            load_end = lpSum(
                end_count[(user.pk, task_id)]
                for task_id in {t for u, t in pair_keys if u == user.pk}
            )
            load_target = sum(
                window.target.get((user.pk, task_id), 0)
                for task_id in {t for u, t in pair_keys if u == user.pk}
            )
            ctx.prob += load_end - load_target == load_over[user.pk] - load_under[user.pk]

            # Hard limit on cells this person may take this month. Not scored;
            # the solver cannot exceed it. fair is their share of this month's
            # cells; ceil(fair)+1 lets them take one extra to catch up; never
            # above the existing 7-job max. First calendar month: also at most 3.
            fair = window.this_month_fair_load(user.pk)
            cap = min(ctx.max_assignments, math.ceil(fair) + 1)
            if user.pk in window.first_month_user_ids:
                cap = min(cap, 3)
            eligible_dts = [
                date_task
                for date_task in ctx.date_tasks
                if ctx.is_eligible(user, date_task) and (date_task, user) in x
            ]
            if eligible_dts:
                ctx.prob += lpSum(x[(dt, user)] for dt in eligible_dts) <= cap

        # Score CBC minimizes. over+under is the size of each (person, task)
        # miss (CBC sets the unused side to 0). Sum those misses. Missing
        # target is allowed; it costs 1 per job of gap. The 0.01 term is the
        # same idea for each person's total jobs, and only breaks ties.
        # rotation_weight * spill is the adjacent-week family extra.
        fairness = lpSum(over[k] + under[k] for k in pair_keys) + self.load_weight * lpSum(
            load_over[uid] + load_under[uid] for uid in user_ids
        )
        return fairness + self._rotation_spill_terms(x, ctx)

    def _rotation_spill_terms(self, x, ctx):
        """Soft cap: at most one family job across two neighboring weeks.

        For each person and each adjacent pair of Sunday-start weeks that both
        have holes in the same rotation_group:

            jobs in week A + jobs in week B  ≤  1 + spill

        spill is 0 when they take at most one of those holes. Each extra job
        is one spill. Previous-month holes in x (base_schedule) count, so a
        locked Wednesday song leader penalizes the next Sunday.
        """
        pairs = adjacent_rotation_week_pairs({dt for dt, _ in x})
        keys = []
        terms = {}
        for user in ctx.users:
            for group, week_a, week_b in pairs:
                xa = [dt for dt in week_a if (dt, user) in x]
                xb = [dt for dt in week_b if (dt, user) in x]
                if not xa or not xb:
                    continue
                key = (
                    user.pk,
                    _lp_token(group),
                    week_a[0].week_sunday.strftime("%Y%m%d"),
                )
                keys.append(key)
                terms[key] = (user, xa, xb)
        if not keys:
            return 0
        spill = LpVariable.dicts("rot_spill", keys, lowBound=0)
        for key, (user, xa, xb) in terms.items():
            ctx.prob += (
                lpSum(x[(dt, user)] for dt in xa)
                + lpSum(x[(dt, user)] for dt in xb)
                <= 1 + spill[key]
            )
        return self.rotation_weight * lpSum(spill[k] for k in keys)


OBJECTIVES = {
    FairJobsObjective.name: FairJobsObjective,
    CatchUpShareObjective.name: CatchUpShareObjective,
}


def get_objective(name=None):
    if name is None:
        return FairJobsObjective()
    if not isinstance(name, str):
        return name
    cls = OBJECTIVES.get(name)
    if cls is None:
        raise ValueError(f"Unknown objective: {name}")
    return cls()

