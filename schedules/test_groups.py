import json
from datetime import date, datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from messaging.models import EmailTemplate
from messaging.services.brevo import FROM_EMAIL
from schedules.models import Assignment, Schedule, Service, Task
from schedules.services.scheduler import Scheduler
from users.access import roster_for
from users.models import Group, Membership


User = get_user_model()


@override_settings(BREVO_API_KEY="test-key")
class GroupIsolationTests(TestCase):
    def setUp(self):
        self.production = Group.objects.get()
        self.sandbox = Group.objects.create(name="Sandbox")
        self.prod_user = User.objects.create_user(
            email="test+prod@example.com",
            first_name="Prod",
            last_name="Member",
            password="prod-password-1",
        )
        self.sand_user = User.objects.create_user(
            email="test+sand@example.com",
            first_name="Sand",
            last_name="Member",
            password="sand-password-1",
        )
        Membership.objects.create(
            user=self.prod_user, group=self.production, role=Membership.SCHEDULER
        )
        Membership.objects.create(
            user=self.sand_user, group=self.sandbox, role=Membership.SCHEDULER
        )
        self.prod_service = Service.objects.create(
            name="Sunday", day_of_week=0, start_time="09:00", group=self.production
        )
        self.sand_service = Service.objects.create(
            name="Sunday", day_of_week=0, start_time="09:00", group=self.sandbox
        )
        self.prod_task = Task.objects.create(
            id="prod_song",
            name="Song",
            service=self.prod_service,
            group=self.production,
            order=1,
        )
        self.sand_task = Task.objects.create(
            id="sand_song",
            name="Song",
            service=self.sand_service,
            group=self.sandbox,
            order=1,
        )
        when = datetime(2026, 5, 3, tzinfo=timezone.utc)
        self.prod_past = Schedule.objects.create(
            name="Production May",
            date=date(2026, 5, 1),
            user=self.prod_user,
            group=self.production,
        )
        self.sand_past = Schedule.objects.create(
            name="Sandbox May",
            date=date(2026, 5, 1),
            user=self.sand_user,
            group=self.sandbox,
        )
        Assignment.objects.create(
            user=self.prod_user,
            task=self.prod_task,
            schedule=self.prod_past,
            assigned_at=when,
            group=self.production,
        )
        Assignment.objects.create(
            user=self.sand_user,
            task=self.sand_task,
            schedule=self.sand_past,
            assigned_at=when,
            group=self.sandbox,
        )
        self.prod_june = Schedule.objects.create(
            name="Production June",
            date=date(2026, 6, 1),
            user=self.prod_user,
            group=self.production,
        )
        self.template = EmailTemplate.objects.create(
            name="Published",
            subject="Hello",
            body="Body",
            created_by=self.prod_user,
        )

    def test_staff_and_superuser_cannot_open_another_groups_schedule(self):
        staff = User.objects.create_user(
            email="test+staff@example.com",
            first_name="Staff",
            last_name="User",
            password="staff-password-1",
            is_staff=True,
        )
        superuser = User.objects.create_superuser(
            email="test+root@example.com",
            first_name="Root",
            last_name="User",
            password="root-password-1",
        )
        for person in (staff, superuser):
            self.client.force_login(person)
            self.assertEqual(
                self.client.get(f"/schedules/{self.prod_june.id}/").status_code,
                404,
            )
            self.assertEqual(
                self.client.put(
                    f"/schedules/{self.prod_june.id}/update",
                    data="{}",
                    content_type="application/json",
                ).status_code,
                404,
            )
            listing = self.client.get("/schedules/")
            self.assertNotContains(listing, "Production June")
            self.assertNotContains(listing, "Sandbox May")

        Membership.objects.create(
            user=staff, group=self.sandbox, role=Membership.SCHEDULER
        )
        self.client.force_login(staff)
        home = self.client.get("/schedules/")
        self.assertContains(home, "Sandbox May")
        self.assertNotContains(home, "Production June")
        self.assertEqual(
            self.client.get(f"/schedules/{self.prod_june.id}/").status_code, 404
        )
        denied = self.client.post(f"/schedules/{self.sand_past.id}/delete")
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(Schedule.objects.filter(id=self.sand_past.id).exists())

    def test_sandbox_user_cannot_open_a_production_schedule(self):
        self.client.force_login(self.sand_user)

        self.assertEqual(
            self.client.get(f"/schedules/{self.prod_june.id}/").status_code, 404
        )
        listing = self.client.get("/schedules/")
        self.assertNotContains(listing, "Production June")
        self.assertContains(listing, "Sandbox May")

        self.client.force_login(self.prod_user)
        listing = self.client.get("/schedules/")
        self.assertContains(listing, "Production June")
        self.assertNotContains(listing, "Sandbox May")

    def test_solver_history_ignores_the_other_group(self):
        counter = Scheduler.__new__(Scheduler)
        counter.schedule = self.prod_june
        counter.year = 2026
        counter.month = 6
        counts, _totals = Scheduler._load_assignment_counts(counter)

        self.assertEqual(counts[(self.prod_user.id, self.prod_task.id)], 1)
        self.assertNotIn((self.sand_user.id, self.sand_task.id), counts)
        self.assertNotIn(self.sand_user, roster_for(self.production))
        self.assertIn(self.prod_user, roster_for(self.production))

    @patch("messaging.services.send.render_schedule_pdf", return_value=b"%PDF-test")
    def test_production_send_leaves_out_the_sandbox_address(self, _pdf):
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"messageId":"<test@brevo>"}'

        def fake_urlopen(request, timeout=30):
            captured["body"] = json.loads(request.data.decode())
            return Response()

        self.client.force_login(self.prod_user)
        with patch("messaging.services.brevo.urllib.request.urlopen", fake_urlopen):
            response = self.client.post(
                "/messages/email/send/",
                {"schedule": self.prod_june.pk, "template": self.template.pk},
            )

        self.assertEqual(response.status_code, 302)
        addresses = [row["email"] for row in captured["body"]["bcc"]]
        self.assertIn(self.prod_user.email, addresses)
        self.assertNotIn(self.sand_user.email, addresses)
        self.assertEqual(captured["body"]["to"], [{"email": FROM_EMAIL}])
