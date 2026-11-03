from datetime import date, datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from messaging.models import SentEmail
from schedules.models import Assignment, Schedule, Service, Task
from users.models import Group, Membership


User = get_user_model()


class GroupNavTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test+nav@example.com",
            first_name="Nav",
            last_name="User",
            password="nav-password-1",
        )
        self.client.force_login(self.user)

    def test_no_group_asks_for_one_and_hides_schedules(self):
        response = self.client.get("/schedules/")

        self.assertContains(response, "Create a group")
        self.assertContains(response, "Create a group to create a schedule.")
        self.assertNotContains(response, "Create New Schedule")

    def test_creating_a_group_selects_it_and_makes_the_creator_admin(self):
        response = self.client.post("/groups/create/", {"name": "Second Church"})

        self.assertRedirects(response, "/schedules/")
        group = Group.objects.get(name="Second Church")
        self.assertTrue(
            Membership.objects.filter(
                user=self.user, group=group, role=Membership.ADMIN
            ).exists()
        )
        page = self.client.get("/schedules/")
        self.assertContains(page, "Second Church")
        self.assertContains(page, "Create New Schedule")
        self.assertNotContains(page, "Create a group to create a schedule.")

    def test_schedule_list_follows_the_selected_group(self):
        home = Group.objects.create(name="Home Church")
        other = Group.objects.create(name="Other Church")
        Membership.objects.create(user=self.user, group=home, role=Membership.ADMIN)
        Membership.objects.create(user=self.user, group=other, role=Membership.SCHEDULER)
        Schedule.objects.create(
            name="Home Month", date=date(2026, 6, 1), user=self.user, group=home
        )
        Schedule.objects.create(
            name="Other Month", date=date(2026, 6, 1), user=self.user, group=other
        )

        first = self.client.get("/schedules/")
        self.assertContains(first, "Home Month")
        self.assertNotContains(first, "Other Month")

        switched = self.client.post("/groups/select/", {"group": other.id})
        self.assertEqual(switched.status_code, 302)
        second = self.client.get("/schedules/")
        self.assertContains(second, "Other Month")
        self.assertNotContains(second, "Home Month")

    def test_adding_an_existing_login_sends_no_mail(self):
        group = Group.objects.create(name="Home Church")
        Membership.objects.create(user=self.user, group=group, role=Membership.ADMIN)
        other = User.objects.create_user(
            email="test+member@example.com",
            first_name="Ada",
            last_name="Member",
            password="member-password-1",
        )
        with patch("users.mail.post_plain_email") as mail:
            response = self.client.post(
                "/groups/add/",
                {"email": other.email, "role": Membership.SCHEDULER},
            )

        self.assertRedirects(response, "/groups/")
        self.assertEqual(mail.call_count, 0)
        self.assertTrue(
            Membership.objects.filter(
                user=other, group=group, role=Membership.SCHEDULER
            ).exists()
        )
        roster = self.client.get("/groups/")
        self.assertContains(roster, other.email)
        self.assertNotContains(roster, "Logins")

    def test_unknown_email_is_not_created_and_not_mailed(self):
        group = Group.objects.create(name="Home Church")
        Membership.objects.create(user=self.user, group=group, role=Membership.ADMIN)
        with patch("users.mail.post_plain_email") as mail:
            response = self.client.post(
                "/groups/add/",
                {"email": "test+missing@example.com", "role": Membership.SCHEDULER},
            )

        self.assertEqual(mail.call_count, 0)
        self.assertContains(response, "Invite links are not built yet.")
        self.assertFalse(User.objects.filter(email="test+missing@example.com").exists())

    def test_scheduler_can_read_the_roster_and_cannot_add(self):
        group = Group.objects.create(name="Home Church")
        Membership.objects.create(user=self.user, group=group, role=Membership.SCHEDULER)
        page = self.client.get("/groups/")
        self.assertContains(page, self.user.email)
        self.assertNotContains(page, 'action="/groups/add/"')
        self.assertEqual(
            self.client.post(
                "/groups/add/",
                {"email": "test+missing@example.com", "role": Membership.SCHEDULER},
            ).status_code,
            403,
        )

    def test_the_last_admin_stays(self):
        group = Group.objects.create(name="Home Church")
        membership = Membership.objects.create(
            user=self.user, group=group, role=Membership.ADMIN
        )
        self.client.post(
            "/groups/remove/",
            {"membership": membership.id},
        )
        membership.refresh_from_db()
        self.assertEqual(membership.role, Membership.ADMIN)

    def test_delete_group_removes_its_data_and_keeps_the_accounts(self):
        doomed = Group.objects.create(name="Doomed")
        kept = Group.objects.create(name="Kept")
        Membership.objects.create(user=self.user, group=doomed, role=Membership.ADMIN)
        Membership.objects.create(user=self.user, group=kept, role=Membership.ADMIN)
        member = User.objects.create_user(
            email="test+kept@example.com",
            first_name="Kept",
            last_name="Person",
            password="kept-password-1",
        )
        Membership.objects.create(user=member, group=doomed, role=Membership.SCHEDULER)
        service = Service.objects.create(
            name="Sunday", day_of_week=0, start_time="09:00", group=doomed
        )
        task = Task.objects.create(
            id="doomed_song", name="Song", service=service, group=doomed, order=1
        )
        schedule = Schedule.objects.create(
            name="Doomed Month", date=date(2026, 6, 1), user=self.user, group=doomed
        )
        Assignment.objects.create(
            user=member,
            task=task,
            schedule=schedule,
            assigned_at=datetime(2026, 6, 7, tzinfo=timezone.utc),
            group=doomed,
        )
        SentEmail.objects.create(
            schedule=schedule,
            subject="Gone",
            body="Gone",
            sent_by=self.user,
            recipients=member.email,
        )
        Schedule.objects.create(
            name="Kept Month", date=date(2026, 6, 1), user=self.user, group=kept
        )

        page = self.client.get("/groups/")
        self.assertContains(page, "This cannot be undone.")
        self.assertContains(page, "People keep their accounts.")
        self.assertContains(page, "Delete this group")

        response = self.client.post("/groups/delete/")
        self.assertRedirects(response, "/schedules/")
        self.assertFalse(Group.objects.filter(name="Doomed").exists())
        self.assertFalse(Service.objects.filter(name="Sunday").exists())
        self.assertFalse(Task.objects.filter(id="doomed_song").exists())
        self.assertFalse(Schedule.objects.filter(name="Doomed Month").exists())
        self.assertFalse(Assignment.objects.exists())
        self.assertFalse(SentEmail.objects.exists())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(User.objects.filter(pk=member.pk).exists())
        self.assertTrue(Schedule.objects.filter(name="Kept Month").exists())
        self.assertFalse(Membership.objects.filter(user=member).exists())

    def test_scheduler_cannot_delete_the_group(self):
        group = Group.objects.create(name="Home Church")
        Membership.objects.create(
            user=self.user, group=group, role=Membership.SCHEDULER
        )
        page = self.client.get("/groups/")
        self.assertNotContains(page, "Delete this group")
        self.assertEqual(self.client.post("/groups/delete/").status_code, 403)
        self.assertTrue(Group.objects.filter(pk=group.pk).exists())
