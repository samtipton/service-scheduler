from django.core.management.base import BaseCommand

from schedules.models import Assignment, Schedule, Service, Task, TaskPreference
from schedules.services.compare_dump import (
    LIVE_DUMP_PATH,
    assignment_cutoff,
    dump_compare_db,
)
from users.models import User


class Command(BaseCommand):
    help = (
        "Dump users, services, tasks, prefs, schedules, and the last year of "
        "assignments to schedules/fixtures/compare/live.sql. Names, emails, "
        "and passwords are anonymized so the file is safe to commit. "
        "Then: python manage.py compare_objectives FairJobs --dump"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=str(LIVE_DUMP_PATH),
            help=f"SQL file to write (default {LIVE_DUMP_PATH}).",
        )
        parser.add_argument(
            "--months",
            type=int,
            default=12,
            help="Keep assignments from this many months back (default 12).",
        )

    def handle(self, *args, **options):
        months = options["months"]
        cutoff = assignment_cutoff(months)
        path = dump_compare_db(options["output"], months=months)
        n_asg = Assignment.objects.filter(assigned_at__date__gte=cutoff).count()
        self.stdout.write(
            f"Wrote {path} (anonymized): {User.objects.count()} users, "
            f"{Service.objects.count()} services, {Task.objects.count()} tasks, "
            f"{TaskPreference.objects.count()} prefs, "
            f"{Schedule.objects.count()} schedules, "
            f"{n_asg} assignments since {cutoff.isoformat()}."
        )
