from django.db import migrations, models

ROTATION_FAMILIES = {
    "song": (
        "first_song_leader",
        "song_leader",
        "wednesday_song_leader",
    ),
    "prayer": (
        "first_opening_prayer",
        "opening_prayer",
        "closing_prayer",
        "wednesday_opening_prayer",
        "wednesday_closing_prayer",
    ),
    "lords_supper": (
        "table_lead_bread",
        "table_lead_cup",
        "table_aid_bread",
        "table_aid_cup",
    ),
}


def set_rotation_groups(apps, schema_editor):
    Task = apps.get_model("schedules", "Task")
    for group, task_ids in ROTATION_FAMILIES.items():
        Task.objects.filter(pk__in=task_ids).update(rotation_group=group)


class Migration(migrations.Migration):

    dependencies = [
        ("schedules", "0004_auto_20250615_2247"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="rotation_group",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Tasks that share this label are one family for adjacent-week "
                    "rotation (e.g. Sunday and Wednesday song leader). Blank means "
                    "no family."
                ),
                max_length=32,
            ),
        ),
        migrations.RunPython(set_rotation_groups, migrations.RunPython.noop),
    ]
