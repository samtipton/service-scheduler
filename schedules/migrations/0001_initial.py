# Generated by Django 5.1.7 on 2025-03-30 01:32

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Service",
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
                ("name", models.CharField(max_length=100)),
                (
                    "day_of_week",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(6),
                        ],
                    ),
                ),
                ("start_time", models.TimeField()),
            ],
            options={
                "ordering": [
                    models.Case(
                        models.When(day_of_week__isnull=True, then=models.Value(999)),
                        default="day_of_week",
                        output_field=models.IntegerField(),
                    ),
                    "start_time",
                ],
            },
        ),
        migrations.CreateModel(
            name="Schedule",
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
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "date",
                    models.DateField(
                        help_text="The month and year this schedule is for"
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "is_official",
                    models.BooleanField(
                        default=False,
                        help_text="Whether this schedule is selected as the official schedule for the month",
                    ),
                ),
                (
                    "base_schedule",
                    models.ForeignKey(
                        blank=True,
                        help_text="Previous schedule this one builds upon",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="derived_schedules",
                        to="schedules.schedule",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User who created this schedule",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="created_schedules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Task",
            fields=[
                (
                    "id",
                    models.CharField(
                        max_length=64, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                (
                    "time_period",
                    models.CharField(
                        choices=[
                            ("0", "Sunday"),
                            ("1", "Monday"),
                            ("2", "Tuesday"),
                            ("3", "Wednesday"),
                            ("4", "Thursday"),
                            ("5", "Friday"),
                            ("6", "Saturday"),
                            ("w", "Weekly"),
                            ("m", "Monthly"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "order",
                    models.IntegerField(default=0, help_text="Used for ordering tasks"),
                ),
                ("excludes", models.ManyToManyField(blank=True, to="schedules.task")),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="tasks",
                        to="schedules.service",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="Assignment",
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
                ("assigned_at", models.DateTimeField(db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="past_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "schedule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="schedules.schedule",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        to="schedules.task",
                    ),
                ),
            ],
            options={
                "ordering": ["-assigned_at"],
            },
        ),
        migrations.CreateModel(
            name="TaskPreference",
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
                    "value",
                    models.FloatField(
                        validators=[django.core.validators.MinValueValidator(0.0)]
                    ),
                ),
                ("updated_at", models.DateField(auto_now_add=True)),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        to="schedules.task",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
                "unique_together": {("user", "task")},
            },
        ),
        migrations.AddField(
            model_name="task",
            name="users_with_preferences",
            field=models.ManyToManyField(
                related_name="tasks_with_preferences",
                through="schedules.TaskPreference",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="AssignmentStats",
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
                    "ideal_average",
                    models.DecimalField(decimal_places=8, max_digits=16, null=True),
                ),
                (
                    "actual_average",
                    models.DecimalField(decimal_places=8, max_digits=16, null=True),
                ),
                (
                    "assignment_delta",
                    models.DecimalField(decimal_places=8, max_digits=9, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignment_stats",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "schedule",
                    models.ManyToManyField(
                        related_name="assignment_stats", to="schedules.schedule"
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignment_stats",
                        to="schedules.task",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "get_latest_by": "created_at",
                "indexes": [
                    models.Index(
                        fields=["user", "task"], name="schedules_a_user_id_3351a8_idx"
                    ),
                    models.Index(
                        fields=["task", "user"], name="schedules_a_task_id_6202ff_idx"
                    ),
                    models.Index(
                        fields=["created_at"], name="schedules_a_created_96571d_idx"
                    ),
                ],
            },
        ),
    ]
