from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from pathlib import Path
import json
import calendar
from schedules.models import Service, Task, Assignment
from users.models import User


class WeekIndexError(Exception):
    """Raised when a week index is invalid for the given month."""

    pass


class Command(BaseCommand):
    help = "Seeds assignments into the database from JSON"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set Sunday as the first day of the week
        calendar.setfirstweekday(calendar.SUNDAY)

    def add_arguments(self, parser):
        parser.add_argument(
            "--json-path",
            type=str,
            help="Path to the JSON file containing assignment data",
        )

    def handle(self, *args, **options):
        if options["json_path"]:
            json_path = Path(options["json_path"])
        else:
            base_path = (Path(__file__).resolve().parent.parent.parent) / "fixtures"
            json_path = base_path / "previous-assignments.json"

        self.stdout.write("Updating Assignments")
        self.seed_assignments(json_path)
        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_assignments(self, json_path):
        with open(json_path, "r") as f:
            assignments_data = json.load(f)

            # Get all users by full name (last_name, first_name)
            users = User.objects.all()
            user_map = {}
            for user in users:
                full_name = f"{user.last_name}, {user.first_name}"
                user_map[full_name] = user

            services = Service.objects.all()
            service_days = {
                service.day_of_week
                for service in services
                if service.day_of_week is not None
            }
            # Get all tasks by ID
            tasks = Task.objects.all()
            task_map = {task.id: task for task in tasks}

            # Process each assignment
            created_count = 0
            skipped_count = 0

            for key, user_full_name in assignments_data.items():
                # Parse the key to get date and task_id
                try:
                    parts = key.split("-")
                    if len(parts) < 2:
                        self.stdout.write(
                            self.style.WARNING(f"Invalid key format: {key}")
                        )
                        skipped_count += 1
                        continue

                    # The last part is the task_id, everything before is the date
                    task_id = parts[-1]
                    date_str = "-".join(parts[:-1])

                    # Find the task first to determine if it's a weekly task
                    if task_id not in task_map:
                        self.stdout.write(
                            self.style.WARNING(f"Task not found: {task_id}")
                        )
                        skipped_count += 1
                        continue

                    task = task_map[task_id]

                    # Parse date components
                    date_parts = date_str.split("-")
                    year = int(date_parts[0])
                    month = int(date_parts[1])
                    day = int(date_parts[2])

                    # Check if the day appears in any service day in the month's calendar
                    month_calendar = calendar.monthcalendar(year, month)
                    valid_service_day = False

                    for week in month_calendar:
                        for service_day in service_days:
                            if week[service_day] == day:
                                valid_service_day = True
                                break
                        if valid_service_day:
                            break

                    if not valid_service_day:
                        # Found an instance in 2025-4 where the first week
                        # had incorrect days, so we skip these assignments
                        # and correct manually
                        self.stdout.write(
                            self.style.WARNING(
                                f"Day {day} is not in service days for {year}-{month}"
                            )
                        )
                        skipped_count += 1
                        continue

                    # Regular service task - use the date as is
                    assigned_at = datetime(year, month, day, tzinfo=timezone.utc)

                    # Find the user
                    if user_full_name not in user_map:
                        self.stdout.write(
                            self.style.WARNING(f"User not found: {user_full_name}")
                        )
                        skipped_count += 1
                        continue

                    user = user_map[user_full_name]

                    # Create the assignment if it doesn't exist
                    assignment, created = Assignment.objects.get_or_create(
                        user=user, task=task, assigned_at=assigned_at
                    )

                    if created:
                        created_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing assignment {key}: {str(e)}")
                    )
                    skipped_count += 1

            self.stdout.write(
                f"Created {created_count} Assignments, skipped {skipped_count}"
            )
