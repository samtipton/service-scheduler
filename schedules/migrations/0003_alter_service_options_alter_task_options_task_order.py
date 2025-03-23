# Generated by Django 5.1.7 on 2025-03-23 03:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("schedules", "0002_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="service",
            options={
                "ordering": [
                    models.Case(
                        models.When(day_of_week__isnull=True, then=models.Value(999)),
                        default="day_of_week",
                        output_field=models.IntegerField(),
                    ),
                    "start_time",
                ]
            },
        ),
        migrations.AlterModelOptions(
            name="task",
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddField(
            model_name="task",
            name="order",
            field=models.IntegerField(default=0, help_text="Used for ordering tasks"),
        ),
    ]
