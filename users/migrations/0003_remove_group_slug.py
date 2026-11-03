from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_group_and_membership"),
        ("schedules", "0007_group_scope"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="group",
            name="slug",
        ),
    ]
