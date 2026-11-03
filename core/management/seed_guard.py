from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class SeedCommand(BaseCommand):
    """Seed data. Refuses to run when DEBUG is false unless --force is passed."""

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even when DEBUG is false.",
        )

    def execute(self, *args, **options):
        if not settings.DEBUG and not options.get("force"):
            raise CommandError(
                "Refusing to seed while DEBUG is false. Pass --force to run on a host."
            )
        return super().execute(*args, **options)
