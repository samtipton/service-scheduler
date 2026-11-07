import calendar
from datetime import datetime, timedelta
import json
from pathlib import Path
import pytz

from django.core.management.base import CommandError

from core.management.seed_guard import SeedCommand
from schedules.models import Schedule
from users.access import sole_group
from users.models import User


class Command(SeedCommand):
    help = "Seeds schedules into the database"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set Sunday as the first day of the week
        calendar.setfirstweekday(calendar.SUNDAY)

    def handle(self, *args, **options):
        self.stdout.write("Updating Schedules")
        base_path = (Path(__file__).resolve().parent.parent.parent) / "fixtures"
        json_path = base_path / "previous-assignments.json"
        self.seed_schedules(json_path)
        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_schedules(self, json_path):
        """
        Get min and max dates from assignments, create a schedule for each month in that range.
        """
        creator = User.objects.get(first_name="Sam", last_name="Tipton")
        group = sole_group()
        if group is None:
            raise CommandError(
                "Create one group before seeding schedules. Refusing to guess when there are zero or several."
            )

        with open(json_path, "r") as f:
            assignments_data = json.load(f)

        min_date = datetime.strptime(
            "-".join(
                min(
                    assignments_data,
                    key=lambda x: datetime.strptime(
                        "-".join(x.split("-")[:-1]), "%Y-%m-%d"
                    ),
                ).split("-")[:-1]
            ),
            "%Y-%m-%d",
        ).date()

        max_date = datetime.strptime(
            "-".join(
                max(
                    assignments_data,
                    key=lambda x: datetime.strptime(
                        "-".join(x.split("-")[:-1]), "%Y-%m-%d"
                    ),
                ).split("-")[:-1]
            ),
            "%Y-%m-%d",
        ).date()

        # Get all year/months between min and max date
        cur = min_date
        cur_datetime = datetime.combine(cur, datetime.min.time())

        while cur < max_date:
            d = {
                "name": f"{calendar.month_name[cur.month].capitalize()} {cur.year}",
                "date": cur,
                "user": creator,
                "group": group,
                "defaults": {
                    "created_at": pytz.utc.localize(cur_datetime - timedelta(days=15)),
                    "updated_at": pytz.utc.localize(cur_datetime - timedelta(days=15)),
                },
            }

            schedule, created = Schedule.objects.get_or_create(**d)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{schedule.user} created schedule {schedule.name} for {schedule.date}"
                    )
                )
            cur = cur.replace(
                day=1,
                month=(cur.month % 12) + 1,
                year=(cur.year + 1 if cur.month == 12 else cur.year),
            )
            cur_datetime = datetime.combine(cur, datetime.min.time())
