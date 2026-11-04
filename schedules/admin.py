from django.contrib import admin
from .models import (
    AssignmentStats,
    Service,
    Task,
    Assignment,
    TaskPreference,
    TaskRequires,
    Schedule,
)


@admin.register(TaskPreference)
class TaskPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "task_id", "value")

    search_fields = ("user__first_name", "user__last_name", "task__name")


@admin.register(TaskRequires)
class TaskRequiresAdmin(admin.ModelAdmin):
    list_display = ("user", "task", "requires")
    list_filter = ("task", "requires")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "task__id",
        "requires__id",
    )


class TaskExcludesInline(admin.TabularInline):
    model = Task.excludes.through
    extra = 1
    verbose_name = "Excluded Task"
    verbose_name_plural = "Excluded Tasks"
    fk_name = "from_task"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "service", "order", "rotation_group")
    list_filter = ("service", "rotation_group")
    search_fields = ("id", "name", "service__name", "rotation_group")

    ordering = ("order", "id")
    fieldsets = (
        (None, {"fields": ("id", "name", "service", "order", "rotation_group")}),
    )

    inlines = (TaskExcludesInline,)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("task", "user", "assigned_at", "schedule")
    list_filter = ("task__service", "user", "assigned_at", "schedule")
    search_fields = ("task__name", "user__username", "schedule__name")
    readonly_fields = ("schedule",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "day_of_week", "start_time")
    list_filter = ("day_of_week",)
    search_fields = ("name",)


@admin.register(AssignmentStats)
class AssignmentStatsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "task",
        "ideal_average",
        "actual_average",
        "assignment_delta",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "task__name",
        "schedule",
    )
    list_filter = ("user", "task", "schedule")

    class Meta:
        verbose_name = "Assignment Stats"
        verbose_name_plural = "Assignment Stats"


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0
    fields = ["user", "task", "assigned_at"]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "date", "user", "created_at")
    list_filter = ("date", "user")
    search_fields = ("name", "description")
    date_hierarchy = "date"
    inlines = (AssignmentInline,)
