import json
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.checks import run_checks
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings

from config.env import as_bool, database_from_url, is_database_url
from users.models import Group, Membership


User = get_user_model()


class EnvTests(SimpleTestCase):
    def test_a_bare_host_is_not_a_database_url(self):
        self.assertFalse(is_database_url("localhost"))
        self.assertFalse(is_database_url(""))
        self.assertTrue(is_database_url("postgres://postgres@localhost/servicescheduler"))

    def test_as_bool_rejects_the_string_false(self):
        self.assertFalse(as_bool("False"))
        self.assertFalse(as_bool("no"))
        self.assertTrue(as_bool("true"))
        self.assertTrue(as_bool(True))

    def test_remote_database_url_requires_ssl(self):
        parsed = database_from_url(
            "postgres://user:p%40ss@db.example.com:5432/servicescheduler"
        )

        self.assertEqual(parsed["USER"], "user")
        self.assertEqual(parsed["PASSWORD"], "p@ss")
        self.assertEqual(parsed["HOST"], "db.example.com")
        self.assertEqual(parsed["NAME"], "servicescheduler")
        self.assertEqual(parsed["OPTIONS"]["sslmode"], "require")

    def test_local_database_url_does_not_force_ssl(self):
        parsed = database_from_url(
            "postgres://postgres:pw@localhost:5432/servicescheduler?sslmode=disable"
        )

        self.assertEqual(parsed["OPTIONS"]["sslmode"], "disable")
        local = database_from_url("postgres://postgres:pw@127.0.0.1/servicescheduler")
        self.assertNotIn("OPTIONS", local)


@override_settings(
    DEBUG=False,
    ALLOWED_HOSTS=["scheduler.example.com"],
    SECURE_SSL_REDIRECT=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SECURE_HSTS_SECONDS=0,
)
class DeployCheckTests(SimpleTestCase):
    def test_only_hsts_stays_open_until_https_is_confirmed(self):
        ids = {issue.id for issue in run_checks(include_deployment_checks=True)}

        self.assertIn("security.W004", ids)
        self.assertFalse(
            ids
            & {
                "security.W008",
                "security.W012",
                "security.W016",
                "security.W018",
                "security.W020",
            }
        )


class SeedGuardTests(TestCase):
    @override_settings(DEBUG=False)
    def test_seed_refuses_when_debug_is_false(self):
        with self.assertRaises(CommandError) as caught:
            call_command("seed_services")

        self.assertIn("DEBUG", str(caught.exception))


class AccountFlowTests(TestCase):
    def setUp(self):
        self.password = "old-password-1"
        self.user = User.objects.create_user(
            email="test+login@example.com",
            first_name="Login",
            last_name="User",
            password=self.password,
        )
        self.group = Group.objects.get()
        Membership.objects.create(
            user=self.user, group=self.group, role=Membership.SCHEDULER
        )

    def test_login_page_links_to_forgot_password(self):
        response = self.client.get("/login/")

        self.assertContains(response, "Forgot password?")
        self.assertContains(response, 'href="/password_reset/"')
        self.assertContains(response, "Email:")

    def test_login_reaches_the_schedule_list(self):
        response = self.client.post(
            "/login/",
            {"username": self.user.email, "password": self.password},
        )

        self.assertRedirects(response, "/schedules/")

    def test_change_password_uses_the_validators(self):
        self.client.force_login(self.user)
        short = self.client.post(
            "/password_change/",
            {
                "old_password": self.password,
                "new_password1": "short",
                "new_password2": "short",
            },
        )
        self.assertEqual(short.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

        response = self.client.post(
            "/password_change/",
            {
                "old_password": self.password,
                "new_password1": "new-password-2",
                "new_password2": "new-password-2",
            },
        )

        self.assertRedirects(response, "/password_change/done/")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-password-2"))
        menu = self.client.get("/schedules/")
        self.assertContains(menu, "Change password")
        self.assertNotContains(menu, "Logins")

    def test_forgot_password_does_not_reveal_the_address(self):
        unusable = User.objects.create_user(
            email="test+unset@example.com",
            first_name="Unset",
            last_name="User",
            password=None,
        )
        self.assertFalse(unusable.has_usable_password())
        with patch("users.mail.post_plain_email") as mail:
            pages = [
                self.client.post("/password_reset/", {"email": address}, follow=True)
                for address in (
                    self.user.email,
                    unusable.email,
                    "test+missing@example.com",
                )
            ]

        self.assertEqual(mail.call_count, 1)
        self.assertIn("/reset/", mail.call_args.kwargs["body"])
        self.assertNotIn("test+missing@example.com", mail.call_args.kwargs["body"])
        self.assertTrue(all(page.status_code == 200 for page in pages))
        self.assertEqual(pages[0].content, pages[1].content)
        self.assertEqual(pages[1].content, pages[2].content)
        self.assertContains(pages[0], "If that address has a login")

    def test_admin_mails_a_set_password_link_and_a_scheduler_cannot(self):
        admin = User.objects.create_user(
            email="test+admin@example.com",
            first_name="Ada",
            last_name="Admin",
            password="admin-password-1",
        )
        Membership.objects.create(user=admin, group=self.group, role=Membership.ADMIN)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/account/members/").status_code, 403)

        self.client.force_login(admin)
        menu = self.client.get("/schedules/")
        self.assertContains(menu, "Groups")
        with patch("users.mail.post_plain_email") as mail:
            response = self.client.post(
                "/account/members/new/",
                {
                    "group": self.group.pk,
                    "email": "test+new@example.com",
                    "first_name": "New",
                    "last_name": "Person",
                    "role": Membership.SCHEDULER,
                },
            )

        self.assertRedirects(response, "/account/members/")
        created = User.objects.get(email="test+new@example.com")
        self.assertFalse(created.has_usable_password())
        self.assertFalse(created.is_staff)
        self.assertTrue(
            Membership.objects.filter(
                user=created, group=self.group, role=Membership.SCHEDULER
            ).exists()
        )
        path = re.search(r"https?://[^/]+(/reset/\S+)", mail.call_args.kwargs["body"])
        self.assertIsNotNone(path)
        opened = self.client.get(path.group(1))
        self.assertEqual(opened.status_code, 302)
        set_password = self.client.post(
            opened.url,
            {"new_password1": "short", "new_password2": "short"},
        )
        self.assertEqual(set_password.status_code, 200)
        created.refresh_from_db()
        self.assertFalse(created.has_usable_password())
        done = self.client.post(
            opened.url,
            {"new_password1": "set-password-1", "new_password2": "set-password-1"},
        )
        self.assertRedirects(done, "/reset/done/")
        created.refresh_from_db()
        self.assertTrue(created.check_password("set-password-1"))

    def test_normal_user_is_not_staff_and_cannot_open_admin(self):
        self.assertFalse(self.user.is_staff)
        self.client.force_login(self.user)
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)


class GridCsrfTests(TestCase):
    def test_update_without_the_token_fails(self):
        from datetime import date

        from schedules.models import Schedule, Service, Task

        user = User.objects.create_user(
            email="test+csrf@example.com",
            first_name="Csrf",
            last_name="User",
            password="csrf-password-1",
        )
        service = Service.objects.create(name="Wednesday", day_of_week=3, start_time="19:00")
        Task.objects.create(id="csrf_lesson", name="Lesson", service=service, order=1)
        schedule = Schedule.objects.create(
            name="Dec 2026", date=date(2026, 12, 1), user=user
        )
        Membership.objects.create(
            user=user, group=schedule.group, role=Membership.SCHEDULER
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        payload = json.dumps({"2026-12-23-csrf_lesson": "User, Csrf"})
        denied = client.put(
            f"/schedules/{schedule.id}/update",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        client.get("/schedules/")
        token = client.cookies["csrftoken"].value
        allowed = client.put(
            f"/schedules/{schedule.id}/update",
            data=payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(allowed.status_code, 204)
