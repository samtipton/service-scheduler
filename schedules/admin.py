from django.contrib import admin
from .models import Service, Task, Assignment, TaskPreference


@admin.register(TaskPreference)
class TaskPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "task_id", "value")


class TaskExcludesInline(admin.TabularInline):
    model = Task.excludes.through
    extra = 1
    verbose_name = "Excluded Task"
    verbose_name_plural = "Excluded Tasks"
    fk_name = "from_task"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "service", "order")
    list_filter = ("service",)
    search_fields = ("id", "name", "service__name")

    ordering = ("order", "id")
    fieldsets = ((None, {"fields": ("id", "name", "service", "order")}),)

    inlines = (TaskExcludesInline,)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("task", "user", "assigned_at")
    list_filter = ("task__service", "user", "assigned_at")
    search_fields = ("task__name", "user__username")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "day_of_week", "start_time")
    list_filter = ("day_of_week",)
    search_fields = ("name",)
