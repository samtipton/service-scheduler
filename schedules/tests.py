from datetime import time
import datetime
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from schedules.models import Service, Task, TaskPreference
from users.models import User

class TaskPreferenceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.service = Service.objects.create(name='Test Service', day_of_week=0, start_time=time(9, 0))
        self.task = Task.objects.create(name='Test Task', 
                                        id='test_task_id',
                                        description='Test Description', 
                                        service=self.service)

    def test_task_preference_creation(self):
        TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        task_preference = TaskPreference.objects.get(user=self.user, task=self.task)
        self.assertEqual(task_preference.value, 1.0)
        self.assertEqual(task_preference.user, self.user)
        self.assertEqual(task_preference.task, self.task)
        self.assertIsNotNone(task_preference.updated_at)
    
    def test_is_eligible(self):
        TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        other_task = Task.objects.create(name='Other Task', id='other_task_id', service=self.service)
        self.assertTrue(TaskPreference.objects.is_eligible(self.user, self.task))
        self.assertFalse(TaskPreference.objects.is_eligible(self.user, other_task))

    def test_unique_together(self):
        TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        with self.assertRaises(IntegrityError):
            TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)

    def test_ordering(self):
        other_task = Task.objects.create(name='Other Task', id='other_task_id', service=self.service)
        TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        pref2 = TaskPreference.objects.create(user=self.user, task=other_task, value=2.0)

        # Manually adjust the `updated_at` timestamp
        TaskPreference.objects.filter(id=pref2.id).update(updated_at=timezone.now() + datetime.timedelta(days=1))

        all_preferences = TaskPreference.objects.all()
        self.assertEqual(TaskPreference.objects.all().count(), 2)
        self.assertEqual(all_preferences[0].value, 2.0)
        self.assertEqual(all_preferences[1].value, 1.0)

    def test_str(self):
        task_preference = TaskPreference.objects.create(user=self.user, task=self.task, value=1.0)
        self.assertEqual(str(task_preference), f"{self.user} -> {self.task.id} (1.0)")
