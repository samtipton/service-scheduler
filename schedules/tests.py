import datetime
from datetime import time
from decimal import Decimal
from django.db import IntegrityError
from django.db.models import Count
from django.forms import ValidationError
from django.test import TestCase
from django.utils import timezone
from core import models
from schedules.models import (
    AssignmentStats,
    Schedule,
    Service,
    Task,
    TaskPreference,
    Assignment,
)
from users.models import User


class ServiceTestCase(TestCase):
    def setUp(self):
        self.service = Service.objects.create(
            name="Test Service", day_of_week=0, start_time=time(9, 0)
        )

    def test_str(self):
        self.assertEqual(str(self.service), "Test Service on day 0 at 09:00:00")

    def test_min_value_validator(self):
        with self.assertRaises(ValidationError):
            service = Service.objects.create(
                name="Test Service", day_of_week=-1, start_time=time(9, 0)
            )
            service.full_clean()

    def test_max_value_validator(self):
        with self.assertRaises(ValidationError):
            service = Service.objects.create(
                name="Test Service", day_of_week=7, start_time=time(9, 0)
            )
            service.full_clean()


class TaskTestCase(TestCase):
    def setUp(self):
        self.service = Service.objects.create(
            name="Test Service", day_of_week=0, start_time=time(9, 0)
        )

        self.task1 = Task.objects.create(
            name="Test Task 1",
            id="test_task_id_1",
            description="Test Description",
            service=self.service,
            time_period=Task.SUNDAY,
        )

        self.task2 = Task.objects.create(
            name="Test Task 2",
            id="test_task_id_2",
            description="Test Description",
            service=self.service,
            time_period=Task.SUNDAY,
        )

    def test_filter_by_id(self):
        self.assertEqual(Task.objects.filter(pk="test_task_id_1").first(), self.task1)
        self.assertEqual(Task.objects.filter(pk="test_task_id_2").first(), self.task2)

    def test_primary_key_is_name(self):
        self.assertEqual(self.task1.pk, "test_task_id_1")
        self.assertEqual(self.task2.pk, "test_task_id_2")

    def test_time_period_choices(self):
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.SUNDAY], "Sunday")
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.MONDAY], "Monday")
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.TUESDAY], "Tuesday")
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.WEDNESDAY], "Wednesday")
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.THURSDAY], "Thursday")
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.FRIDAY], "Friday")
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.SATURDAY], "Saturday")
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.WEEKLY], "Weekly")
        self.assertEqual(Task.TIME_PERIOD_CHOICES[Task.MONTHLY], "Monthly")

    def test_excludes_self_on_save(self):
        self.assertEqual(self.task1.excludes.count(), 1)
        self.assertEqual(self.task1.excludes.first(), self.task1)
        self.assertTrue(self.task1.is_excluded(self.task1))

    def test_excludes_other(self):
        self.task1.excludes.add(self.task2)

        self.assertTrue(self.task1.is_excluded(self.task2))

    def test_manager_excludes_other(self):
        self.task1.excludes.add(self.task2)

        self.assertTrue(self.task1.is_excluded(self.task2))
        self.assertTrue(Task.objects.is_excluded(self.task1.id, self.task2.id))
        self.assertTrue(Task.objects.is_excluded(self.task2.id, self.task1.id))

    def test_unique_together(self):
        with self.assertRaises(IntegrityError):
            Task.objects.create(
                name="Test Task", id="test_task_id", service=self.service
            )
            Task.objects.create(
                name="Test Task", id="test_task_id", service=self.service
            )

    def test_str(self):
        self.assertEqual(str(self.task1), "test_task_id_1")


class AssignmentTestCase(TestCase):
    def setUp(self):
        self.service = Service.objects.create(
            name="Test Service", day_of_week=0, start_time=time(9, 0)
        )

        self.task1 = Task.objects.create(
            name="Test Task 1",
            id="test_task_id_1",
            description="Test Description",
            service=self.service,
        )

        self.task2 = Task.objects.create(
            name="Test Task 2",
            id="test_task_id_2",
            description="Test Description",
            service=self.service,
        )

        self.user = User.objects.create_user(
            email="testuser@example.com",
            first_name="Test",
            last_name="User",
            password="testpassword",
        )

    def test_assignment_creation(self):
        assignment = Assignment.objects.create(
            user=self.user,
            task=self.task1,
            assigned_at=timezone.now(),
        )
        self.assertEqual(assignment.user, self.user)
        self.assertIsNotNone(assignment.assigned_at)

    def test_ordering(self):
        assignment1 = Assignment.objects.create(
            user=self.user,
            task=self.task1,
            assigned_at=timezone.now(),
        )
        assignment2 = Assignment.objects.create(
            user=self.user,
            task=self.task2,
            assigned_at=timezone.now() + datetime.timedelta(hours=1),
        )
        assignments = Assignment.objects.all()
        self.assertEqual(assignments[0], assignment2)
        self.assertEqual(assignments[1], assignment1)

    def test_str(self):
        now = timezone.now()
        assignment = Assignment.objects.create(
            user=self.user,
            task=self.task1,
            assigned_at=now,
        )
        self.assertEqual(
            str(assignment),
            f"{now.strftime('%Y-%m-%d %H:%M')}-test_task_id_1 -> Test User",
        )


class TaskPreferenceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com",
            first_name="Test",
            last_name="User",
            password="testpassword",
        )
        self.service = Service.objects.create(
            name="Test Service", day_of_week=0, start_time=time(9, 0)
        )
        self.task = Task.objects.create(
            name="Test Task",
            id="test_task_id",
            description="Test Description",
            service=self.service,
        )

    def test_task_preference_creation(self):
        TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        task_preference = TaskPreference.objects.get(user=self.user, task=self.task)
        self.assertEqual(task_preference.value, 1.0)
        self.assertEqual(task_preference.user, self.user)
        self.assertEqual(task_preference.task, self.task)
        self.assertIsNotNone(task_preference.updated_at)

    def test_is_eligible(self):
        TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        other_task = Task.objects.create(
            name="Other Task", id="other_task_id", service=self.service
        )
        self.assertTrue(TaskPreference.objects.is_eligible(self.user, self.task))
        self.assertFalse(TaskPreference.objects.is_eligible(self.user, other_task))

    def test_unique_together(self):
        TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        with self.assertRaises(IntegrityError):
            TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)

    def test_ordering(self):
        other_task = Task.objects.create(
            name="Other Task", id="other_task_id", service=self.service
        )
        TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        pref2 = TaskPreference.objects.create(
            user=self.user, task=other_task, value=2.0
        )

        # Manually adjust the `updated_at` timestamp
        TaskPreference.objects.filter(id=pref2.id).update(
            updated_at=timezone.now() + datetime.timedelta(days=1)
        )

        all_preferences = TaskPreference.objects.all()
        self.assertEqual(TaskPreference.objects.all().count(), 2)
        self.assertEqual(all_preferences[0].value, 2.0)
        self.assertEqual(all_preferences[1].value, 1.0)

    def test_str(self):
        task_preference = TaskPreference.objects.create(
            user=self.user, task=self.task, value=1.0
        )
        self.assertEqual(str(task_preference), f"{self.task.id}")


class UserEligibleTasksTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com",
            first_name="Test",
            last_name="User",
            password="testpassword",
        )
        self.service = Service.objects.create(
            name="Test Service", day_of_week=0, start_time=time(9, 0)
        )
        self.task1 = Task.objects.create(
            name="Test Task 1",
            id="test_task_id_1",
            description="Test Description",
            service=self.service,
        )
        self.task2 = Task.objects.create(
            name="Test Task 2",
            id="test_task_id_2",
            description="Test Description",
            service=self.service,
        )
        self.task3 = Task.objects.create(
            name="Test Task 3",
            id="test_task_id_3",
            description="Test Description",
            service=self.service,
        )

    def test_eligible_tasks_with_preferences(self):
        # Create preferences for tasks 1 and 2
        TaskPreference.objects.create(user=self.user, task=self.task1, value=1.0)
        TaskPreference.objects.create(user=self.user, task=self.task2, value=0.5)
        # Create preference with 0 value for task 3
        TaskPreference.objects.create(user=self.user, task=self.task3, value=0.0)

        eligible_tasks = self.user.eligible_tasks
        self.assertEqual(eligible_tasks.count(), 2)
        self.assertIn(self.task1, eligible_tasks)
        self.assertIn(self.task2, eligible_tasks)
        self.assertNotIn(self.task3, eligible_tasks)

    def test_eligible_tasks_no_preferences(self):
        eligible_tasks = self.user.eligible_tasks
        self.assertEqual(eligible_tasks.count(), 0)


class TaskEligibleUsersTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            first_name="User",
            last_name="One",
            password="testpassword",
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            first_name="User",
            last_name="Two",
            password="testpassword",
        )
        self.user3 = User.objects.create_user(
            email="user3@example.com",
            first_name="User",
            last_name="Three",
            password="testpassword",
        )
        self.service = Service.objects.create(
            name="Test Service", day_of_week=0, start_time=time(9, 0)
        )
        self.task = Task.objects.create(
            name="Test Task",
            id="test_task_id",
            description="Test Description",
            service=self.service,
        )

        self.task1 = Task.objects.create(
            name="Test Task 1",
            id="test_task_id_1",
            description="Test Description",
            service=self.service,
        )

        self.task_preference1 = TaskPreference.objects.create(
            user=self.user1, task=self.task, value=1.0
        )
        self.task_preference2 = TaskPreference.objects.create(
            user=self.user2, task=self.task, value=1.0
        )
        self.task_preference3 = TaskPreference.objects.create(
            user=self.user3, task=self.task, value=0.0
        )

    def test_eligible_users(self):
        eligible_users = self.task.get_eligible_users()
        self.assertEqual(eligible_users.count(), 2)
        self.assertIn(self.user1, eligible_users)
        self.assertIn(self.user2, eligible_users)
        self.assertNotIn(self.user3, eligible_users)

    def test_eligible_users_no_preferences(self):
        eligible_users = self.task1.get_eligible_users()
        self.assertEqual(eligible_users.count(), 0)


class AssignmentStatsTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            first_name="User",
            last_name="One",
            password="testpassword",
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            first_name="User",
            last_name="Two",
            password="testpassword",
        )
        self.service = Service.objects.create(
            name="Test Service", day_of_week=0, start_time=time(9, 0)
        )
        self.task = Task.objects.create(
            name="Test Task",
            id="test_task_id",
            description="Test Description",
            service=self.service,
        )
        # Create preferences for both users
        TaskPreference.objects.create(user=self.user1, task=self.task, value=1.0)
        TaskPreference.objects.create(user=self.user2, task=self.task, value=1.0)

    def test_calculate_ideal_average(self):
        stats = AssignmentStats.objects.create(
            user=self.user1, task=self.task, ideal_average=Decimal("0.5")
        )
        self.assertAlmostEqual(
            stats.calculate_ideal_average(), Decimal("0.5"), places=8
        )  # 1/2 eligible users

    def test_calculate_actual_average(self):
        # Create some assignments
        Assignment.objects.create(
            user=self.user1, task=self.task, assigned_at=timezone.now()
        )
        Assignment.objects.create(
            user=self.user1, task=self.task, assigned_at=timezone.now()
        )
        Assignment.objects.create(
            user=self.user2, task=self.task, assigned_at=timezone.now()
        )

        stats = AssignmentStats.objects.create(
            user=self.user1, task=self.task, ideal_average=Decimal("0.5")
        )
        self.assertAlmostEqual(
            stats.calculate_actual_average(), Decimal("0.66666667"), places=8
        )

    def test_calculate_assignment_delta(self):
        """Test assignment delta calculation"""
        # Create stats with different actual and ideal averages
        stats = AssignmentStats.objects.create(
            user=self.user1,
            task=self.task,
            actual_average=Decimal(0.3),
            ideal_average=Decimal(0.5),
        )
        self.assertAlmostEqual(
            stats.calculate_assignment_delta(), Decimal(-0.4), places=8
        )

        # Test with equal actual and ideal
        stats.actual_average = Decimal("0.5")
        stats.save()
        self.assertAlmostEqual(
            stats.calculate_assignment_delta(), Decimal(0.0), places=8
        )

        # Test with actual higher than ideal
        stats.actual_average = Decimal("0.7")
        stats.save()
        self.assertAlmostEqual(
            stats.calculate_assignment_delta(), Decimal(0.4), places=8
        )

    def test_update_stats(self):
        """Test updating assignment statistics"""
        # Create some assignments
        Assignment.objects.create(
            user=self.user1, task=self.task, assigned_at=timezone.now()
        )
        Assignment.objects.create(
            user=self.user1, task=self.task, assigned_at=timezone.now()
        )
        Assignment.objects.create(
            user=self.user2, task=self.task, assigned_at=timezone.now()
        )

        # Create and update stats
        stats = AssignmentStats.objects.create(user=self.user1, task=self.task)

        # Verify calculations
        self.assertAlmostEqual(stats.actual_average, Decimal("0.66666667"), places=8)
        self.assertAlmostEqual(stats.ideal_average, Decimal("0.5"), places=8)
        self.assertAlmostEqual(stats.assignment_delta, Decimal("0.33333334"), places=8)

    def test_update_all_stats(self):

        # Create some assignments
        Assignment.objects.create(
            user=self.user1, task=self.task, assigned_at=timezone.now()
        )
        Assignment.objects.create(
            user=self.user1, task=self.task, assigned_at=timezone.now()
        )
        Assignment.objects.create(
            user=self.user2, task=self.task, assigned_at=timezone.now()
        )

        # Create stats for both users
        stats1, created = AssignmentStats.objects.get_or_create(
            user=self.user1, task=self.task, ideal_average=Decimal("0.5")
        )
        stats2, created = AssignmentStats.objects.get_or_create(
            user=self.user2, task=self.task, ideal_average=Decimal("0.5")
        )

        self.assertAlmostEqual(stats1.ideal_average, Decimal("0.5"), places=8)
        self.assertAlmostEqual(stats1.actual_average, Decimal("0.66666667"), places=8)
        self.assertAlmostEqual(stats1.assignment_delta, Decimal("0.33333334"), places=8)

        self.assertAlmostEqual(stats2.ideal_average, Decimal("0.5"), places=8)
        self.assertAlmostEqual(stats2.actual_average, Decimal("0.33333333"), places=8)
        self.assertAlmostEqual(
            stats2.assignment_delta, Decimal("-0.33333334"), places=8
        )

    def test_ideal_average_with_preferences(self):
        # Create a third user with different preference
        user3 = User.objects.create_user(
            email="user3@example.com",
            first_name="User",
            last_name="Three",
            password="testpassword",
        )
        TaskPreference.objects.create(user=user3, task=self.task, value=2.0)

        # Create stats for all users
        stats1 = AssignmentStats.objects.create(user=self.user1, task=self.task)
        stats2 = AssignmentStats.objects.create(user=self.user2, task=self.task)
        stats3 = AssignmentStats.objects.create(user=user3, task=self.task)

        # Calculate ideal averages
        self.assertAlmostEqual(
            stats1.calculate_ideal_average(), Decimal("0.25"), places=8
        )  # 1.0 / (1.0 + 1.0 + 2.0)
        self.assertAlmostEqual(
            stats2.calculate_ideal_average(), Decimal("0.25"), places=8
        )  # 1.0 / (1.0 + 1.0 + 2.0)
        self.assertAlmostEqual(
            stats3.calculate_ideal_average(), Decimal("0.5"), places=8
        )  # 2.0 / (1.0 + 1.0 + 2.0)

    def test_ideal_average_with_zero_preferences(self):
        # Set user2's preference to 0
        TaskPreference.objects.filter(user=self.user2, task=self.task).update(value=0.0)

        # Create stats for both users
        stats1 = AssignmentStats.objects.create(user=self.user1, task=self.task)
        stats2 = AssignmentStats.objects.create(user=self.user2, task=self.task)

        # Calculate ideal averages
        self.assertAlmostEqual(
            stats1.calculate_ideal_average(), Decimal("1.0"), places=8
        )  # 1.0 / (1.0 + 0.0)
        self.assertAlmostEqual(
            stats2.calculate_ideal_average(), Decimal("0.0"), places=8
        )  # 0.0 / (1.0 + 0.0)

    def test_ideal_average_with_no_preferences(self):
        # Delete all preferences
        TaskPreference.objects.all().delete()

        # Create stats for both users
        stats1 = AssignmentStats.objects.create(user=self.user1, task=self.task)
        stats2 = AssignmentStats.objects.create(user=self.user2, task=self.task)

        # Calculate ideal averages
        self.assertAlmostEqual(
            stats1.calculate_ideal_average(), Decimal("0.0"), places=8
        )  # No preferences
        self.assertAlmostEqual(
            stats2.calculate_ideal_average(), Decimal("0.0"), places=8
        )  # No preferences

    def test_ideal_average_with_updated_preferences(self):
        # Create initial stats
        stats1 = AssignmentStats.objects.create(user=self.user1, task=self.task)
        stats2 = AssignmentStats.objects.create(user=self.user2, task=self.task)

        # Update user2's preference to 2.0
        TaskPreference.objects.filter(user=self.user2, task=self.task).update(value=2.0)

        # Recalculate ideal averages
        self.assertAlmostEqual(
            stats1.calculate_ideal_average(), Decimal("0.33333333"), places=8
        )  # 1.0 / (1.0 + 2.0)
        self.assertAlmostEqual(
            stats2.calculate_ideal_average(), Decimal("0.66666667"), places=8
        )  # 2.0 / (1.0 + 2.0)

    def test_ideal_average_with_all_zero_preferences(self):
        """Test ideal average calculation when all preferences are zero"""
        # Set all preferences to zero
        TaskPreference.objects.filter(task=self.task).update(value=0.0)

        # Create stats for both users
        stats1 = AssignmentStats.objects.create(user=self.user1, task=self.task)
        stats2 = AssignmentStats.objects.create(user=self.user2, task=self.task)

        # Both users should get equal distribution (0.5 each)
        self.assertAlmostEqual(stats1.calculate_ideal_average(), Decimal(0), places=8)
        self.assertAlmostEqual(stats2.calculate_ideal_average(), Decimal(0), places=8)


class ScheduleTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            first_name="User",
            last_name="One",
            password="testpassword",
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            first_name="User",
            last_name="Two",
            password="testpassword",
        )
        self.service = Service.objects.create(
            name="Test Service", day_of_week=0, start_time=time(9, 0)
        )
        self.task = Task.objects.create(
            name="Test Task",
            id="test_task_id",
            description="Test Description",
            service=self.service,
        )

        # Create preferences for both users
        TaskPreference.objects.create(user=self.user1, task=self.task, value=1.0)
        TaskPreference.objects.create(user=self.user2, task=self.task, value=1.0)

        # Create a base schedule
        self.base_schedule = Schedule.objects.create(
            name="May 2023 Schedule",
            date=datetime.date(2023, 5, 1),
            user=self.user1,
            is_official=True,
        )

        # Create assignments for the base schedule
        self.assignment1 = Assignment.objects.create(
            user=self.user1,
            task=self.task,
            assigned_at=timezone.now(),
            schedule=self.base_schedule,
        )
        self.assignment2 = Assignment.objects.create(
            user=self.user2,
            task=self.task,
            assigned_at=timezone.now(),
            schedule=self.base_schedule,
        )

        # Create stats for both users
        self.stats1 = AssignmentStats.objects.create(user=self.user1, task=self.task)
        self.stats2 = AssignmentStats.objects.create(user=self.user2, task=self.task)

    def test_schedule_creation(self):
        schedule = Schedule.objects.create(
            name="June 2023 Schedule",
            date=datetime.date(2023, 6, 1),
            user=self.user1,
        )
        self.assertEqual(schedule.name, "June 2023 Schedule")
        self.assertEqual(schedule.date, datetime.date(2023, 6, 1))
        self.assertEqual(schedule.user, self.user1)
        self.assertFalse(schedule.is_official)

    def test_create_from_base(self):
        # Create a new schedule based on the base schedule
        new_schedule = Schedule.objects.create_from_base(
            name="June 2023 Schedule",
            date=datetime.date(2023, 6, 1),
            user=self.user2,
            base_schedule=self.base_schedule,
            description="Test description",
        )

        # Check basic attributes
        self.assertEqual(new_schedule.name, "June 2023 Schedule")
        self.assertEqual(new_schedule.date, datetime.date(2023, 6, 1))
        self.assertEqual(new_schedule.user, self.user2)
        self.assertEqual(new_schedule.description, "Test description")
        self.assertEqual(new_schedule.base_schedule, self.base_schedule)
        self.assertFalse(new_schedule.is_official)

        # Check that assignments were copied
        self.assertEqual(new_schedule.base_schedule.get_assignments().count(), 2)

        # Verify user assignments were preserved
        user_counts = {}
        for user_id, count in (
            new_schedule.base_schedule.get_assignments()
            .values_list("user")
            .annotate(count=Count("user", distinct=True))
        ):
            user_counts[user_id] = count

        self.assertEqual(user_counts.get(self.user1.id), 1)
        self.assertEqual(user_counts.get(self.user2.id), 1)

    def test_select_as_official(self):
        # Create two schedules for the same month
        schedule1 = Schedule.objects.create(
            name="June 2023 Schedule A",
            date=datetime.date(2023, 6, 1),
            user=self.user1,
        )
        schedule2 = Schedule.objects.create(
            name="June 2023 Schedule B",
            date=datetime.date(2023, 6, 15),
            user=self.user2,
        )

        # Mark the first one as selected
        schedule1.select_as_official()
        schedule1.refresh_from_db()
        schedule2.refresh_from_db()

        # Check that the first one is selected
        self.assertTrue(schedule1.is_official)
        self.assertFalse(schedule2.is_official)

        # Mark the second one as selected
        schedule2.select_as_official()
        schedule1.refresh_from_db()
        schedule2.refresh_from_db()

        # Check that the second one is now selected and the first one is not
        self.assertFalse(schedule1.is_official)
        self.assertTrue(schedule2.is_official)

    def test_get_latest_selected(self):
        # May is already created and selected in setUp

        # Create June schedule and mark as selected
        june_schedule = Schedule.objects.create(
            name="June 2023 Schedule",
            date=datetime.date(2023, 6, 1),
            user=self.user1,
        )
        june_schedule.select_as_official()

        # Get the latest selected
        latest = Schedule.objects.get_latest_selected()
        self.assertEqual(latest, june_schedule)

    def test_create_assignment(self):
        schedule = Schedule.objects.create(
            name="Test Schedule", date=datetime.date(2023, 6, 1), user=self.user1
        )

        # Create a new assignment
        new_assignment = schedule.create_assignment(user=self.user1, task=self.task)

        # Check that it was created properly
        self.assertEqual(new_assignment.user, self.user1)
        self.assertEqual(new_assignment.task, self.task)
        self.assertEqual(new_assignment.schedule, schedule)
        self.assertIsNotNone(new_assignment.assigned_at)

        # Check that it's associated with the schedule
        self.assertEqual(schedule.get_assignments().count(), 1)
        self.assertEqual(schedule.get_assignments().first(), new_assignment)

    def test_get_assignments(self):
        # Get assignments from the base schedule
        assignments = self.base_schedule.get_assignments()
        self.assertEqual(assignments.count(), 2)
        self.assertIn(self.assignment1, assignments)
        self.assertIn(self.assignment2, assignments)

    def test_string_representation(self):
        schedule = Schedule.objects.create(
            name="Test Schedule", date=datetime.date(2023, 6, 1), user=self.user1
        )
        self.assertEqual(str(schedule), "Test Schedule (Draft) - June 2023")

        schedule.is_official = True
        schedule.save()
        self.assertEqual(str(schedule), "Test Schedule (Selected) - June 2023")
