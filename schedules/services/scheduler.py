from collections import defaultdict
from django.contrib.auth import get_user_model
from schedules.models import AssignmentStats, Schedule, Service, Task, TaskPreference
from schedules.utils import (
    get_service_day,
    get_month_calendar,
    get_service_weeks,
)
from users.models import User

from pulp import LpVariable, LpProblem, LpMaximize, lpSum


class Scheduler:
    class DateTask:
        def __init__(self, date: str, task_id: str):
            self.date = date
            self.task_id = task_id

        def __str__(self):
            return f"{self.date}-{self.task_id}"

    def __init__(
        self,
        schedule: Schedule,
        services: list[Service],
    ):
        # TODO optimize queries
        self.year = schedule.date.year
        self.month = schedule.date.month
        self.services = services
        self.month_calendar, self.month_name = get_month_calendar(self.year, self.month)

        # TODO filter by group
        self.users = get_user_model().objects.all()
        self.service_days = {service.day_of_week for service in services}
        self.service_weeks = get_service_weeks(self.month_calendar, self.service_days)
        self.date_tasks = self.get_date_tasks()
        self.eligibility = self.get_eligiblity()

        # TODO filter by group
        self.assignment_stats = schedule.assignment_stats.all().select_related(
            "user", "task"
        )
        # Dictionary of dictionaries for user -> task -> assignment_stat
        self.user_task_stats: defaultdict[int, dict[str, AssignmentStats]] = (
            defaultdict(dict)
        )
        for stat in self.assignment_stats:
            self.user_task_stats[stat.user.pk][stat.task.id] = stat

        # Dictionary of dictionaries for user -> task -> task_preference
        # TODO filter by group
        self.user_task_preferences: defaultdict[int, dict[str, TaskPreference]] = (
            defaultdict(dict)
        )
        task_preferences = TaskPreference.objects.all().select_related("user", "task")
        for preference in task_preferences:
            self.user_task_preferences[preference.user.pk][
                preference.task.id
            ] = preference

        # TODO INCLUDE HISTORICAL VARS FROM BASE SCHEDULE/ ALL ASSIGNMENTS
        self.assignment_vars = list(
            (date_task.task_id, user)
            for user in self.users
            for date_task in self.date_tasks
            if self.is_eligible(user, date_task)
        )

        self.x = LpVariable.dicts(
            "assignment",
            self.assignment_vars,
            cat="Binary",
        )

        self.set_objective_function()
        # self.constrain_past_assignments()
        # self.constrain_one_person_per_task()
        # self.constrain_assign_only_eligible_people()
        # self.constrain_do_not_assign_excluded_tasks()
        # self.constrain_do_not_over_assign_in_month()
        # self.constrain_do_not_over_assign_new_people()
        # self.constrain_month_boundary_assignments()

    def set_objective_function(self):
        """
        We want to choose assignees so as to Maximize the deviation between
        their historical mean and the ideal mean.
        Over time, we should converge to everyone having the ideal mean
        """
        self.prob = LpProblem("Scheduling_Problem", LpMaximize)
        self.prob += lpSum(
            # maximize the difference between ideal and actual averages
            (
                self.user_task_stats[user.pk][date_task.task_id].ideal_average
                - (
                    self.user_task_stats[user.pk][date_task.task_id].actual_average
                    * self.user_task_preferences[user.pk][date_task.task_id].value
                )
            )
            # 1 if assigned, 0 otherwise
            * self.x[(date_task.task_id, user)]
            for user in self.users
            for date_task in self.date_tasks
            # if self.is_eligible(person, trim_task_name(date_task))
        )

    def is_eligible(self, user: User, date_task: DateTask):
        return user in self.eligibility[date_task.task_id]

    def get_date_tasks(self) -> list[DateTask]:
        """
        A date task is a task that is scheduled for a specific date.
        It is a string of the form "YYYY-MM-DD-TASK_ID"
        For tasks for services that are scheduled every week (service.day_of_week is None),
        we will choose the earliest day in that week that has a service scheduled.

        This logic must be identical to schedule_tags#get_service_day
        EXCEPT that we do not create date_tasks with days of value '0'
        (which is the value for days that are not in the month).

        TODO See if we need to preselect tasks here.
        """
        date_tasks = []
        for service in self.services:
            for task in service.tasks.all():
                for service_week in self.service_weeks:
                    service_day = get_service_day(
                        service_week, self.service_days, service.day_of_week
                    )
                    if service_day and service_day != 0:
                        # date_tasks.append(
                        #     f"{self.year}-{self.month}-{service_day}-{task.id}"
                        # )
                        date_tasks.append(
                            Scheduler.DateTask(
                                f"{self.year}-{self.month}-{service_day}", task.id
                            )
                        )
        return date_tasks

    def get_eligiblity(self):
        """
        A user is eligible for a task if the user has a TaskPreference for the task
        """
        eligibility = defaultdict(set)
        for service in self.services:
            for task in service.tasks.all():
                for user in task.get_eligible_users():
                    eligibility[task.id].add(user)

        return eligibility

    def solve(self):
        pass
