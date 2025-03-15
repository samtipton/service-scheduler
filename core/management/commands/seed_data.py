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

        # csv_path = self.base_path / "extra_data.csv"

        # Load CSV data
        # with open(csv_path, "r") as f:
        #     reader = csv.DictReader(f)
        #     for row in reader:
        #         # MyModel.objects.get_or_create(**row)
        #         pass

        self.upsert_users()
        # self.seed_assignments()
        self.stdout.write(self.style.SUCCESS("Successfully seeded data!"))

    def upsert_users(self):
        """
        This function seeds users from a CSV file into the database.

        The CSV file should have the following columns:
        - name
        - email
        - date_joined
        - phone
        """
        csv_path = self.base_path / "men.csv"
        users = []
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                last_name, first_name = row["name"].split(", ")
                users.append(
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

        for user in users:
            if user.email == "sam.tipton@gmail.com":
                # obj = User.objects.create_superuser(
                #     email=user.email,
                #     first_name=user.first_name,
                #     last_name=user.last_name,
                #     date_joined=user.date_joined,
                #     password=config("MY_PASSWORD"),
                # )

                continue
            else:
                obj = User.objects.create_user(
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    date_joined=user.date_joined,
                    password=user.password,
                )
            self.stdout.write(self.style.SUCCESS(f"Created User: {str(obj)}"))

    def seed_services(self):
        pass

    def seed_tasks(self):
        pass

    def seed_assignments(self):
        json_path = self.base_path / "previous-assignments.json"
        print(json_path)
        # Load JSON data
        with open(json_path, "r") as f:
            data = json.load(f)
            for item in data:
                self.stdout.write(self.style.SUCCESS(item))
        pass

    def seed_task_preferences(self):
        pass
