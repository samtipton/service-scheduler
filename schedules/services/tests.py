import importlib
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

from django.apps import apps
from django.test import TestCase
from django.utils import timezone
from pulp import LpMaximize, lpSum

from schedules.models import (
    Assignment,
    Schedule,
    Service,
    Task,
    TaskPreference,
    TaskRequires,
)
from schedules.services.datetask import DateTask
from schedules.services.fairness import build_fairness_window
from schedules.services.objectives import (
    CatchUpShareObjective,
    FairJobsObjective,
    adjacent_rotation_week_pairs,
)
from schedules.services.scheduler import DEFAULT_CONSTRAINT_NAMES, Scheduler
from users.models import User

JOINED = timezone.make_aware(datetime(2020, 1, 1))
_rotation_migration = importlib.import_module(
    "schedules.migrations.0005_task_rotation_group"
)
ROTATION_FAMILIES = _rotation_migration.ROTATION_FAMILIES
set_rotation_groups = _rotation_migration.set_rotation_groups


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
    def _user(self, slug, first, last, joined=None):
        user = User.objects.create_user(
            email=TEST_EMAIL.format(slug=slug),
            first_name=first,
            last_name=last,
            password="x",
        )
        if joined is not None:
            User.objects.filter(pk=user.pk).update(date_joined=joined)
            user.refresh_from_db()
        return user

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

    def test_weekly_pairs_with_sunday_of_same_week(self):
        """April 2025 starts Tuesday: extra Wed-only weekly hole must not
        zip onto the first Sunday."""
        schedule = self._schedule(2025, 4)
        services = list(Service.objects.prefetch_related("tasks").all())
        scheduler = Scheduler(schedule, services)
        pairs = scheduler.week_aligned_date_task_pairs(self.t1, self.t3)
        pair_dates = {(a.date, b.date) for a, b in pairs}
        self.assertEqual(
            pair_dates,
            {
                ("2025-4-6", "2025-4-6"),
                ("2025-4-13", "2025-4-13"),
                ("2025-4-20", "2025-4-20"),
                ("2025-4-27", "2025-4-27"),
            },
        )
        wed_pairs = scheduler.week_aligned_date_task_pairs(self.t1, self.t2)
        wed_dates = {(a.date, b.date) for a, b in wed_pairs}
        self.assertEqual(
            wed_dates,
            {
                ("2025-4-6", "2025-4-9"),
                ("2025-4-13", "2025-4-16"),
                ("2025-4-20", "2025-4-23"),
                ("2025-4-27", "2025-4-30"),
            },
        )

    def test_next_week_sound_board_and_opening_prayer_share_sunday(self):
        """April 2025: week 1 is Wednesday-only (sound board Apr 2). The next
        week sound board is dated Sunday Apr 6, same day as opening prayer.
        Index-zip paired prayer Apr 6 with sound board Apr 2 instead.
        """
        prayer = Task.objects.create(
            id="opening_prayer", name="Opening Prayer", service=self.sun, order=10
        )
        booth = Task.objects.create(
            id="sound_board_operator",
            name="Sound Board",
            service=self.weekly,
            order=11,
        )
        self._pref(self.alice, prayer)
        self._pref(self.alice, booth)
        schedule = self._schedule(2025, 4)
        services = list(Service.objects.prefetch_related("tasks").all())
        scheduler = Scheduler(schedule, services)
        booth_dates = [dt.date for dt in scheduler.filter_date_tasks_by_task(
            scheduler.date_tasks, booth
        )]
        prayer_dates = [dt.date for dt in scheduler.filter_date_tasks_by_task(
            scheduler.date_tasks, prayer
        )]
        self.assertEqual(booth_dates[0], "2025-4-2")
        self.assertEqual(booth_dates[1], "2025-4-6")
        self.assertEqual(prayer_dates[0], "2025-4-6")
        pairs = scheduler.week_aligned_date_task_pairs(prayer, booth)
        pair_dates = {(a.date, b.date) for a, b in pairs}
        self.assertIn(("2025-4-6", "2025-4-6"), pair_dates)
        self.assertNotIn(("2025-4-6", "2025-4-2"), pair_dates)
        self.assertNotIn(("2025-4-2", "2025-4-6"), pair_dates)


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
        result, assignments = Scheduler(
            schedule, services, objective=CatchUpShareObjective()
        ).solve()
        self.assertNotEqual(result, -1)
        self.assertEqual(len(assignments), 4)
        counts = Counter(assignments.values())
        self.assertEqual(counts["Test, Carol"], 2)
        self.assertEqual(counts["Test, Alice"], 1)
        self.assertEqual(counts["Test, Bob"], 1)

    def test_exclusion_blocks_weekly_and_sunday_same_week(self):
        """Prefer Alice for both; she must not hold Sunday + weekly that week."""
        self.creator = self._user("creator", "Test", "Creator")
        sun = Service.objects.create(
            name="Sunday", day_of_week=0, start_time=time(9, 0)
        )
        weekly = Service.objects.create(
            name="Weekly", day_of_week=None, start_time=time(0, 0)
        )
        prayer = Task.objects.create(
            id="ex_prayer", name="Prayer", service=sun, order=1
        )
        security = Task.objects.create(
            id="ex_security", name="Security", service=weekly, order=2
        )
        prayer.excludes.add(security)
        security.excludes.add(prayer)
        alice = self._user("alice", "Alice", "Test")
        bob = self._user("bob", "Bob", "Test")
        carol = self._user("carol", "Carol", "Test")
        for user in (alice, bob, carol):
            self._pref(user, prayer)
            self._pref(user, security)

        schedule = self._schedule(2025, 4)
        services = list(Service.objects.prefetch_related("tasks", "tasks__excludes"))
        result, assignments = Scheduler(
            schedule, services, objective=PreferUserObjective(alice)
        ).solve()
        self.assertNotEqual(result, -1)
        alice_name = alice.inverted_name()
        alice_days = defaultdict(set)
        for date_task_str, name in assignments.items():
            if name != alice_name:
                continue
            date_str, task_id = date_task_str.rsplit("-", 1)
            year, month, day = (int(p) for p in date_str.split("-"))
            week = date(year, month, day) - timedelta(
                days=(date(year, month, day).weekday() + 1) % 7
            )
            alice_days[week].add(task_id)
        for week, task_ids in alice_days.items():
            self.assertFalse(
                {"ex_prayer", "ex_security"} <= task_ids,
                f"Alice held both on week of {week}: {task_ids}",
            )

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


class FairJobsTests(SchedulerFixtureMixin, TestCase):
    def _people(self, n):
        return [
            self._user(f"u{i}", f"User{i}", "Test", joined=JOINED) for i in range(n)
        ]

    def _services(self):
        return list(Service.objects.prefetch_related("tasks", "tasks__excludes"))

    def test_abundance_four_distinct_people(self):
        self._sunday_world()
        people = self._people(8)
        for user in people:
            self._pref(user, self.task)
        schedule = self._schedule(2025, 5)
        result, assignments = Scheduler(
            schedule, self._services(), objective=FairJobsObjective()
        ).solve()
        self.assertNotEqual(result, -1)
        self.assertEqual(len(assignments), 4)
        counts = Counter(assignments.values())
        self.assertEqual(len(counts), 4)
        self.assertTrue(all(n == 1 for n in counts.values()))

    def test_behind_on_six_tasks_does_not_get_six_jobs(self):
        self._sunday_world()
        people = self._people(8)
        tasks = [self.task]
        for i in range(5):
            tasks.append(
                Task.objects.create(
                    id=f"t{i}", name=f"Task {i}", service=self.service, order=i + 2
                )
            )
        for user in people:
            for task in tasks:
                self._pref(user, task)
        bob = people[0]
        for other in people[1:]:
            for task in tasks:
                self._history(other, task, date(2025, 4, 6), n=4)

        schedule = self._schedule(2025, 5)
        result, assignments = Scheduler(
            schedule, self._services(), objective=FairJobsObjective()
        ).solve()
        self.assertNotEqual(result, -1)
        bob_jobs = sum(1 for name in assignments.values() if name == bob.inverted_name())
        self.assertLess(bob_jobs, 6)
        self.assertGreater(bob_jobs, 0)

    def test_p2_ranks_ahead_of_p1_when_both_even(self):
        self._sunday_world()
        people = self._people(8)
        self._pref(people[0], self.task, value=2.0)
        for user in people[1:]:
            self._pref(user, self.task, value=1.0)
        schedule = self._schedule(2025, 5)
        window = build_fairness_window(schedule, self._services(), people)
        keys = [window.ranking_key(u.pk, self.task.id) for u in people]
        self.assertLess(keys[0], min(keys[1:]))

        result, assignments = Scheduler(
            schedule, self._services(), objective=FairJobsObjective()
        ).solve()
        self.assertNotEqual(result, -1)
        self.assertIn(people[0].inverted_name(), assignments.values())

    def test_new_person_virtual_count_is_near_even(self):
        self._sunday_world()
        people = self._people(8)
        for user in people:
            self._pref(user, self.task)
        veterans = people[1:]
        for user in veterans:
            self._history(user, self.task, date(2025, 4, 6), n=5)
        bob = people[0]
        schedule = self._schedule(2025, 5)
        window = build_fairness_window(schedule, self._services(), people + [self.creator])
        key = window.ranking_key(bob.pk, self.task.id)
        raw_behind = 0 - window.target[(bob.pk, self.task.id)]
        self.assertGreater(key, raw_behind)
        self.assertLess(abs(key), abs(raw_behind) / 2)


class RotationGroupTests(SchedulerFixtureMixin, TestCase):
    """Song-leader family: same rotation_group, adjacent Sunday-start weeks."""

    def _family(self, group="song"):
        self.creator = self._user("creator", "Test", "Creator")
        self.sun = Service.objects.create(
            name="Sunday", day_of_week=0, start_time=time(9, 0)
        )
        self.wed = Service.objects.create(
            name="Wednesday", day_of_week=3, start_time=time(19, 0)
        )
        self.sun_task = Task.objects.create(
            id="rg_sun_song",
            name="Sun Song",
            service=self.sun,
            order=1,
            rotation_group=group,
        )
        self.wed_task = Task.objects.create(
            id="rg_wed_song",
            name="Wed Song",
            service=self.wed,
            order=2,
            rotation_group=group,
        )
        self.sun_task.excludes.add(self.wed_task)
        return self.sun_task, self.wed_task

    def _people_on_family(self, n=3):
        people = [
            self._user(f"rg{i}", f"User{i}", "Rot", joined=JOINED) for i in range(n)
        ]
        for user in people:
            self._pref(user, self.sun_task)
            self._pref(user, self.wed_task)
        return people

    def _services(self):
        return list(Service.objects.prefetch_related("tasks", "tasks__excludes"))

    def _adjacent_hits(self, assignments):
        by_user = defaultdict(list)
        for date_task_str, name in assignments.items():
            by_user[name].append(DateTask.from_str(date_task_str))
        return sum(
            len(adjacent_rotation_week_pairs(dts)) for dts in by_user.values()
        )

    def test_pairs_wednesday_with_next_sunday(self):
        self._family()
        schedule = self._schedule(2025, 4)
        scheduler = Scheduler(schedule, self._services())
        pairs = adjacent_rotation_week_pairs(scheduler.date_tasks)
        self.assertEqual(len(pairs), 4)
        first_group, week_a, week_b = pairs[0]
        self.assertEqual(first_group, "song")
        self.assertEqual({dt.date for dt in week_a}, {"2025-4-2"})
        self.assertEqual({dt.date for dt in week_b}, {"2025-4-6", "2025-4-9"})

    def test_pairs_month_boundary_wednesday_to_next_sunday(self):
        self._family()
        jan28 = DateTask("2026-1-28", self.wed_task)
        feb1 = DateTask("2026-2-1", self.sun_task)
        pairs = adjacent_rotation_week_pairs([jan28, feb1])
        self.assertEqual(len(pairs), 1)
        group, week_a, week_b = pairs[0]
        self.assertEqual(group, "song")
        self.assertEqual({dt.date for dt in week_a}, {"2026-1-28"})
        self.assertEqual({dt.date for dt in week_b}, {"2026-2-1"})

    def test_blank_group_is_not_paired(self):
        self._family(group="")
        schedule = self._schedule(2025, 4)
        scheduler = Scheduler(schedule, self._services())
        self.assertEqual(adjacent_rotation_week_pairs(scheduler.date_tasks), [])

    def test_different_groups_are_not_paired_together(self):
        self._family()
        self.wed_task.rotation_group = "other"
        self.wed_task.save()
        schedule = self._schedule(2025, 4)
        scheduler = Scheduler(schedule, self._services())
        for group, week_a, week_b in adjacent_rotation_week_pairs(scheduler.date_tasks):
            ids = {dt.task_id for dt in week_a + week_b}
            self.assertFalse(
                {"rg_sun_song", "rg_wed_song"} <= ids,
                f"mixed family pair in {group}: {ids}",
            )

    def test_prefer_user_takes_adjacent_family_weeks(self):
        """Without the FairJobs penalty, packing Alice to 4 jobs needs a spill."""
        self._family()
        alice, *_ = self._people_on_family(3)
        schedule = self._schedule(2025, 4)
        result, assignments = Scheduler(
            schedule, self._services(), objective=PreferUserObjective(alice)
        ).solve()
        self.assertNotEqual(result, -1)
        alice_jobs = sum(
            1 for name in assignments.values() if name == alice.inverted_name()
        )
        self.assertGreaterEqual(alice_jobs, 4)
        self.assertGreater(self._adjacent_hits(assignments), 0)

    def test_fairjobs_high_weight_avoids_adjacent_family_weeks(self):
        self._family()
        self._people_on_family(4)
        schedule = self._schedule(2025, 4)
        result, assignments = Scheduler(
            schedule,
            self._services(),
            objective=FairJobsObjective(rotation_weight=50),
        ).solve()
        self.assertNotEqual(result, -1)
        self.assertEqual(len(assignments), 9)
        self.assertEqual(self._adjacent_hits(assignments), 0)

    def test_month_boundary_locked_wednesday_blocks_next_sunday(self):
        self._family()
        alice, *_ = self._people_on_family(4)
        jan = self._schedule(2026, 1)
        Assignment.objects.create(
            schedule=jan,
            task=self.wed_task,
            user=alice,
            assigned_at=timezone.make_aware(datetime(2026, 1, 28)),
        )
        feb = self._schedule(2026, 2, base=jan)
        result, assignments = Scheduler(
            feb,
            self._services(),
            objective=FairJobsObjective(rotation_weight=50),
        ).solve()
        self.assertNotEqual(result, -1)
        alice_name = alice.inverted_name()
        self.assertNotEqual(assignments.get("2026-2-1-rg_sun_song"), alice_name)
        self.assertNotEqual(assignments.get("2026-2-4-rg_wed_song"), alice_name)
        self.assertEqual(self._adjacent_hits(assignments), 0)

    def test_known_ids_get_family_labels(self):
        self.creator = self._user("creator", "Test", "Creator")
        service = Service.objects.create(
            name="Sunday", day_of_week=0, start_time=time(9, 0)
        )
        for ids in ROTATION_FAMILIES.values():
            for task_id in ids:
                Task.objects.create(
                    id=task_id, name=task_id, service=service, order=1
                )
        set_rotation_groups(apps, None)
        for group, ids in ROTATION_FAMILIES.items():
            for task_id in ids:
                self.assertEqual(
                    Task.objects.get(pk=task_id).rotation_group, group, task_id
                )


class TaskRequiresTests(SchedulerFixtureMixin, TestCase):
    """Person-specific: if assigned task, also assign requires the same week."""

    def _world(self):
        self.creator = self._user("creator", "Test", "Creator")
        self.sun = Service.objects.create(
            name="Sunday", day_of_week=0, start_time=time(9, 0)
        )
        self.security = Task.objects.create(
            id="rq_security", name="Security", service=self.sun, order=1
        )
        self.usher = Task.objects.create(
            id="rq_usher", name="Usher", service=self.sun, order=2
        )
        self.security.excludes.add(self.usher)
        return self.security, self.usher

    def _services(self):
        return list(Service.objects.prefetch_related("tasks", "tasks__excludes"))

    def _week_pairs(self, assignments, name):
        by_week = defaultdict(set)
        for date_task_str, assigned in assignments.items():
            if assigned != name:
                continue
            date_str, task_id = date_task_str.rsplit("-", 1)
            year, month, day = (int(p) for p in date_str.split("-"))
            on = date(year, month, day)
            week = on - timedelta(days=(on.weekday() + 1) % 7)
            by_week[week].add(task_id)
        return by_week

    def test_requires_takes_usher_with_security(self):
        self._world()
        alice = self._user("alice", "Alice", "Test", joined=JOINED)
        bob = self._user("bob", "Bob", "Test", joined=JOINED)
        carol = self._user("carol", "Carol", "Test", joined=JOINED)
        for user in (alice, bob, carol):
            self._pref(user, self.security)
            self._pref(user, self.usher)
        TaskRequires.objects.create(
            user=alice, task=self.security, requires=self.usher
        )
        schedule = self._schedule(2025, 4)
        result, assignments = Scheduler(
            schedule, self._services(), objective=PreferUserObjective(alice)
        ).solve()
        self.assertNotEqual(result, -1)
        alice_weeks = self._week_pairs(assignments, alice.inverted_name())
        security_weeks = [w for w, ids in alice_weeks.items() if "rq_security" in ids]
        self.assertGreater(len(security_weeks), 0)
        for week in security_weeks:
            self.assertIn("rq_usher", alice_weeks[week])

    def test_other_person_still_cannot_hold_both(self):
        self._world()
        alice = self._user("alice", "Alice", "Test", joined=JOINED)
        bob = self._user("bob", "Bob", "Test", joined=JOINED)
        carol = self._user("carol", "Carol", "Test", joined=JOINED)
        for user in (alice, bob, carol):
            self._pref(user, self.security)
            self._pref(user, self.usher)
        TaskRequires.objects.create(
            user=alice, task=self.security, requires=self.usher
        )
        schedule = self._schedule(2025, 4)
        result, assignments = Scheduler(
            schedule, self._services(), objective=PreferUserObjective(bob)
        ).solve()
        self.assertNotEqual(result, -1)
        bob_weeks = self._week_pairs(assignments, bob.inverted_name())
        for week, ids in bob_weeks.items():
            self.assertFalse(
                {"rq_security", "rq_usher"} <= ids,
                f"Bob held both on week of {week}: {ids}",
            )

    def test_usher_without_security_is_allowed(self):
        self._world()
        alice = self._user("alice", "Alice", "Test", joined=JOINED)
        bob = self._user("bob", "Bob", "Test", joined=JOINED)
        carol = self._user("carol", "Carol", "Test", joined=JOINED)
        for user in (alice, bob, carol):
            self._pref(user, self.security)
            self._pref(user, self.usher)
        TaskRequires.objects.create(
            user=alice, task=self.security, requires=self.usher
        )
        schedule = self._schedule(2025, 4)
        result, assignments = Scheduler(
            schedule,
            self._services(),
            locked_in_assignments={
                "2025-4-6-rq_usher": alice.inverted_name(),
                "2025-4-6-rq_security": bob.inverted_name(),
            },
            objective=PreferUserObjective(bob),
        ).solve()
        self.assertNotEqual(result, -1)
        self.assertEqual(assignments.get("2025-4-6-rq_usher"), alice.inverted_name())
        self.assertEqual(assignments.get("2025-4-6-rq_security"), bob.inverted_name())
