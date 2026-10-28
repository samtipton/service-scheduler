from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta
from itertools import chain

from django.contrib.auth import get_user_model
from django.db.models import Count
from pulp import LpVariable, LpProblem, lpSum, PULP_CBC_CMD, LpStatus

from schedules.models import Assignment, Schedule, Service, Task, TaskPreference
from schedules.services.datetask import DateTask
from schedules.services.objectives import get_objective
from schedules.utils import (
    get_service_day,
    get_month_calendar,
    get_service_weeks,
)
from users.models import User


CONSTRAINTS = {
    "past_assignments": "constrain_past_assignments",
    "one_person_per_task": "constrain_one_person_per_task",
    "do_not_assign_excluded_tasks": "constrain_do_not_assign_excluded_tasks",
    "do_not_over_assign_same_task": "constrain_do_not_over_assign_same_task",
    "month_boundary_assignments": "constrain_month_boundary_assignments",
    "total_assignments": "constrain_total_assignments",
    "provided_assignments": "constrain_provided_assignments",
}
DEFAULT_CONSTRAINT_NAMES = tuple(CONSTRAINTS.keys())


class Scheduler:

    def __init__(
        self,
        schedule: Schedule,
        services: list[Service],
        locked_in_assignments: dict[str, str] | None = None,
        objective=None,
        constraint_names: tuple[str, ...] | None = None,
    ):
        self.max_assignments = 7
        self.schedule = schedule
        self.objective = get_objective(objective)
        self.constraint_names = tuple(constraint_names or DEFAULT_CONSTRAINT_NAMES)
        unknown = [n for n in self.constraint_names if n not in CONSTRAINTS]
        if unknown:
            raise ValueError(f"Unknown constraint names: {unknown}")

        self._load(schedule, services, locked_in_assignments or {})
        self._build_variables()
        self._set_objective()
        self._apply_constraints()

    def _load(
        self,
        schedule: Schedule,
        services: list[Service],
        locked_in_assignments: dict[str, str],
    ):
        self.year = schedule.date.year
        self.month = schedule.date.month
        self.services = services
        self.month_calendar, self.month_name = get_month_calendar(self.year, self.month)
        self.users = list(get_user_model().objects.filter(is_active=True))
        self.service_days = {service.day_of_week for service in services}
        self.service_weeks = get_service_weeks(self.month_calendar, self.service_days)
        self.date_tasks = self.get_date_tasks()

        self.locked_in_assignment_vars = []
        if locked_in_assignments:
            self.users_by_inverted_name = {
                user.inverted_name(): user for user in self.users
            }
            self.locked_in_assignment_vars = [
                (
                    DateTask.from_str(date_task_str),
                    self.users_by_inverted_name[user_name],
                )
                for date_task_str, user_name in locked_in_assignments.items()
            ]

        for date_task, _ in self.locked_in_assignment_vars:
            if date_task not in set(self.date_tasks):
                raise ValueError(f"date_task {date_task} not found in date_tasks")

        self.tasks = self.get_tasks()
        self.task_exclusions = self.get_exclusions()
        self.eligibility = self.get_eligiblity()
        self.user_task_preferences = self._load_preferences()
        self.preference_totals = self._preference_totals()
        self.assignment_counts, self.task_assignment_totals = (
            self._load_assignment_counts()
        )
        self._load_base_assignments(schedule)

    def _load_preferences(self):
        prefs: defaultdict[int, dict[str, TaskPreference]] = defaultdict(dict)
        for preference in TaskPreference.objects.all().select_related("user", "task"):
            prefs[preference.user.pk][preference.task.id] = preference
        return prefs

    def _preference_totals(self):
        active = {user.pk for user in self.users}
        totals = defaultdict(float)
        for user_id, task_prefs in self.user_task_preferences.items():
            if user_id not in active:
                continue
            for task_id, pref in task_prefs.items():
                if pref.value > 0:
                    totals[task_id] += pref.value
        return totals

    def _load_assignment_counts(self):
        """All-time Assignment counts before this month. Not AssignmentStats."""
        month_start = date(self.year, self.month, 1)
        qs = Assignment.objects.filter(assigned_at__date__lt=month_start)
        if self.schedule.pk:
            qs = qs.exclude(schedule_id=self.schedule.pk)

        counts = defaultdict(int)
        totals = defaultdict(int)
        for row in qs.values("user_id", "task_id").annotate(n=Count("id")):
            counts[(row["user_id"], row["task_id"])] = row["n"]
            totals[row["task_id"]] += row["n"]
        return counts, totals

    def _load_base_assignments(self, schedule: Schedule):
        self.base_date_tasks = []
        self.base_assignments_dict = {}
        if not schedule.base_schedule_id:
            return
        for assignment in schedule.base_schedule.assignments.all().select_related(
            "user", "task"
        ):
            date_str = assignment.assigned_at.strftime("%Y-%m-%d")
            date_task = DateTask(date_str, assignment.task)
            self.base_assignments_dict[date_task] = assignment.user
            self.base_date_tasks.append((date_task, assignment.user))

    def _build_variables(self):
        self.assignment_vars = list(
            set(
                chain(
                    (
                        (date_task, user)
                        for user in self.users
                        for date_task in self.date_tasks
                        if self.is_eligible(user, date_task)
                    ),
                    self.base_date_tasks,
                )
            )
        )
        self.x = LpVariable.dicts(
            "assignment",
            self.assignment_vars,
            cat="Binary",
        )

    def _set_objective(self):
        self.prob = LpProblem("Scheduling_Problem", self.objective.sense)
        self.prob += self.objective.expression(self.x, self)

    def _apply_constraints(self):
        for name in self.constraint_names:
            getattr(self, CONSTRAINTS[name])()

    def get_actual_average(self, user: User, date_task: DateTask):
        total = self.task_assignment_totals.get(date_task.task_id, 0)
        if not total:
            return 0.0
        return self.assignment_counts.get((user.pk, date_task.task_id), 0) / total

    def get_ideal_average(self, user: User, date_task: DateTask):
        total = self.preference_totals.get(date_task.task_id, 0)
        pref = self.user_task_preferences.get(user.pk, {}).get(date_task.task_id)
        if not pref or not total:
            return 0.0
        return pref.value / total

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

        sorted_assignments = OrderedDict()
        for date_task, user_name in sorted(
            tasks_to_user_name.items(), key=lambda x: x[0].task.order
        ):
            sorted_assignments[str(date_task)] = user_name

        return result, sorted_assignments

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
                    if self.is_eligible(user, date_task)
                )
                == 1
            )

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

            locked_assignments_for_task = {
                user
                for date_task, user in self.locked_in_assignment_vars
                if date_task.task_id == task_id
            }

            for user in eligible:
                date_tasks = self.filter_date_tasks_by_task(self.date_tasks, task_id)

                if user in locked_assignments_for_task:
                    continue

                if num_eligible > len(date_tasks):
                    self.prob += (
                        lpSum(self.x[(date_task, user)] for date_task in date_tasks)
                        <= 1
                    )
                else:
                    self.prob += (
                        lpSum(self.x[(date_task, user)] for date_task in date_tasks)
                        <= (len(date_tasks) + num_eligible - 1) / num_eligible
                    )
                    self.prob += (
                        lpSum(self.x[(date_task, user)] for date_task in date_tasks)
                        >= 1
                    )

    def constrain_total_assignments(self):
        for user in self.users:
            self.prob += (
                lpSum(
                    self.x[(date_task, user)]
                    for date_task in self.date_tasks
                    if self.is_eligible(user, date_task)
                )
                <= self.max_assignments
            )

    def constrain_provided_assignments(self):
        for date_task, user in self.locked_in_assignment_vars:
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

        for task_id, date_tasks in grouped_tasks.items():
            sorted_dates = sorted(
                date_tasks, key=lambda x: datetime.strptime(x.date, "%Y-%m-%d")
            )

            task_consec_pairs_dict[task_id] = [
                (sorted_dates[i], sorted_dates[i + 1])
                for i in range(len(sorted_dates) - 1)
            ]

        task_consec_pairs_dict = dict(task_consec_pairs_dict)

        locked_task_user_pairs = {
            (date_task.task_id, user)
            for date_task, user in self.locked_in_assignment_vars
        }

        for user in self.users:
            for task_id, consec_date_task_pairs in task_consec_pairs_dict.items():
                if (task_id, user) in locked_task_user_pairs:
                    continue

                if (
                    self.is_eligible(user, task_id)
                    and len(self.get_eligible(task_id)) >= 2
                ):
                    for i, (earlier_date_task, later_date_task) in enumerate(
                        consec_date_task_pairs
                    ):
                        if (
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
                    exclusions.add((task, exclusion))

        return exclusions

    def week_aligned_date_task_pairs(self, task1: Task, task2: Task):
        """Pairs of holes that fall in the same Sunday-start week.

        Weekly tasks are dated as the first service day of the week, so a
        Wednesday-only week has a weekly hole and no Sunday hole. Pairing by
        list index shifted those weekly holes onto the next Sunday. Pair by
        week instead.
        """
        by_week1 = {
            dt.week_sunday: dt
            for dt in self.filter_date_tasks_by_task(self.date_tasks, task1)
        }
        by_week2 = {
            dt.week_sunday: dt
            for dt in self.filter_date_tasks_by_task(self.date_tasks, task2)
        }
        pairs = []
        for week in by_week1.keys() & by_week2.keys():
            left, right = by_week1[week], by_week2[week]
            if left != right:
                pairs.append((left, right))
        return pairs

    def filter_date_tasks_by_task(
        self, date_tasks: list[DateTask], task_id_or_task: str | Task
    ) -> list[DateTask]:
        task_id = (
            task_id_or_task.id if isinstance(task_id_or_task, Task) else task_id_or_task
        )
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

    def is_eligible(self, user: User, task_id_or_date_task: str | DateTask | Task):
        if isinstance(task_id_or_date_task, str):
            return user in self.eligibility[task_id_or_date_task]
        elif isinstance(task_id_or_date_task, DateTask):
            return user in self.eligibility[task_id_or_date_task.task_id]
        elif isinstance(task_id_or_date_task, Task):
            return user in self.eligibility[task_id_or_date_task.id]
        raise TypeError(
            f"Expected str, DateTask, or Task, got {type(task_id_or_date_task)}"
        )

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
