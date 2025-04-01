from datetime import date, time

from django.test import TestCase
from schedules.models import Schedule, Service, Task
from schedules.services.scheduler import Scheduler
from users.models import User


class SchedulerTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            first_name="Test",
            last_name="User",
            email="testuser@test.com",
            password="testpassword",
        )
        self.service1 = Service.objects.create(
            name="Test Service 1",
            day_of_week=0,
            start_time=time(9, 0),
        )
        self.service2 = Service.objects.create(
            name="Test Service 2",
            day_of_week=3,
            start_time=time(19, 0),
        )
        self.service3 = Service.objects.create(
            name="Test Service 3",
            day_of_week=None,
            start_time=time(0, 0),  # Weekly service, check time
        )
        self.first_task = Task.objects.create(
            name="First Task",
            id="1",
            service=self.service1,
        )
        self.second_task = Task.objects.create(
            name="Second Task",
            id="2",
            service=self.service2,
        )
        self.third_task = Task.objects.create(
            name="Third Task",
            id="3",
            service=self.service3,
        )

    def test_get_date_tasks_March_2025(self):
        """
        5 weeks with non-equal number Sundays and Wednesdays in March 2025
        therefore 4 Sundays and 5 Wednesdays and 5 weekly tasks, first
        weekly tasks will have sundays calendar dates
        """
        schedule = Schedule.objects.create(
            name="Test Schedule",
            user=self.user,
            date=date(2025, 3, 1),
        )
        scheduler = Scheduler(schedule, [self.service1, self.service2, self.service3])

        date_tasks = set(scheduler.get_date_tasks())
        self.assertEqual(len(date_tasks), 14)
        self.assertIn("2025-3-2-1", date_tasks)
        self.assertIn("2025-3-9-1", date_tasks)
        self.assertIn("2025-3-16-1", date_tasks)
        self.assertIn("2025-3-23-1", date_tasks)
        self.assertIn("2025-3-30-1", date_tasks)

        self.assertIn("2025-3-5-2", date_tasks)
        self.assertIn("2025-3-12-2", date_tasks)
        self.assertIn("2025-3-19-2", date_tasks)
        self.assertIn("2025-3-26-2", date_tasks)
        # no wednesday in week 5

        self.assertIn("2025-3-2-3", date_tasks)
        self.assertIn("2025-3-9-3", date_tasks)
        self.assertIn("2025-3-16-3", date_tasks)
        self.assertIn("2025-3-23-3", date_tasks)
        self.assertIn("2025-3-30-3", date_tasks)

    def test_get_date_tasks_April_2025(self):
        """
        5 weeks with non-equal number Sundays and Wednesdays
        4 Sundays and 5 Wednesdays and 5 weekly tasks, first
        weekly task will have a calendar date of a wednesday in this case
        """
        schedule = Schedule.objects.create(
            name="Test Schedule",
            user=self.user,
            date=date(2025, 4, 1),
        )
        scheduler = Scheduler(schedule, [self.service1, self.service2, self.service3])

        date_tasks = set(scheduler.get_date_tasks())
        self.assertEqual(len(date_tasks), 14)
        self.assertIn("2025-4-6-1", date_tasks)
        self.assertIn("2025-4-13-1", date_tasks)
        self.assertIn("2025-4-20-1", date_tasks)
        self.assertIn("2025-4-27-1", date_tasks)

        self.assertIn("2025-4-2-2", date_tasks)
        self.assertIn("2025-4-9-2", date_tasks)
        self.assertIn("2025-4-16-2", date_tasks)
        self.assertIn("2025-4-23-2", date_tasks)
        self.assertIn("2025-4-30-2", date_tasks)

        self.assertIn("2025-4-2-3", date_tasks)  # odd duck
        self.assertIn("2025-4-6-3", date_tasks)
        self.assertIn("2025-4-13-3", date_tasks)
        self.assertIn("2025-4-20-3", date_tasks)
        self.assertIn("2025-4-27-3", date_tasks)

    def test_get_date_tasks_May_2025(self):
        """
        4 weeks with equal number Sundays and Wednesdays
        4 Sundays and 4 Wednesdays and 4 weekly tasks
        """
        schedule = Schedule.objects.create(
            name="Test Schedule",
            user=self.user,
            date=date(2025, 5, 1),
        )
        scheduler = Scheduler(schedule, [self.service1, self.service2, self.service3])

        date_tasks = set(scheduler.get_date_tasks())
        self.assertEqual(len(date_tasks), 12)
        self.assertIn("2025-5-4-1", date_tasks)
        self.assertIn("2025-5-11-1", date_tasks)
        self.assertIn("2025-5-18-1", date_tasks)
        self.assertIn("2025-5-25-1", date_tasks)

        self.assertIn("2025-5-7-2", date_tasks)
        self.assertIn("2025-5-14-2", date_tasks)
        self.assertIn("2025-5-21-2", date_tasks)
        self.assertIn("2025-5-28-2", date_tasks)

        self.assertIn("2025-5-4-3", date_tasks)
        self.assertIn("2025-5-11-3", date_tasks)
        self.assertIn("2025-5-18-3", date_tasks)
        self.assertIn("2025-5-25-3", date_tasks)
