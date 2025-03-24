from django.core.management.base import BaseCommand
from django.db import transaction
from schedules.models import Task, AssignmentStats
from decimal import Decimal


class Command(BaseCommand):
    help = "Initialize assignment statistics for all user/task combinations"

    def handle(self, *args, **options):
        self.stdout.write("Updating Assignment Statistics")
        self.init_assignment_stats()
        self.stdout.write(self.style.SUCCESS("Done."))

    def init_assignment_stats(self):
        # Get all users and tasks
        tasks = Task.objects.all()

        stats_created = 0
        stats_updated = 0

        with transaction.atomic():
            for task in tasks:
                # Get eligible users for this task
                eligible_users = task.get_eligible_users()
                if not eligible_users.exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"No eligible users found for task: {task.name}"
                        )
                    )
                    continue

                # Calculate ideal average for this task
                ideal_avg = Decimal("1.0") / Decimal(len(eligible_users))

                # Create or update stats for each eligible user
                for user in eligible_users:
                    stats, created = AssignmentStats.objects.get_or_create(
                        user=user, task=task
                    )
                    if not created:
                        stats_updated += 1
                    else:
                        stats_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully initialized assignment statistics:\n"
                f"- Created: {stats_created} new stats\n"
                f"- Updated: {stats_updated} existing stats"
            )
        )
