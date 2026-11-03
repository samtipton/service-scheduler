from django.conf import settings
from django.db import models


class EmailTemplate(models.Model):
    name = models.CharField(max_length=120, unique=True)
    subject = models.CharField(
        max_length=200,
        help_text="One line. Placeholders: {{month}} {{year}}",
    )
    body = models.TextField(help_text="Placeholders: {{month}} {{year}}")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="email_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SentEmail(models.Model):
    schedule = models.ForeignKey(
        "schedules.Schedule",
        on_delete=models.CASCADE,
        related_name="sent_emails",
    )
    template = models.ForeignKey(
        EmailTemplate,
        null=True,
        on_delete=models.SET_NULL,
        related_name="sent_emails",
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_emails",
    )
    recipients = models.TextField(
        help_text="Addresses on the request, one per line."
    )

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return self.subject
