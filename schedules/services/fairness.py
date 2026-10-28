"""Windowed job counts and FairJobs targets. Shared by the LP and datalist sort."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from schedules.models import Assignment, Schedule, Service, TaskPreference
from schedules.services.datetask import DateTask
from schedules.utils import get_month_calendar, get_service_day, get_service_weeks

WINDOW_MONTHS = 12


def add_months(year: int, month: int, delta: int) -> date:
    idx = year * 12 + (month - 1) + delta
    return date(idx // 12, idx % 12 + 1, 1)


def as_date(value) -> date:
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    dt = value
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.date()


def date_tasks_for_schedule(schedule: Schedule, services: list[Service]) -> list[DateTask]:
    year, month = schedule.date.year, schedule.date.month
    month_calendar, _ = get_month_calendar(year, month)
    service_days = {service.day_of_week for service in services}
    service_weeks = get_service_weeks(month_calendar, service_days)
    date_tasks = []
    for service in services:
        for task in service.tasks.all():
            for service_week in service_weeks:
                service_day = get_service_day(
                    service_week, service_days, service.day_of_week
                )
                if service_day and service_day != 0:
                    date_tasks.append(
                        DateTask(f"{year}-{month}-{service_day}", task)
                    )
    return date_tasks


@dataclass
class FairnessWindow:
    # count_so_far[(user, task)]: times this person already did this task in the
    #   12 months before this schedule. New people with no history are set to
    #   their fair share of the past so they start even, not infinitely behind.
    count_so_far: dict
    # slots_month[task]: how many cells of this task exist this month.
    slots_month: dict
    # target[(user, task)]: fair share over the past 12 months plus this month.
    #   (this person's preference / sum of preferences for the task)
    #   × (times the task appeared in that span).
    target: dict
    preference: dict
    preference_total: dict
    first_month_user_ids: set

    def ranking_key(self, user_id, task_id) -> float:
        """Jobs already done minus fair share. Most behind sorts first."""
        return self.count_so_far.get((user_id, task_id), 0) - self.target.get(
            (user_id, task_id), 0
        )

    def this_month_fair_load(self, user_id) -> float:
        """How many jobs this person is due this month, across all their tasks.

        For each task: (their preference / everyone's preferences) × cells of
        that task this month. Used only as the catch-up cap, not the objective.
        """
        total = 0.0
        for (uid, task_id), pref in self.preference.items():
            if uid != user_id or pref <= 0:
                continue
            denom = self.preference_total.get(task_id, 0)
            if not denom:
                continue
            total += (pref / denom) * self.slots_month.get(task_id, 0)
        return total


def build_fairness_window(schedule: Schedule, services: list[Service], users) -> FairnessWindow:
    month_start = date(schedule.date.year, schedule.date.month, 1)
    window_start = add_months(month_start.year, month_start.month, -WINDOW_MONTHS)

    slots_month = defaultdict(int)
    for dt in date_tasks_for_schedule(schedule, services):
        slots_month[dt.task_id] += 1

    user_ids = {u.pk for u in users}
    preference = {}
    preference_total = defaultdict(float)
    for pref in TaskPreference.objects.filter(value__gt=0, user_id__in=user_ids):
        preference[(pref.user_id, pref.task_id)] = pref.value
        preference_total[pref.task_id] += pref.value

    qs = Assignment.objects.filter(
        assigned_at__date__gte=window_start,
        assigned_at__date__lt=month_start,
    ).select_related("user")
    if schedule.pk:
        qs = qs.exclude(schedule_id=schedule.pk)
    assignments = list(qs)

    user_by_id = {u.pk: u for u in users}

    def user_start(user) -> date:
        joined = as_date(user.date_joined)
        if joined >= month_start:
            return month_start
        return max(window_start, date(joined.year, joined.month, 1))

    dates_by_task = defaultdict(list)
    raw_count = defaultdict(int)
    users_with_history = set()
    for assignment in assignments:
        on = as_date(assignment.assigned_at)
        dates_by_task[assignment.task_id].append(on)
        user = user_by_id.get(assignment.user_id) or assignment.user
        if on >= user_start(user):
            raw_count[(assignment.user_id, assignment.task_id)] += 1
            users_with_history.add(assignment.user_id)

    first_month_user_ids = set()
    count_so_far = {}
    target = {}
    for user in users:
        start = user_start(user)
        joined_this_month = as_date(user.date_joined) >= month_start
        if joined_this_month or user.pk not in users_with_history:
            if joined_this_month:
                first_month_user_ids.add(user.pk)
        for task_id, month_holes in slots_month.items():
            p = preference.get((user.pk, task_id), 0)
            if p <= 0:
                continue
            denom = preference_total.get(task_id, 0)
            past = sum(1 for d in dates_by_task.get(task_id, []) if d >= start)
            slots_window = past + month_holes
            tgt = (p / denom) * slots_window if denom else 0.0
            target[(user.pk, task_id)] = tgt
            own = raw_count.get((user.pk, task_id), 0)
            if own == 0 and slots_window:
                count_so_far[(user.pk, task_id)] = tgt * past / slots_window
            else:
                count_so_far[(user.pk, task_id)] = float(own)

    return FairnessWindow(
        count_so_far=count_so_far,
        slots_month=dict(slots_month),
        target=target,
        preference=preference,
        preference_total=dict(preference_total),
        first_month_user_ids=first_month_user_ids,
    )
