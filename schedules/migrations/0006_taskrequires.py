from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("schedules", "0005_task_rotation_group"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaskRequires",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_requires",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="requirements",
                        to="schedules.task",
                    ),
                ),
                (
                    "requires",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="required_by",
                        to="schedules.task",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "task requires",
                "unique_together": {("user", "task", "requires")},
            },
        ),
    ]
