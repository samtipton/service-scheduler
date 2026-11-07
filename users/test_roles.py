import datetime
from datetime import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from schedules.models import Schedule, Service
from users.models import Group, Membership


User = get_user_model()


class RoleChoiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="test+role-admin@example.com",
            first_name="Ada",
            last_name="Admin",
            password="x",
        )
        self.group = Group.objects.create(name="Home")
        Membership.objects.create(
            user=self.admin, group=self.group, role=Membership.ADMIN
        )
        self.client.force_login(self.admin)

    def test_add_person_lists_user_then_scheduler_then_admin(self):
        for path in ("/account/members/", "/groups/"):
            html = self.client.get(path).content.decode()
            user_at = html.index('value="user"')
            scheduler_at = html.index('value="scheduler"')
            admin_at = html.index('value="admin"')
            self.assertLess(user_at, scheduler_at)
            self.assertLess(scheduler_at, admin_at)

    def test_creating_a_login_can_choose_user(self):
        with patch("users.mail.post_plain_email") as mail:
            response = self.client.post(
                "/account/members/new/",
                {
                    "group": self.group.pk,
                    "email": "test+viewer@example.com",
                    "first_name": "Vi",
                    "last_name": "Ewer",
                    "role": Membership.USER,
                },
            )
        self.assertRedirects(response, "/account/members/")
        self.assertEqual(mail.call_count, 1)
        created = User.objects.get(email="test+viewer@example.com")
        self.assertFalse(created.has_usable_password())
        self.assertTrue(
            Membership.objects.filter(
                user=created, group=self.group, role=Membership.USER
            ).exists()
        )

    def test_a_missing_role_defaults_to_user(self):
        with patch("users.mail.post_plain_email"):
            created_response = self.client.post(
                "/account/members/new/",
                {
                    "group": self.group.pk,
                    "email": "test+blank-role@example.com",
                    "first_name": "Blank",
                    "last_name": "Role",
                },
            )
        self.assertRedirects(created_response, "/account/members/")
        created = User.objects.get(email="test+blank-role@example.com")
        self.assertTrue(
            Membership.objects.filter(
                user=created, group=self.group, role=Membership.USER
            ).exists()
        )

        other = User.objects.create_user(
            email="test+blank-add@example.com",
            first_name="Blank",
            last_name="Add",
            password="x",
        )
        added = self.client.post(
            "/groups/add/",
            {"email": other.email, "role": "nope"},
        )
        self.assertRedirects(added, "/groups/")
        self.assertTrue(
            Membership.objects.filter(
                user=other, group=self.group, role=Membership.USER
            ).exists()
        )

    def test_adding_an_existing_login_can_choose_user(self):
        other = User.objects.create_user(
            email="test+already@example.com",
            first_name="Al",
            last_name="Ready",
            password="x",
        )
        response = self.client.post(
            "/groups/add/",
            {"email": other.email, "role": Membership.USER},
        )
        self.assertRedirects(response, "/groups/")
        self.assertTrue(
            Membership.objects.filter(
                user=other, group=self.group, role=Membership.USER
            ).exists()
        )


class ReadOnlyMemberTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            email="test+viewer@example.com",
            first_name="Vi",
            last_name="Ewer",
            password="x",
        )
        self.group = Group.objects.create(name="Home")
        Membership.objects.create(
            user=self.viewer, group=self.group, role=Membership.USER
        )
        self.schedule = Schedule.objects.create(
            name="June Card",
            date=datetime.date(2026, 6, 1),
            user=self.viewer,
            group=self.group,
        )
        for name in ("Sunday AM", "Sunday Class", "Sunday PM", "Wednesday"):
            Service.objects.create(
                name=name,
                day_of_week=0,
                start_time=time(9, 0),
                group=self.group,
            )
        self.client.force_login(self.viewer)

    def test_a_user_can_open_the_grid_and_not_change_it(self):
        page = self.client.get(f"/schedules/{self.schedule.id}/")
        self.assertContains(page, "June Card")
        self.assertContains(page, "Download PDF")
        self.assertContains(page, "readonly")
        self.assertNotContains(page, "Generate Assignments")
        self.assertNotContains(page, "Clear Assignments")
        self.assertNotContains(page, "Send schedule")
        listing = self.client.get("/schedules/")
        self.assertContains(listing, "June Card")
        self.assertNotContains(listing, "Create New Schedule")
        self.assertNotContains(listing, "Create a group")

        denied = self.client.put(
            f"/schedules/{self.schedule.id}/update",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(
            self.client.post(
                "/schedules/create/",
                {"name": "July", "date": "2026-07-01", "description": ""},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/groups/create/", {"name": "Other"}).status_code,
            403,
        )
