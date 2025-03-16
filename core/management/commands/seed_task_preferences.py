from datetime import datetime
from django.core.management.base import BaseCommand
from pathlib import Path
import csv
from schedules.models import Task, TaskPreference
from users.models import User


class Command(BaseCommand):
    help = "Seeds task preferences into the database from CSV files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixtures-path",
            type=str,
            help="Path to the fixtures directory containing CSV files",
        )

    def handle(self, *args, **options):
        if options["fixtures_path"]:
            self.base_path = Path(options["fixtures_path"])
        else:
            self.base_path = (
                Path(__file__).resolve().parent.parent.parent
            ) / "fixtures"

        self.stdout.write("Updating Task Preferences")
        self.seed_task_preferences()
        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_task_preferences(self):
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
