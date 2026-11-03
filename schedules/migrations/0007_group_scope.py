import django.db.models.deletion
from django.db import migrations, models


def backfill_groups(apps, schema_editor):
    Group = apps.get_model("users", "Group")
    Membership = apps.get_model("users", "Membership")
    User = apps.get_model("users", "User")
    production, _ = Group.objects.get_or_create(
        slug="production", defaults={"name": "Olsen Park"}
    )
    for user in User.objects.all():
        role = "admin" if user.is_superuser or user.is_staff else "scheduler"
        Membership.objects.get_or_create(
            user_id=user.id, group_id=production.id, defaults={"role": role}
        )
    for model_name in ("Service", "Task", "TaskPreference", "Schedule", "Assignment"):
        model = apps.get_model("schedules", model_name)
        model.objects.filter(group__isnull=True).update(group_id=production.id)


def group_field(related_name, null):
    return models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name=related_name,
        to="users.group",
        null=null,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("schedules", "0006_taskrequires"),
        ("users", "0002_group_and_membership"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="group",
            field=group_field("services", True),
        ),
        migrations.AddField(
            model_name="task",
            name="group",
            field=group_field("tasks", True),
        ),
        migrations.AddField(
            model_name="taskpreference",
            name="group",
            field=group_field("task_preferences", True),
        ),
        migrations.AddField(
            model_name="schedule",
            name="group",
            field=group_field("schedules", True),
        ),
        migrations.AddField(
            model_name="assignment",
            name="group",
            field=group_field("assignments", True),
        ),
        migrations.RunPython(backfill_groups, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="service",
            name="group",
            field=group_field("services", False),
        ),
        migrations.AlterField(
            model_name="task",
            name="group",
            field=group_field("tasks", False),
        ),
        migrations.AlterField(
            model_name="taskpreference",
            name="group",
            field=group_field("task_preferences", False),
        ),
        migrations.AlterField(
            model_name="schedule",
            name="group",
            field=group_field("schedules", False),
        ),
        migrations.AlterField(
            model_name="assignment",
            name="group",
            field=group_field("assignments", False),
        ),
    ]
