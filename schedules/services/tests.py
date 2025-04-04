from datetime import date, time
from unittest.mock import MagicMock, patch

from django.test import TestCase
from schedules.models import Schedule, Service, Task
from schedules.services.scheduler import Scheduler
from users.models import User


class SchedulerTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Patch the methods and start the patches
        cls.patcher_user_model = patch("schedules.services.scheduler.get_user_model")
        cls.patcher_task_prefs = patch(
            "schedules.services.scheduler.TaskPreference.objects.all"
        )

        # Start the patches
        cls.mock_get_user_model = cls.patcher_user_model.start()
        cls.mock_task_prefs_all = cls.patcher_task_prefs.start()

        # Mock user model return value
        cls.mock_user1 = MagicMock(pk=1, username="user1")
        cls.mock_user2 = MagicMock(pk=2, username="user2")
        cls.mock_get_user_model.return_value.objects.all.return_value = [
            cls.mock_user1,
            cls.mock_user2,
        ]

        # Mock tasks
        cls.mock_tasks = []
        for i, name in enumerate(["First Task", "Second Task", "Third Task"], 1):
            task = MagicMock()
            task.name = name
            task.id = str(i)
            task.get_eligible_users.return_value = [cls.mock_user1, cls.mock_user2]
            cls.mock_tasks.append(task)

        # Assign the mock_tasks_property to each service in mock_services
        cls.mock_services = [
            MagicMock(
                **{
                    "name": "Test Service 1",
                    "day_of_week": 0,
                    "start_time": time(9, 0),
                    "tasks.all.return_value": [cls.mock_tasks[0]],
                }
            ),
            MagicMock(
                **{
                    "name": "Test Service 2",
                    "day_of_week": 3,
                    "start_time": time(19, 0),
                    "tasks.all.return_value": [cls.mock_tasks[1]],
                }
            ),
            MagicMock(
                **{
                    "name": "Test Service 3",
                    "day_of_week": None,
                    "start_time": time(0, 0),
                    "tasks.all.return_value": [cls.mock_tasks[2]],
                }
            ),
        ]

        # Mock task preferences
        cls.mock_task_prefs = []
        for user in [cls.mock_user1, cls.mock_user2]:
            for task in cls.mock_tasks:
                task_pref = MagicMock()
                task_pref.user = user
                task_pref.task = task
                task_pref.value = 1.0
                cls.mock_task_prefs.append(task_pref)

        cls.mock_task_prefs_all.return_value.select_related.return_value = (
            cls.mock_task_prefs
        )

        # Mock assignment stats
        cls.mock_assignment_stats_all = []
        for user in [cls.mock_user1, cls.mock_user2]:
            for task in cls.mock_tasks:
                stat = MagicMock()
                # Configure the stat with actual attributes instead of nested configuration
                stat.user = user
                stat.task = task
                stat.ideal_average = 1.0  # Add any other needed attributes
                stat.actual_average = 0.5
                cls.mock_assignment_stats_all.append(stat)

        # Create the schedule mock and set its assignment_stats property
        cls.mock_schedule = MagicMock()
        cls.mock_schedule.configure_mock(
            **{
                "assignment_stats.all.return_value.select_related.return_value": cls.mock_assignment_stats_all
            }
        )

    @classmethod
    def tearDownClass(cls):
        # Stop all patches
        cls.patcher_user_model.stop()
        cls.patcher_task_prefs.stop()
        super().tearDownClass()

    def test_service_tasks(self):
        tasks = (
            self.mock_services[0].tasks.all()
            + self.mock_services[1].tasks.all()
            + self.mock_services[2].tasks.all()
        )

        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0].name, "First Task")
        self.assertEqual(tasks[1].name, "Second Task")
        self.assertEqual(tasks[2].name, "Third Task")
        self.assertEqual(
            tasks[0].get_eligible_users(), [self.mock_user1, self.mock_user2]
        )
        self.assertEqual(
            tasks[1].get_eligible_users(), [self.mock_user1, self.mock_user2]
        )
        self.assertEqual(
            tasks[2].get_eligible_users(), [self.mock_user1, self.mock_user2]
        )

    def test_user_task_stats(self):
        user_task_stats = self.mock_schedule.assignment_stats.all().select_related(
            "user", "task"
        )
        print(user_task_stats)
        self.assertEqual(len(user_task_stats), 6)
        self.assertEqual(user_task_stats[0].task.name, "First Task")
        self.assertEqual(user_task_stats[1].task.name, "Second Task")
        self.assertEqual(user_task_stats[2].task.name, "Third Task")

    def test_init(self):
        # Mock schedule and services
        self.mock_schedule.date.year = 2025
        self.mock_schedule.date.month = 3

        # Create the Scheduler instance
        scheduler = Scheduler(self.mock_schedule, self.mock_services)

        # Assertions
        self.assertEqual(scheduler.year, 2025)
        self.assertEqual(scheduler.month, 3)
        self.assertEqual(scheduler.users, [self.mock_user1, self.mock_user2])
        self.assertIn(self.mock_tasks[0], scheduler.services[0].tasks.all())
        self.assertIn(self.mock_tasks[1], scheduler.services[1].tasks.all())
        self.assertIn(self.mock_tasks[2], scheduler.services[2].tasks.all())
        self.assertEqual(
            self.mock_task_prefs[0], scheduler.user_task_preferences[1]["1"]
        )

    def test_get_date_tasks_March_2025(self):
        """
        5 weeks with non-equal number Sundays and Wednesdays in March 2025
        therefore 4 Sundays and 5 Wednesdays and 5 weekly tasks, first
        weekly tasks will have sundays calendar dates
        """
        self.mock_schedule.date.year = 2025
        self.mock_schedule.date.month = 3
        scheduler = Scheduler(self.mock_schedule, self.mock_services)

        date_tasks = set(str(dt) for dt in scheduler.get_date_tasks())
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
        self.mock_schedule.date.year = 2025
        self.mock_schedule.date.month = 4
        scheduler = Scheduler(self.mock_schedule, self.mock_services)

        date_tasks = set(str(dt) for dt in scheduler.get_date_tasks())
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
        self.mock_schedule.date.year = 2025
        self.mock_schedule.date.month = 5
        scheduler = Scheduler(self.mock_schedule, self.mock_services)

        date_tasks = set(str(dt) for dt in scheduler.get_date_tasks())
        print(date_tasks)
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
