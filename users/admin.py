from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from schedules.models import TaskPreference
from .models import User


class TaskPreferenceInline(admin.TabularInline):
    model = TaskPreference
    extra = 1


class CustomUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "assignment_count", "is_active")
    search_fields = ("email", "first_name", "last_name")
    ordering = ["email"]

    fieldsets = (
        (None, {"fields": ("first_name", "last_name", "email")}),
        ("Username & Password", {"fields": ("username", "password")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
    )

    inlines = (TaskPreferenceInline,)


admin.site.register(User, CustomUserAdmin)
