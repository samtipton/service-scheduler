from django.core.management.base import CommandError

from core.management.seed_guard import SeedCommand
from schedules.models import Service
from users.access import sole_group


class Command(SeedCommand):
    help = "Seeds services into the database"

    def handle(self, *args, **options):
        self.stdout.write("Updating Services")
        self.seed_services()
        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_services(self):
        group = sole_group()
        if group is None:
            raise CommandError(
                "Create one group before seeding services. Refusing to guess when there are zero or several."
            )
        services = [
            {"name": "1st Service 9:00", "day_of_week": 0, "start_time": "14:00", "group": group},
            {"name": "2nd Service 10:30", "day_of_week": 0, "start_time": "15:30", "group": group},
            {"name": "Wednesday", "day_of_week": 3, "start_time": "00:00", "group": group},
            {"name": "Weekly", "day_of_week": None, "start_time": "00:00", "group": group},
        ]
        for service in services:
            srv, created = Service.objects.get_or_create(**service)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Service: {srv}"))
