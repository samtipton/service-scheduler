import base64
import io
import json
import urllib.error
from datetime import date, datetime, timezone as datetime_timezone
from http.client import HTTPMessage
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from messaging.models import EmailTemplate, SentEmail
from messaging.services.placeholders import fill_placeholders
from messaging.services.recipients import active_roster, bcc_chunks
from messaging.services.brevo import FROM_EMAIL
from schedules.models import Schedule, Service
from schedules.services.pdf import render_schedule_pdf


class PlaceholderTests(TestCase):
    def test_month_and_year_are_filled(self):
        schedule = Schedule(date=date(2026, 10, 1))

        self.assertEqual(
            fill_placeholders("Schedule for {{month}} {{year}}.", schedule),
            "Schedule for October 2026.",
        )
        self.assertEqual(
            fill_placeholders("Leave {{name}} and {month} alone.", schedule),
            "Leave {{name}} and {month} alone.",
        )


class RosterTests(TestCase):
    def test_inactive_users_are_left_off(self):
        User = get_user_model()
        User.objects.create_user(
            email="test+active@example.com",
            first_name="Active",
            last_name="Member",
        )
        User.objects.create_user(
            email="test+inactive@example.com",
            first_name="Inactive",
            last_name="Member",
            is_active=False,
        )

        emails = list(active_roster().values_list("email", flat=True))

        self.assertIn("test+active@example.com", emails)
        self.assertNotIn("test+inactive@example.com", emails)

    def test_bcc_chunks_stay_within_the_attachment_cap(self):
        chunks = bcc_chunks([f"test+{i}@example.com" for i in range(100)])

        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 98)
        self.assertTrue(all(len(chunk) <= 98 for chunk in chunks))


@override_settings(BREVO_API_KEY="test-key")
class SendTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="test+sender@example.com",
            first_name="Send",
            last_name="Er",
        )
        self.other = User.objects.create_user(
            email="test+roster@example.com",
            first_name="Roster",
            last_name="Member",
        )
        User.objects.create_user(
            email="test+inactive@example.com",
            first_name="Inactive",
            last_name="Member",
            is_active=False,
        )
        self.schedule = Schedule.objects.create(
            name="October",
            date=date(2026, 10, 1),
            user=self.user,
        )
        for name in ("Sunday AM", "Sunday PM", "Wednesday", "Other"):
            Service.objects.create(name=name, day_of_week=0, start_time="09:00")
        self.template = EmailTemplate.objects.create(
            name="Published",
            subject="{{month}} {{year}} schedule",
            body="The {{month}} schedule is attached.",
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def _capture_send(self):
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
            captured["key"] = request.get_header("Api-key")
            return Response()

        return captured, fake_urlopen

    @patch("schedules.services.pdf.pdfkit.from_string", return_value=b"%PDF-test")
    def test_send_bccs_active_users_and_attaches_the_pdf(self, _pdf):
        captured, fake_urlopen = self._capture_send()
        with patch("messaging.services.brevo.urllib.request.urlopen", fake_urlopen):
            response = self.client.post(
                "/messages/email/send/",
                {"schedule": self.schedule.pk, "template": self.template.pk},
            )

        sent = SentEmail.objects.get()
        self.assertRedirects(response, f"/messages/email/sent/{sent.pk}/")
        self.assertEqual(sent.subject, "October 2026 schedule")
        self.assertEqual(sent.body, "The October schedule is attached.")
        self.assertEqual(
            sent.recipients, "test+sender@example.com\ntest+roster@example.com"
        )
        self.assertEqual(sent.sent_by, self.user)
        body = captured["body"]
        self.assertEqual(body["to"], [{"email": FROM_EMAIL}])
        self.assertEqual(
            body["bcc"],
            [
                {"email": "test+sender@example.com"},
                {"email": "test+roster@example.com"},
            ],
        )
        self.assertNotIn("test+inactive@example.com", json.dumps(body["bcc"]))
        self.assertEqual(body["sender"]["email"], "olsenparkannouncements@gmail.com")
        self.assertEqual(body["sender"]["name"], "Olsen Park")
        self.assertEqual(body["attachment"][0]["name"], "schedule-10-2026.pdf")
        self.assertEqual(
            base64.b64decode(body["attachment"][0]["content"]), b"%PDF-test"
        )
        self.assertEqual(captured["key"], "test-key")
        self.assertEqual(render_schedule_pdf(self.schedule), b"%PDF-test")

    def test_compose_partial_fixes_the_schedule(self):
        response = self.client.get(
            f"/messages/email/compose/?schedule={self.schedule.pk}"
        )

        self.assertContains(response, "Cancel")
        self.assertContains(response, "Send test email")
        self.assertContains(response, 'name="test_email"')
        self.assertContains(response, self.schedule.name)
        self.assertContains(response, f'value="{self.schedule.pk}"')

    def test_month_page_offers_send(self):
        response = self.client.get(f"/schedules/{self.schedule.pk}/")

        self.assertContains(response, "Send schedule")
        self.assertContains(
            response,
            f"/messages/email/compose/?schedule={self.schedule.pk}",
        )

    def test_new_email_lists_the_active_roster(self):
        response = self.client.get("/messages/email/new/")

        self.assertContains(response, "Send test email")
        self.assertContains(response, 'name="test_email"')
        self.assertContains(response, "every active member")
        self.assertContains(response, "test+roster@example.com")
        self.assertNotContains(response, "test+inactive@example.com")

    @patch("schedules.services.pdf.pdfkit.from_string", return_value=b"%PDF-test")
    def test_failed_send_leaves_no_row(self, _pdf):
        def fake_urlopen(request, timeout=30):
            raise urllib.error.HTTPError(
                "https://api.brevo.com/v3/smtp/email",
                400,
                "bad",
                HTTPMessage(),
                io.BytesIO(b'{"message":"no"}'),
            )

        with patch("messaging.services.brevo.urllib.request.urlopen", fake_urlopen):
            response = self.client.post(
                "/messages/email/send/",
                {"schedule": self.schedule.pk, "template": self.template.pk},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SentEmail.objects.count(), 0)
        self.assertContains(response, "no", status_code=400)

    @patch("schedules.services.pdf.pdfkit.from_string", return_value=b"%PDF-test")
    def test_send_test_goes_only_to_the_typed_address(self, _pdf):
        captured, fake_urlopen = self._capture_send()
        with patch("messaging.services.brevo.urllib.request.urlopen", fake_urlopen):
            response = self.client.post(
                "/messages/email/send-test/",
                {
                    "schedule": self.schedule.pk,
                    "template": self.template.pk,
                    "test_email": "test+one@example.com",
                },
            )

        sent = SentEmail.objects.get()
        self.assertRedirects(response, f"/messages/email/sent/{sent.pk}/")
        self.assertEqual(sent.recipients, "test+one@example.com")
        self.assertEqual(captured["body"]["to"], [{"email": "test+one@example.com"}])
        self.assertNotIn("bcc", captured["body"])
        self.assertNotIn("test+roster@example.com", json.dumps(captured["body"]["to"]))

    @patch("schedules.services.pdf.pdfkit.from_string", return_value=b"%PDF-test")
    def test_send_ignores_the_test_address(self, _pdf):
        captured, fake_urlopen = self._capture_send()
        with patch("messaging.services.brevo.urllib.request.urlopen", fake_urlopen):
            self.client.post(
                "/messages/email/send/",
                {
                    "schedule": self.schedule.pk,
                    "template": self.template.pk,
                    "test_email": "test+one@example.com",
                },
            )

        self.assertEqual(captured["body"]["to"], [{"email": FROM_EMAIL}])
        self.assertNotIn("test+one@example.com", json.dumps(captured["body"]))

    def test_send_test_rejects_anything_but_one_address(self):
        def fake_urlopen(request, timeout=30):
            raise AssertionError("invalid test address must not call Brevo")

        with patch("messaging.services.brevo.urllib.request.urlopen", fake_urlopen):
            for address in ("", "not-an-email", "a@b.com, c@d.com", "a@b.com c@d.com"):
                response = self.client.post(
                    "/messages/email/send-test/",
                    {
                        "schedule": self.schedule.pk,
                        "template": self.template.pk,
                        "test_email": address,
                    },
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(SentEmail.objects.count(), 0)
        self.assertContains(response, "Enter one email address.", status_code=400)

    def test_preview_does_not_send(self):
        def fake_urlopen(request, timeout=30):
            raise AssertionError("preview must not call Brevo")

        with patch("messaging.services.brevo.urllib.request.urlopen", fake_urlopen):
            response = self.client.post(
                "/messages/email/preview/",
                {"schedule": self.schedule.pk, "template": self.template.pk},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["subject"], "October 2026 schedule")
        self.assertIn("Roster Member <test+roster@example.com>", payload["recipients"])
        self.assertNotIn(
            "Inactive Member <test+inactive@example.com>", payload["recipients"]
        )
        self.assertEqual(SentEmail.objects.count(), 0)

    @override_settings(BREVO_API_KEY="")
    @patch("schedules.services.pdf.pdfkit.from_string", return_value=b"%PDF-test")
    def test_missing_key_does_not_call_brevo(self, _pdf):
        def fake_urlopen(request, timeout=30):
            raise AssertionError("missing key must not call Brevo")

        with patch("messaging.services.brevo.urllib.request.urlopen", fake_urlopen):
            response = self.client.post(
                "/messages/email/send/",
                {"schedule": self.schedule.pk, "template": self.template.pk},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SentEmail.objects.count(), 0)
        self.assertContains(response, "Email is not configured.", status_code=400)


class PageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="test+pages@example.com",
            first_name="Page",
            last_name="User",
        )

    def test_anonymous_messages_redirect_to_login(self):
        response = self.client.get("/messages/email/reminders/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
        self.assertIn("/messages/email/reminders/", response.url)

    def test_messages_link_is_on_the_schedule_list(self):
        self.client.force_login(self.user)
        response = self.client.get("/schedules/")

        self.assertContains(response, 'href="/messages/email/new/"')

    def test_reminders_page(self):
        self.client.force_login(self.user)
        response = self.client.get("/messages/email/reminders/")

        self.assertContains(response, "not set up yet")

    def test_create_template(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/messages/email/templates/new/",
            {
                "name": "Weekly",
                "subject": "{{month}}",
                "body": "Hello {{year}}",
            },
        )

        self.assertRedirects(response, "/messages/email/templates/")
        template = EmailTemplate.objects.get(name="Weekly")
        self.assertEqual(template.created_by, self.user)
        self.assertEqual(template.subject, "{{month}}")

    def test_sent_time_renders_in_central_time(self):
        User = get_user_model()
        schedule = Schedule.objects.create(
            name="October",
            date=date(2026, 10, 1),
            user=self.user,
        )
        template = EmailTemplate.objects.create(
            name="Published",
            subject="Hello",
            body="Body",
            created_by=self.user,
        )
        sent = SentEmail.objects.create(
            schedule=schedule,
            template=template,
            subject="Hello",
            body="Body",
            sent_by=self.user,
            recipients="test+one@example.com",
        )
        SentEmail.objects.filter(pk=sent.pk).update(
            sent_at=datetime(2026, 11, 1, 21, 12, tzinfo=datetime_timezone.utc)
        )
        self.client.force_login(self.user)

        list_response = self.client.get("/messages/email/sent/")
        detail_response = self.client.get(f"/messages/email/sent/{sent.pk}/")

        self.assertContains(list_response, "3:12 p.m.")
        self.assertNotContains(list_response, "9:12 p.m.")
        self.assertContains(detail_response, "3:12 p.m.")
        self.assertNotContains(detail_response, "9:12 p.m.")
