from collections import Counter
from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone
from pulp import LpMaximize, lpSum

from schedules.models import Assignment, Schedule, Service, Task, TaskPreference
from schedules.services.objectives import CatchUpShareObjective
from schedules.services.scheduler import DEFAULT_CONSTRAINT_NAMES, Scheduler
from users.models import User


TEST_EMAIL = "test+{slug}@example.com"


class PreferUserObjective:
    """Stub: maximize assignments for one user. Constraints still apply."""

    name = "PreferUserObjective"
    sense = LpMaximize

    def __init__(self, user):
        self.user = user

    def expression(self, x, ctx):
        return lpSum(
            x[(date_task, user)]
            for user in ctx.users
            for date_task in ctx.date_tasks
            if ctx.is_eligible(user, date_task) and user.pk == self.user.pk
        )


class SchedulerFixtureMixin:
    def _user(self, slug, first, last):
        return User.objects.create_user(
            email=TEST_EMAIL.format(slug=slug),
            first_name=first,
            last_name=last,
            password="x",
        )

    def _sunday_world(self, task_id="song_leader"):
        self.creator = self._user("creator", "Test", "Creator")
        self.service = Service.objects.create(
            name="Sunday AM", day_of_week=0, start_time=time(10, 0)
        )
        self.task = Task.objects.create(
            id=task_id, name="Song Leader", service=self.service, order=1
        )
        return self.service, self.task

    def _schedule(self, year, month, base=None):
        return Schedule.objects.create(
            name=f"test-{year}-{month}",
            date=date(year, month, 1),
            user=self.creator,
            base_schedule=base,
        )

    def _pref(self, user, task, value=1.0):
        return TaskPreference.objects.create(user=user, task=task, value=value)

    def _history(self, user, task, on, n=1):
        hist = self._schedule(on.year, on.month)
        for i in range(n):
            Assignment.objects.create(
                schedule=hist,
                task=task,
                user=user,
                assigned_at=timezone.make_aware(
                    datetime(on.year, on.month, on.day) + timedelta(hours=i)
                ),
            )


class DateTaskCalendarTests(SchedulerFixtureMixin, TestCase):
    def setUp(self):
        self.creator = self._user("creator", "Test", "Creator")
        self.sun = Service.objects.create(
            name="Sunday", day_of_week=0, start_time=time(9, 0)
        )
        self.wed = Service.objects.create(
            name="Wednesday", day_of_week=3, start_time=time(19, 0)
        )
        self.weekly = Service.objects.create(
            name="Weekly", day_of_week=None, start_time=time(0, 0)
        )
        self.t1 = Task.objects.create(
            id="cal_sun", name="Sun Task", service=self.sun, order=1
        )
        self.t2 = Task.objects.create(
            id="cal_wed", name="Wed Task", service=self.wed, order=2
        )
        self.t3 = Task.objects.create(
            id="cal_week", name="Week Task", service=self.weekly, order=3
        )
        self.alice = self._user("alice", "Alice", "Test")
        for task in (self.t1, self.t2, self.t3):
            self._pref(self.alice, task)

    def _date_task_ids(self, year, month):
        schedule = self._schedule(year, month)
        services = list(Service.objects.prefetch_related("tasks").all())
        scheduler = Scheduler(schedule, services)
        return set(str(dt) for dt in scheduler.date_tasks)

    def test_march_2025(self):
        date_tasks = self._date_task_ids(2025, 3)
        self.assertEqual(len(date_tasks), 14)
        self.assertIn("2025-3-2-cal_sun", date_tasks)
        self.assertIn("2025-3-30-cal_sun", date_tasks)
        self.assertIn("2025-3-5-cal_wed", date_tasks)
        self.assertIn("2025-3-26-cal_wed", date_tasks)
        self.assertNotIn("2025-3-2-cal_wed", date_tasks)
        self.assertIn("2025-3-2-cal_week", date_tasks)
        self.assertIn("2025-3-30-cal_week", date_tasks)

    def test_april_2025(self):
        date_tasks = self._date_task_ids(2025, 4)
        self.assertEqual(len(date_tasks), 14)
        self.assertIn("2025-4-6-cal_sun", date_tasks)
        self.assertIn("2025-4-2-cal_wed", date_tasks)
        self.assertIn("2025-4-30-cal_wed", date_tasks)
        self.assertIn("2025-4-2-cal_week", date_tasks)

    def test_may_2025(self):
        date_tasks = self._date_task_ids(2025, 5)
        self.assertEqual(len(date_tasks), 12)
        self.assertIn("2025-5-4-cal_sun", date_tasks)
        self.assertIn("2025-5-25-cal_sun", date_tasks)
        self.assertIn("2025-5-7-cal_wed", date_tasks)
        self.assertIn("2025-5-4-cal_week", date_tasks)


class RealSolveTests(SchedulerFixtureMixin, TestCase):
    def test_catch_up_gives_extra_slot_to_most_behind(self):
        self._sunday_world()
        alice = self._user("alice", "Alice", "Test")
        bob = self._user("bob", "Bob", "Test")
        carol = self._user("carol", "Carol", "Test")
        for user in (alice, bob, carol):
            self._pref(user, self.task)
        self._history(alice, self.task, date(2025, 4, 6), n=10)
        self._history(bob, self.task, date(2025, 4, 13), n=8)
        self._history(carol, self.task, date(2025, 4, 20), n=2)

        schedule = self._schedule(2025, 5)
        services = list(Service.objects.prefetch_related("tasks", "tasks__excludes"))
        result, assignments = Scheduler(schedule, services).solve()
        self.assertNotEqual(result, -1)
        self.assertEqual(len(assignments), 4)
        counts = Counter(assignments.values())
        self.assertEqual(counts["Test, Carol"], 2)
        self.assertEqual(counts["Test, Alice"], 1)
        self.assertEqual(counts["Test, Bob"], 1)

    def test_stub_objective_prefers_named_user(self):
        self._sunday_world()
        alice = self._user("alice", "Alice", "Test")
        bob = self._user("bob", "Bob", "Test")
        carol = self._user("carol", "Carol", "Test")
        for user in (alice, bob, carol):
            self._pref(user, self.task)

        schedule = self._schedule(2025, 5)
        services = list(Service.objects.prefetch_related("tasks", "tasks__excludes"))
        result, assignments = Scheduler(
            schedule, services, objective=PreferUserObjective(alice)
        ).solve()
        self.assertNotEqual(result, -1)
        counts = Counter(assignments.values())
        self.assertEqual(counts["Test, Alice"], 2)
        self.assertEqual(counts["Test, Bob"], 1)
        self.assertEqual(counts["Test, Carol"], 1)

    def test_abundance_at_most_one_each(self):
        self._sunday_world()
        people = [
            self._user(f"u{i}", f"User{i}", "Test") for i in range(8)
        ]
        for user in people:
            self._pref(user, self.task)

        schedule = self._schedule(2025, 5)
        services = list(Service.objects.prefetch_related("tasks", "tasks__excludes"))
        result, assignments = Scheduler(schedule, services).solve()
        self.assertNotEqual(result, -1)
        self.assertEqual(len(assignments), 4)
        counts = Counter(assignments.values())
        self.assertEqual(len(counts), 4)
        self.assertTrue(all(n == 1 for n in counts.values()))

    def test_history_from_assignment_not_stats(self):
        self._sunday_world()
        alice = self._user("alice", "Alice", "Test")
        self._pref(alice, self.task)
        self._history(alice, self.task, date(2025, 4, 6), n=3)
        schedule = self._schedule(2025, 5)
        services = list(Service.objects.prefetch_related("tasks", "tasks__excludes"))
        scheduler = Scheduler(schedule, services)
        dt = scheduler.date_tasks[0]
        self.assertEqual(scheduler.assignment_counts[(alice.pk, self.task.id)], 3)
        self.assertEqual(scheduler.get_actual_average(alice, dt), 1.0)
        self.assertEqual(scheduler.get_ideal_average(alice, dt), 1.0)

    def test_constraint_names_can_drop_a_rule(self):
        names = tuple(n for n in DEFAULT_CONSTRAINT_NAMES if n != "total_assignments")
        self._sunday_world()
        alice = self._user("alice", "Alice", "Test")
        self._pref(alice, self.task)
        schedule = self._schedule(2025, 5)
        services = list(Service.objects.prefetch_related("tasks", "tasks__excludes"))
        scheduler = Scheduler(schedule, services, constraint_names=names)
        self.assertEqual(scheduler.constraint_names, names)

    def test_unknown_constraint_name_raises(self):
        self._sunday_world()
        alice = self._user("alice", "Alice", "Test")
        self._pref(alice, self.task)
        schedule = self._schedule(2025, 5)
        services = list(Service.objects.prefetch_related("tasks", "tasks__excludes"))
        with self.assertRaises(ValueError):
            Scheduler(schedule, services, constraint_names=("not_a_rule",))
