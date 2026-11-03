import django.db.models.deletion
from django.db import migrations, models


def cascade_group(related_name):
    return models.ForeignKey(
        on_delete=django.db.models.deletion.CASCADE,
        related_name=related_name,
        to="users.group",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("schedules", "0007_group_scope"),
        ("users", "0003_remove_group_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="service",
            name="group",
            field=cascade_group("services"),
        ),
        migrations.AlterField(
            model_name="task",
            name="group",
            field=cascade_group("tasks"),
        ),
        migrations.AlterField(
            model_name="taskpreference",
            name="group",
            field=cascade_group("task_preferences"),
        ),
        migrations.AlterField(
            model_name="schedule",
            name="group",
            field=cascade_group("schedules"),
        ),
        migrations.AlterField(
            model_name="assignment",
            name="group",
            field=cascade_group("assignments"),
        ),
    ]
