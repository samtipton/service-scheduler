from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, tag

from schedules.models import Assignment, Schedule, Service, Task, TaskPreference
from schedules.services.compare_dump import dump_compare_db, load_compare_dump
from schedules.services.objectives import CatchUpShareObjective, FairJobsObjective
from schedules.services.year_compare import (
    DISPLAY_NAMES,
    MONTHS,
    load_compare_world,
    run_comparison,
    score_months,
    world_from_database,
)
from users.models import User


@tag("year")
class YearCompareTests(TestCase):
    """Generate a year with each objective and compare jobs vs fair share.

    Hard asserts: feasible months, filled cells, exclusions and consecutive-week
    hold. The table is recorded, not a pass/fail of one objective vs the other.
    """

    def test_twelve_months_both_objectives(self):
        text, scores, world = run_comparison(
            [CatchUpShareObjective.name, FairJobsObjective.name]
        )
        print("\n" + text)

        catch = scores[DISPLAY_NAMES[CatchUpShareObjective.name]]
        fair = scores[DISPLAY_NAMES[FairJobsObjective.name]]

        for name, score in (
            (CatchUpShareObjective.name, catch),
            (FairJobsObjective.name, fair),
        ):
            self.assertEqual(score["infeasible"], 0, name)
            self.assertEqual(score["unfilled"], 0, name)
            self.assertEqual(score["exclusion_violations"], 0, name)
            self.assertEqual(score["consecutive_violations"], 0, name)
            self.assertEqual(score["months"], MONTHS, name)

        self.assertGreaterEqual(
            fair["count_ut"].get((world.p2.pk, world.song.id), 0),
            fair["count_ut"].get((world.p05.pk, world.song.id), 0),
        )
        self.assertLessEqual(
            fair["count_u_month"].get(
                (world.new.pk, world.start.year, world.start.month), 0
            ),
            3,
        )


class ScoreMonthsTests(TestCase):
    def test_inactive_user_is_not_starved(self):
        world = load_compare_world()
        ghost = world.p05
        schedule = Schedule.objects.create(
            name="score-inactive",
            date=world.start,
            user=world.creator,
        )
        ghost.is_active = False
        ghost.save()
        starved_inactive = score_months([schedule])["starved"]
        ghost.is_active = True
        ghost.save()
        starved_active = score_months([schedule])["starved"]
        self.assertEqual(starved_active, starved_inactive + 1)


@tag("year")
class CompareDumpTests(TestCase):
    """Round-trip the postgres dump used by compare_objectives --dump."""

    def test_dump_load_starts_after_latest_assignment(self):
        world = load_compare_world()
        n_users = User.objects.count()
        n_tasks = Task.objects.count()
        n_prefs = TaskPreference.objects.count()
        n_asg = Assignment.objects.count()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "live.sql"
            dump_compare_db(path, months=12, today=date(2026, 10, 1))
            sql = path.read_text()
            Assignment.objects.all().delete()
            TaskPreference.objects.all().delete()
            Schedule.objects.all().delete()
            Task.objects.all().delete()
            Service.objects.all().delete()
            User.objects.all().delete()
            load_compare_dump(path)

        restored = world_from_database()
        self.assertEqual(User.objects.count(), n_users)
        self.assertEqual(Task.objects.count(), n_tasks)
        self.assertEqual(TaskPreference.objects.count(), n_prefs)
        self.assertEqual(Assignment.objects.count(), n_asg)
        self.assertEqual(restored.start, world.start)
        self.assertNotIn("pbkdf2", sql)
        self.assertNotIn("YearU0", sql)
        self.assertNotIn("test+", sql)
        for user in User.objects.all():
            self.assertEqual(user.first_name, "Person")
            self.assertEqual(user.email, f"person{user.pk}@example.com")
            self.assertEqual(user.password, "!")
