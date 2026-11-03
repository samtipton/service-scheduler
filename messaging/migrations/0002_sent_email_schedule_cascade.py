import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("messaging", "0001_email_template_and_sent_email"),
        ("schedules", "0008_cascade_group_delete"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sentemail",
            name="schedule",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sent_emails",
                to="schedules.schedule",
            ),
        ),
    ]
