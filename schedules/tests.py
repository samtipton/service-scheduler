import datetime
from datetime import time
from django.db import IntegrityError
from django.forms import ValidationError
from django.test import TestCase
from django.utils import timezone
from schedules.models import Service, Task, TaskPreference, Assignment
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
            f"{now.strftime('%Y-%m-%d %H:%M')}-test_task_id_1 -> Test User (testuser@example.com)",
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
