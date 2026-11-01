from django.contrib import admin

from messaging.models import EmailTemplate, SentEmail


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "subject", "created_by", "updated_at")
    search_fields = ("name", "subject")


@admin.register(SentEmail)
class SentEmailAdmin(admin.ModelAdmin):
    list_display = ("subject", "schedule", "sent_by", "sent_at")
    readonly_fields = (
        "schedule",
        "template",
        "subject",
        "body",
        "sent_at",
        "sent_by",
        "recipients",
    )
