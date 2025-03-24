from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Seeds all data into the database by calling individual seed commands"

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting data seeding process...")

        call_command("seed_users")

        call_command("seed_services")

        call_command("seed_tasks")

        call_command("seed_assignments")

        call_command("seed_task_preferences")

        call_command("init_assignment_stats")
