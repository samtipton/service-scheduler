"""Pluggable LP objectives. See CONTEXT.md and docs/features/pluggable-objective.md."""

import random

from pulp import LpMaximize, lpSum


class CatchUpShareObjective:
    """Current production objective. CONTEXT.md Objective Function."""

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


OBJECTIVES = {
    CatchUpShareObjective.name: CatchUpShareObjective,
}
