from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("schedules", "0008_cascade_group_delete"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="schedule",
            name="base_schedule",
        ),
        migrations.RemoveField(
            model_name="schedule",
            name="is_official",
        ),
    ]
