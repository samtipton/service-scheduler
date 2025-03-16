from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from pathlib import Path
import csv
from users.models import User
from decouple import config


class Command(BaseCommand):
    help = "Seeds users into the database from CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-path",
            type=str,
            help="Path to the CSV file containing user data",
        )

    def handle(self, *args, **options):
        if options["csv_path"]:
            csv_path = Path(options["csv_path"])
        else:
            base_path = (Path(__file__).resolve().parent.parent.parent) / "fixtures"
            csv_path = base_path / "men.csv"

        self.stdout.write("Updating Users")
        self.upsert_users(csv_path)
        self.stdout.write(self.style.SUCCESS("Done."))

    def upsert_users(self, csv_path):
        """
        This function seeds users from a CSV file into the database.

        The CSV file should have the following columns:
        - name
        - email
        - date_joined
        - phone
        """
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
