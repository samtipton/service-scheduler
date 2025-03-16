from django.core.management.base import BaseCommand
from schedules.models import Service


class Command(BaseCommand):
    help = "Seeds services into the database"

    def handle(self, *args, **options):
        self.stdout.write("Updating Services")
        self.seed_services()
        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_services(self):
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
