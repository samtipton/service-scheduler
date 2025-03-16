from django.contrib import admin
from .models import Service, Task, Assignment, TaskPreference

# Register your models here.


class TaskPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "task_id", "value")


class TaskExcludesInline(admin.TabularInline):
    model = Task.excludes.through
    extra = 1
    verbose_name = "Excluded Task"
    verbose_name_plural = "Excluded Tasks"
    fk_name = "from_task"


class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "service")

    search_fields = ("id", "name")

    fieldsets = ((None, {"fields": ("id", "name", "service")}),)

    inlines = (TaskExcludesInline,)


class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "task", "assigned_at")
    search_fields = ("user__first_name", "user__last_name", "task__id")
    ordering = ("-assigned_at",)


class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "day_of_week", "start_time")


admin.site.register(Service, ServiceAdmin)
admin.site.register(Task, TaskAdmin)
admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(TaskPreference, TaskPreferenceAdmin)
