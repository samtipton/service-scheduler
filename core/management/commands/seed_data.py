from django.core.management import call_command

from core.management.seed_guard import SeedCommand


class Command(SeedCommand):
    help = "Seeds all data into the database by calling individual seed commands"

    def handle(self, *args, **options):
        self.stdout.write("Starting data seeding process...")
        force = options.get("force", False)
        for name in (
            "seed_users",
            "seed_services",
            "seed_tasks",
            "seed_schedules",
            "seed_assignments",
            "seed_task_preferences",
            "init_assignment_stats",
        ):
            call_command(name, force=force)
