from datetime import datetime, timezone
from pathlib import Path
import csv

from decouple import config

from django.core.management.base import CommandError

from core.management.seed_guard import SeedCommand
from users.access import sole_group
from users.models import Membership, User


class Command(SeedCommand):
    help = "Seeds users into the database from CSV"

    def add_arguments(self, parser):
        super().add_arguments(parser)
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

        group = sole_group()
        if group is None:
            raise CommandError(
                "Create one group before seeding users. Refusing to guess when there are zero or several."
            )
        for user in parsed_users:
            obj = User.objects.filter(email=user.email).first()
            if obj is None:
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
            role = (
                Membership.ADMIN
                if obj.is_superuser or obj.is_staff
                else Membership.SCHEDULER
            )
            Membership.objects.get_or_create(
                user=obj, group=group, defaults={"role": role}
            )
