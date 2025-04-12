from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from itertools import chain, zip_longest
from django.contrib.auth import get_user_model
from schedules.models import AssignmentStats, Schedule, Service, Task, TaskPreference
from schedules.services.datetask import DateTask
from schedules.utils import (
    get_service_day,
    get_month_calendar,
    get_service_weeks,
)
from users.models import User

from pulp import LpVariable, LpProblem, LpMaximize, lpSum, PULP_CBC_CMD, LpStatus


class Scheduler:

    def __init__(
        self,
        schedule: Schedule,
        services: list[Service],
        provided_assignments: dict[str, str] = {},
    ):
        # TODO optimize queries
        # TODO clean up this setup into functions, pass in member variables instead of referencing self
        self.max_assignments = 7
        self.year = schedule.date.year
        self.month = schedule.date.month
        self.services = services
        self.month_calendar, self.month_name = get_month_calendar(self.year, self.month)

        # TODO filter by group
        self.users = get_user_model().objects.filter(is_active=True)
        self.service_days = {service.day_of_week for service in services}
        self.service_weeks = get_service_weeks(self.month_calendar, self.service_days)
        self.date_tasks = self.get_date_tasks()

        self.provided_assignment_vars = []
        if provided_assignments:
            self.users_by_inverted_name = {
                user.inverted_name(): user for user in self.users
            }
            self.provided_assignment_vars = [
                (
                    DateTask.from_str(date_task_str),
                    self.users_by_inverted_name[user_name],
                )
                for date_task_str, user_name in provided_assignments.items()
            ]

        # Validate provided date tasks
        for date_task, _ in self.provided_assignment_vars:
            if date_task not in set(self.date_tasks):
                raise ValueError(f"date_task {date_task} not found in date_tasks")

        # optionally if len(provided_date_tasks) == len(date_tasks) we could return here
        # maybe we should handle on frontend
        # if len(self.provided_assignment_vars) == len(self.date_tasks):
        #     print("provided assignments cover all date tasks")
        #     # but what to return? Flip a boolean to indicate that provided assignments were used

        self.tasks = self.get_tasks()
        self.task_exclusions = self.get_exclusions()
        self.eligibility = self.get_eligiblity()

        # TODO filter by group
        self.assignment_stats = (
            schedule.base_schedule.assignment_stats.all().select_related("user", "task")
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

        # Get assignments from the base schedule
        self.base_assignments = schedule.base_schedule.assignments.all().select_related(
            "user", "task"
        )

        # Create a dictionary mapping (date, task_id) to user for quick lookup
        # and create DateTasks for these assignments
        self.base_date_tasks = []
        self.base_assignments_dict = {}
        for assignment in self.base_assignments:
            date_str = assignment.assigned_at.strftime("%Y-%m-%d")
            date_task = DateTask(date_str, assignment.task)
            self.base_assignments_dict[date_task] = assignment.user

            # Create DateTask for each assignment
            self.base_date_tasks.append((date_task, assignment.user))

        self.assignment_vars = list(
            set(
                chain(
                    (
                        (date_task, user)
                        for user in self.users
                        for date_task in self.date_tasks
                        if self.is_eligible(user, date_task)
                    ),
                    self.base_date_tasks,  # previous month assignments
                )
            )
        )

        self.x = LpVariable.dicts(
            "assignment",
            self.assignment_vars,
            cat="Binary",
        )

        # Cache for adjusted averages
        self._adjusted_average_cache = {}

        self.set_objective_function()
        self.constrain_past_assignments()
        self.constrain_one_person_per_task()
        self.constrain_assign_only_eligible_people()
        self.constrain_do_not_assign_excluded_tasks()
        self.constrain_do_not_over_assign_same_task()
        self.constrain_month_boundary_assignments()
        self.constrain_total_assignments()
        self.constrain_provided_assignments()

    def solve(self, verbose: bool = False) -> tuple[any, dict[str, str]]:
        result = self.prob.solve(PULP_CBC_CMD(msg=verbose))

        if self.prob.status == -1:
            print(f"result: {LpStatus[self.prob.status]}")
            print("debug constraints")

        assignment = {}
        for user in self.users:
            assigned_date_tasks = [
                date_task
                for date_task in self.date_tasks
                if (date_task, user) in self.x
                and self.x[(date_task, user)].value() == 1
            ]
            if assigned_date_tasks:
                # record assignment
                assignment[user.inverted_name()] = assigned_date_tasks
                for date_task in assigned_date_tasks:
                    if not self.is_eligible(user, date_task):
                        print(
                            f"user {user.inverted_name()} is not eligible for task {date_task.task_id}"
                        )

        tasks_to_user_name = {}
        for user in self.users:
            if user.inverted_name() in assignment:
                for date_task in assignment[user.inverted_name()]:
                    tasks_to_user_name[date_task] = user.inverted_name()

        # I don't think we actually need to sort
        sorted_assignments = OrderedDict()
        for date_task, user_name in sorted(
            tasks_to_user_name.items(), key=lambda x: x[0].task.order
        ):
            sorted_assignments[str(date_task)] = user_name

        return result, sorted_assignments

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
                float(self.get_ideal_average(user, date_task))
                - (
                    float(self.get_adjusted_actual_average(user, date_task))
                    * self.user_task_preferences[user.pk][date_task.task_id].value
                )
            )
            # 1 if assigned, 0 otherwise
            * self.x[(date_task, user)]
            for user in self.users
            for date_task in self.date_tasks
            if self.is_eligible(user, date_task)
        )

    def get_adjusted_actual_average(self, user: User, date_task: DateTask):
        cache_key = (user.pk, date_task.task_id)

        if cache_key in self._adjusted_average_cache:
            return self._adjusted_average_cache[cache_key]

        actual = float(self.get_actual_average(user, date_task))
        ideal = float(self.get_ideal_average(user, date_task))

        # Very low threshold - only affect users with almost no assignments
        threshold_value = ideal * 0.05  # 5% of ideal

        if actual < threshold_value:
            # Binary-like adjustment - either fully adjust or not
            # For users below threshold, pull them 90% of the way to ideal
            adjusted_actual = actual + (ideal - actual) * 0.9
            # print(
            #     f"pulling {actual} to {adjusted_actual} for {user.inverted_name()} {date_task.task_id}"
            # )
            self._adjusted_average_cache[cache_key] = adjusted_actual
            return adjusted_actual

        self._adjusted_average_cache[cache_key] = actual
        return actual

    def get_actual_average(self, user: User, date_task: DateTask):
        if user.pk not in self.user_task_stats:
            print(f"user {user.pk} does not have a task stat")
            return 0
        if date_task.task_id not in self.user_task_stats[user.pk]:
            raise KeyError(
                f"user {user.pk} does not have a task stat for task {date_task.task_id}"
            )
        return self.user_task_stats[user.pk][date_task.task_id].actual_average

    def get_ideal_average(self, user: User, date_task: DateTask):
        if user.pk not in self.user_task_stats:
            return 0
        if date_task.task_id not in self.user_task_stats[user.pk]:
            raise KeyError(
                f"user {user.pk} does not have a task stat for task {date_task.task_id}"
            )
        return self.user_task_stats[user.pk][date_task.task_id].ideal_average

    def constrain_past_assignments(self):
        """Constrain all past assignments variables to 1"""
        for base_date_task, user in self.base_assignments_dict.items():
            self.prob += self.x[(base_date_task, user)] == 1

    def constrain_one_person_per_task(self):
        """Constrain each task to have only one person assigned to it"""
        for date_task in self.date_tasks:
            self.prob += (
                lpSum(
                    self.x[(date_task, user)]
                    for user in self.users
                    if self.is_eligible(user, date_task)  # not in original
                )
                == 1
            )

    def constrain_assign_only_eligible_people(self):
        # TODO may not need, only have eligible date_task:user assignment variables now
        pass

    def constrain_do_not_assign_excluded_tasks(self):
        for task1, task2 in self.task_exclusions:
            for user in self.users:
                if self.is_eligible(user, task1) and self.is_eligible(user, task2):
                    for ineligible_pair in self.week_aligned_date_task_pairs(
                        task1, task2
                    ):
                        if (
                            0 not in ineligible_pair
                            and ineligible_pair[0] != ineligible_pair[1]
                        ):
                            self.prob += (
                                self.x[(ineligible_pair[0], user)]
                                + self.x[(ineligible_pair[1], user)]
                                <= 1
                            )

    def constrain_do_not_over_assign_same_task(self):
        for task in self.tasks:
            task_id = task.id
            eligible = self.get_eligible(task)
            num_eligible = len(eligible)
            for user in eligible:
                date_tasks = self.filter_date_tasks_by_task(self.date_tasks, task_id)
                if num_eligible > len(date_tasks):
                    # we have an abundance everyone should go at most once
                    self.prob += (
                        lpSum(self.x[(date_task, user)] for date_task in date_tasks)
                        <= 1
                    )
                else:
                    # Some may repeat, but no one should repeat more than one more than the other people
                    self.prob += (
                        lpSum(self.x[(date_task, user)] for date_task in date_tasks)
                        <= (len(date_tasks) + num_eligible - 1) / num_eligible
                    )
                    # And everyone should get assigned at least once
                    self.prob += (
                        lpSum(self.x[(date_task, user)] for date_task in date_tasks)
                        >= 1
                    )

    def constrain_total_assignments(self):
        for user in self.users:
            # Calculate the user's average assignment delta across all tasks
            total_delta = 0
            task_count = 0

            for task in self.tasks:
                if (
                    user.pk in self.user_task_stats
                    and task.id in self.user_task_stats[user.pk]
                ):
                    stat = self.user_task_stats[user.pk][task.id]
                    # Only penalize positive deltas (over-assignment)
                    # Negative deltas (under-assignment) will be treated as 0
                    delta = max(0, float(stat.assignment_delta))
                    total_delta += delta
                    task_count += 1

            # Calculate average delta (0 if no tasks)
            avg_delta = total_delta / task_count if task_count > 0 else 0

            # Scale the maximum assignments based on the delta
            # If delta is large (over-assigned), they get fewer assignments
            # If delta is small or negative (under-assigned), they get more assignments
            # We'll use a sigmoid-like function to scale between 1 and 5 assignments
            # The scaling factor will be between 0.2 and 1.0
            scaling_factor = 1.0 / (1.0 + avg_delta)
            scaled_max_assignments = max(
                1, min(5, int(self.max_assignments * scaling_factor))
            )
            print(
                f"max assignments for {user.inverted_name()}: {scaled_max_assignments}"
            )

            self.prob += (
                lpSum(
                    self.x[(date_task, user)]
                    for date_task in self.date_tasks
                    if self.is_eligible(user, date_task)
                )
                <= scaled_max_assignments
            )

    def constrain_provided_assignments(self):
        for date_task, user in self.provided_assignment_vars:
            self.prob += self.x[(date_task, user)] == 1

    def constrain_month_boundary_assignments(self):
        """
        do not double assign person in next week if there are multiple choices
        month boundary doesn't matter rename method
        """
        today = datetime(self.year, self.month, 1)
        first_of_month = today.replace(day=1)
        last_week_prev_month = first_of_month - timedelta(days=7)

        filtered_assignments = {}
        for date_task, assigned in self.assignment_vars:
            date_part = date_task.date
            date_obj = datetime.strptime(date_part, "%Y-%m-%d")

            if date_obj >= last_week_prev_month:
                filtered_assignments[date_task] = assigned

        task_consec_pairs_dict = defaultdict(list)
        grouped_tasks = defaultdict(list)

        for date_task in filtered_assignments.keys():
            grouped_tasks[date_task.task_id].append(date_task)

        # Sort and create tuples
        # assumes we schedule contiguous months
        # sort, then group by
        # {
        # task: [(dt0,dt1), (dt1, dt2), (dt2, dt3), (dt3, dt4])]
        # }
        for task_id, date_tasks in grouped_tasks.items():
            sorted_dates = sorted(
                date_tasks, key=lambda x: datetime.strptime(x.date, "%Y-%m-%d")
            )

            task_consec_pairs_dict[task_id] = [
                (sorted_dates[i], sorted_dates[i + 1])
                for i in range(len(sorted_dates) - 1)
            ]

        task_consec_pairs_dict = dict(task_consec_pairs_dict)

        for user in self.users:
            for task_id, consec_date_task_pairs in task_consec_pairs_dict.items():
                if (
                    self.is_eligible(user, task_id)
                    # must check that there are enough people to go around
                    and len(self.get_eligible(task_id)) >= 2
                ):
                    for i, (earlier_date_task, later_date_task) in enumerate(
                        consec_date_task_pairs
                    ):
                        if (
                            # earliest date is from last month, this assignment is known
                            i == 0
                            and user == filtered_assignments[earlier_date_task]
                        ) or i > 0:
                            self.prob += (
                                self.x[(earlier_date_task, user)]
                                + self.x[(later_date_task, user)]
                            ) <= 1

    def get_exclusions(self):
        exclusions = set()
        for service in self.services:
            for task in service.tasks.all():
                for exclusion in task.excludes.all():
                    exclusions.add((task.id, exclusion.id))

        return exclusions

    def week_aligned_date_task_pairs(self, task1: Task, task2: Task):
        """
        need to pad start to get weekly duties to align correctly
        otherwise we exclude tasks in different weeks
        """
        date_tasks1 = self.filter_date_tasks_by_task(self.date_tasks, task1)
        date_tasks2 = self.filter_date_tasks_by_task(self.date_tasks, task2)

        if len(date_tasks1) != len(date_tasks2):
            task1weekly = task1.service.day_of_week is None
            task2weekly = task2.service.day_of_week is None

            if task1weekly ^ task2weekly:
                weekly_date_tasks = date_tasks1 if task1weekly else date_tasks2
                daily_date_tasks = date_tasks2 if task1weekly else date_tasks1

                if (
                    len(weekly_date_tasks) > len(daily_date_tasks)
                    and int(daily_date_tasks[0].day_of_week)
                    not in self.month_calendar[0]
                ):
                    daily_date_tasks = [0, *daily_date_tasks]

                date_tasks1 = daily_date_tasks
                date_tasks2 = weekly_date_tasks

        return zip_longest(date_tasks1, date_tasks2, fillvalue=0)

    def filter_date_tasks_by_task(
        self, date_tasks: list[DateTask], task_id: str
    ) -> list[DateTask]:
        return [date_task for date_task in date_tasks if date_task.task_id == task_id]

    def get_tasks(self) -> list[Task]:
        tasks = []
        for service in self.services:
            tasks.extend(service.tasks.all())

        return tasks

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
                        date_tasks.append(
                            DateTask(f"{self.year}-{self.month}-{service_day}", task)
                        )
        return date_tasks

    def get_eligible(self, task_id_or_task: str | Task):
        if isinstance(task_id_or_task, str):
            return self.eligibility[task_id_or_task]
        elif isinstance(task_id_or_task, Task):
            return self.eligibility[task_id_or_task.id]

    def is_eligible(self, user: User, task_id_or_date_task: str | DateTask):
        if isinstance(task_id_or_date_task, str):
            return user in self.eligibility[task_id_or_date_task]
        elif isinstance(task_id_or_date_task, DateTask):
            return user in self.eligibility[task_id_or_date_task.task_id]

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
