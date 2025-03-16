from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from pathlib import Path
import json
import csv
from schedules.models import Service, Task, Assignment, TaskPreference
from users.models import User

from decouple import config


class Command(BaseCommand):
    help = "Seeds initial data into the database"

    def handle(self, *args, **kwargs):
        self.base_path = (Path(__file__).resolve().parent.parent.parent) / "fixtures"

        self.upsert_users()
        self.seed_services()
        self.seed_tasks()
        self.seed_assignments()
        self.seed_task_preferences()

    def upsert_users(self):
        """
        This function seeds users from a CSV file into the database.

        The CSV file should have the following columns:
        - name
        - email
        - date_joined
        - phone
        """
        self.stdout.write("Updating Users")
        csv_path = self.base_path / "men.csv"
        parsed_users = []
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                last_name, first_name = row["name"].split(", ")
                parsed_users.append(
                    User(
                        email=row["email"],
                        first_name=first_name,
                        last_name=last_name,
                        password=config("DEFAULT_USER_PASSWORD"),
                        date_joined=datetime.strptime(
                            row["date_joined"], "%Y-%m-%d"
                        ).replace(tzinfo=timezone.utc),
                        # phone=row["phone"],
                    )
                )

        # filter out users that already exist
        existing_emails = set(User.objects.values_list("email", flat=True))

        for user in parsed_users:
            if not user.email in existing_emails:
                if user.email == "sam.tipton@gmail.com":
                    obj = User.objects.create_superuser(
                        email=user.email,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        date_joined=user.date_joined,
                        password=config("MY_PASSWORD"),
                    )
                else:
                    obj = User.objects.create_user(
                        email=user.email,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        date_joined=user.date_joined,
                        password=user.password,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Created User: {str(obj)}"))

        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_services(self):
        self.stdout.write("Updating Services")
        services = [
            {"name": "1st Service 9:00", "day_of_week": 0, "start_time": "14:00"},
            {"name": "2nd Service 10:30", "day_of_week": 0, "start_time": "15:30"},
            {"name": "Wednesday", "day_of_week": 3, "start_time": "00:00"},
            {"name": "Weekly", "day_of_week": None, "start_time": "00:00"},
        ]
        for service in services:
            srv, created = Service.objects.get_or_create(**service)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Service: {srv}"))

        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_tasks(self):
        self.stdout.write("Updating Tasks")

        # Read task IDs and service information from service-times.csv
        service_times_path = self.base_path / "service-times.csv"
        task_ids = []
        service_task_map = {}

        with open(service_times_path, "r") as f:
            reader = csv.reader(f)
            # First row contains task IDs
            header = next(reader)
            task_ids = header[1:]  # Skip the first column which is empty

            # Read service to task mapping
            for row in reader:
                service_name = row[0]
                service_task_map[service_name] = {}
                for i, value in enumerate(row[1:], 1):
                    if value == "1":
                        service_task_map[service_name][header[i]] = True

        # Read task names from duty-names.csv
        duty_names_path = self.base_path / "duty-names.csv"
        task_names = {}

        with open(duty_names_path, "r") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if len(row) >= 2:
                    task_id = row[0]
                    task_name = row[1]
                    task_names[task_id] = task_name

        # Read time periods from duty-codes.csv
        duty_codes_path = self.base_path / "duty-codes.csv"
        time_periods = {}

        with open(duty_codes_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            time_period_row = next(reader)
            for i, task_id in enumerate(header):
                time_periods[task_id] = time_period_row[i]

        # Read exclusions from exclusions.csv
        exclusions_path = self.base_path / "exclusions.csv"
        task_exclusions = {}

        with open(exclusions_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            task_ids_in_exclusions = header[1:]  # Skip the first column

            for row in reader:
                task_id = row[0]
                task_exclusions[task_id] = []

                for i, value in enumerate(row[1:], 0):
                    if value == "1":
                        excluded_task_id = task_ids_in_exclusions[i]
                        task_exclusions[task_id].append(excluded_task_id)

        # Get existing services
        services = {service.name: service for service in Service.objects.all()}

        # Create or update tasks
        created_tasks = []
        for task_id in task_ids:
            if task_id == "lords_supper_prep":
                continue

            # Find which service this task belongs to
            service_name = None
            for svc_name, tasks in service_task_map.items():
                if task_id in tasks:
                    service_name = svc_name
                    break

            if not service_name or service_name not in services:
                self.stdout.write(
                    self.style.WARNING(f"Service not found for task: {task_id}")
                )
                continue

            task_name = task_names.get(task_id, f"Unknown Task ({task_id})")
            time_period = time_periods.get(task_id, Task.SUNDAY)  # Default to Sunday

            # Create or update the task
            task, created = Task.objects.get_or_create(
                id=task_id,
                name=task_name,
                description="",
                service=services[service_name],
                time_period=time_period,
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Task: {task}"))

            created_tasks.append(task)

        # Add exclusions
        for task in created_tasks:
            if task.id in task_exclusions:
                for excluded_task_id in task_exclusions[task.id]:
                    excluded_task = Task.objects.filter(id=excluded_task_id).first()
                    if (
                        excluded_task
                        and not task.excludes.filter(id=excluded_task_id).exists()
                    ):
                        task.excludes.add(excluded_task)

        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_assignments(self):
        self.stdout.write("Updating Assignments")
        json_path = self.base_path / "previous-assignments.json"

        with open(json_path, "r") as f:
            assignments_data = json.load(f)

            # Get all users by full name (last_name, first_name)
            users = User.objects.all()
            user_map = {}
            for user in users:
                full_name = f"{user.last_name}, {user.first_name}"
                user_map[full_name] = user

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

                    # Convert date string to datetime (at 12:00 UTC)
                    try:
                        assigned_at = datetime.strptime(date_str, "%Y-%m-%d").replace(
                            tzinfo=timezone.utc
                        )
                    except ValueError:
                        self.stdout.write(
                            self.style.WARNING(f"Invalid date format in key: {key}")
                        )
                        skipped_count += 1
                        continue

                    # Find the user
                    if user_full_name not in user_map:
                        self.stdout.write(
                            self.style.WARNING(f"User not found: {user_full_name}")
                        )
                        skipped_count += 1
                        continue

                    user = user_map[user_full_name]

                    # Find the task
                    if task_id not in task_map:
                        self.stdout.write(
                            self.style.WARNING(f"Task not found: {task_id}")
                        )
                        skipped_count += 1
                        continue

                    task = task_map[task_id]

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

        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_task_preferences(self):
        self.stdout.write("Updating Task Preferences")

        # Read preferences from prefs.csv
        prefs_path = self.base_path / "prefs.csv"

        # Read update history from prefs_update_history.csv
        update_history_path = self.base_path / "prefs_update_history.csv"

        # Read biases from biases.csv
        biases_path = self.base_path / "biases.csv"

        # Get all users by full name (last_name, first_name)
        users = User.objects.all()
        user_map = {}
        for user in users:
            full_name = f"{user.last_name}, {user.first_name}"
            user_map[full_name] = user

        # Get all tasks by ID
        tasks = Task.objects.all()
        task_map = {task.id: task for task in tasks}

        # Read preferences data
        preferences = {}
        with open(prefs_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            task_ids = header[1:]  # Skip the first column which is the user name

            for row in reader:
                if len(row) <= 1:
                    continue

                user_full_name = row[0].strip('"')
                if user_full_name not in user_map:
                    self.stdout.write(
                        self.style.WARNING(f"User not found: {user_full_name}")
                    )
                    continue

                user = user_map[user_full_name]
                preferences[user_full_name] = {}

                for i, value in enumerate(row[1:], 0):
                    if i >= len(task_ids):
                        break

                    task_id = task_ids[i]
                    if task_id not in task_map:
                        continue

                    if value == "1":
                        preferences[user_full_name][task_id] = 1.0

        # Read update history data
        update_history = {}
        with open(update_history_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            task_ids = header[1:]  # Skip the first column which is the user name

            for row in reader:
                if len(row) <= 1:
                    continue

                user_full_name = row[0].strip('"')
                if user_full_name not in user_map:
                    continue

                update_history[user_full_name] = {}

                for i, value in enumerate(row[1:], 0):
                    if i >= len(task_ids):
                        break

                    task_id = task_ids[i]
                    if task_id not in task_map:
                        continue

                    if value:
                        try:
                            update_date = datetime.strptime(value, "%Y-%m-%d").date()
                            update_history[user_full_name][task_id] = update_date
                        except ValueError:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Invalid date format in update history: {value}"
                                )
                            )

        # Read biases data
        biases = {}
        with open(biases_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            task_ids = header[1:]  # Skip the first column which is the user name

            for row in reader:
                if len(row) <= 1:
                    continue

                user_full_name = row[0].strip('"')
                if user_full_name not in user_map:
                    continue

                biases[user_full_name] = {}

                for i, value in enumerate(row[1:], 0):
                    if i >= len(task_ids):
                        break

                    task_id = task_ids[i]
                    if task_id not in task_map:
                        continue

                    if value:
                        try:
                            bias_value = float(value)
                            biases[user_full_name][task_id] = bias_value
                        except ValueError:
                            self.stdout.write(
                                self.style.WARNING(f"Invalid bias value: {value}")
                            )

        # Create or update TaskPreference objects
        created_count = 0
        updated_count = 0
        skipped_count = 0

        default_update_date = datetime(2024, 7, 1).date()

        for user_full_name, user_prefs in preferences.items():
            if user_full_name not in user_map:
                skipped_count += 1
                continue

            user = user_map[user_full_name]

            for task_id, pref_value in user_prefs.items():
                if task_id not in task_map:
                    skipped_count += 1
                    continue

                task = task_map[task_id]

                # Apply bias if available
                final_value = pref_value
                if user_full_name in biases and task_id in biases[user_full_name]:
                    bias_value = biases[user_full_name][task_id]
                    final_value = pref_value * bias_value

                # Get update date if available
                updated_at = default_update_date
                if (
                    user_full_name in update_history
                    and task_id in update_history[user_full_name]
                ):
                    updated_at = update_history[user_full_name][task_id]

                # Create or update the TaskPreference
                try:
                    try:
                        task_pref_before = TaskPreference.objects.get(
                            user=user, task=task
                        )
                    except TaskPreference.DoesNotExist:
                        task_pref_before = None

                    task_pref, created = TaskPreference.objects.update_or_create(
                        user=user,
                        task=task,
                        defaults={
                            "value": final_value,
                            "updated_at": updated_at,
                        },
                    )

                    if task_pref_before is None:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"Created TaskPreference: {task_pref}")
                        )
                    elif task_pref_before != task_pref:
                        self.stdout.write(
                            self.style.SUCCESS(f"Updated TaskPreference: {task_pref}")
                        )
                        updated_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error creating TaskPreference for {user_full_name} - {task_id}: {str(e)}"
                        )
                    )
                    skipped_count += 1

        self.stdout.write(
            f"Created {created_count} TaskPreferences, updated {updated_count}, skipped {skipped_count}"
        )

        self.stdout.write(self.style.SUCCESS("Done."))
