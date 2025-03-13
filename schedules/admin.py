from django.contrib import admin
from .models import Service, Task, Assignment, TaskPreference

# Register your models here.

admin.site.register(Service)
admin.site.register(Task)
admin.site.register(Assignment)
admin.site.register(TaskPreference)
