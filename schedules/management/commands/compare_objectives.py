import time

from django.core.management.base import BaseCommand, CommandError
from django.test.runner import DiscoverRunner
from django.test.utils import setup_test_environment, teardown_test_environment

from schedules.services.compare_dump import LIVE_DUMP_PATH, load_compare_dump
from schedules.services.objectives import OBJECTIVES
from schedules.services.year_compare import (
    MONTHS,
    available_worlds,
    run_comparison,
    world_from_database,
)


class Command(BaseCommand):
    help = (
        "Generate months with one or more scheduling objectives and print "
        "fairness metrics. Uses a throwaway test database, not Sunday data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "objectives",
            nargs="*",
            help=(
                "Objective names or unique substrings. "
                f"Default: all ({', '.join(OBJECTIVES)}). "
                "Examples: FairJobs  CatchUpShare"
            ),
        )
        parser.add_argument(
            "--months",
            type=int,
            default=MONTHS,
            help=f"Months to generate per objective (default {MONTHS}).",
        )
        parser.add_argument(
            "--world",
            default="default",
            help=(
                "Roster TOML: a name in schedules/fixtures/compare/ "
                f"({', '.join(available_worlds()) or 'default'}) "
                "or a path to a .toml file."
            ),
        )
        parser.add_argument(
            "--dump",
            action="store_true",
            help=(
                "Seed the test database from "
                f"{LIVE_DUMP_PATH} (anonymized snapshot). "
                "Refresh with dump_compare_db. Ignores --world."
            ),
        )

    def handle(self, *args, **options):
        runner = DiscoverRunner(
            verbosity=int(options["verbosity"]),
            interactive=False,
            keepdb=False,
        )
        setup_test_environment()
        old_config = runner.setup_databases()
        try:
            world = None
            world_path = options["world"]
            if options["dump"]:
                try:
                    load_compare_dump()
                except FileNotFoundError as exc:
                    raise CommandError(str(exc)) from exc
                world = world_from_database()
                world_path = None
            started = {}

            def on_progress(label, done, total):
                if int(options["verbosity"]) < 1:
                    return
                if label not in started:
                    started[label] = time.monotonic()
                width = 28
                filled = int(width * done / total) if total else width
                bar = "#" * filled + "-" * (width - filled)
                elapsed = time.monotonic() - started[label]
                eta = elapsed * (total - done) / done if done else 0
                extra = f"  {elapsed:.0f}s  eta {eta:.0f}s"
                self.stderr.write(
                    f"\r{label} [{bar}] {done}/{total}{extra}", ending=""
                )
                self.stderr.flush()
                if done >= total:
                    self.stderr.write("")

            text, _, _ = run_comparison(
                options["objectives"] or None,
                months=options["months"],
                world=world,
                world_path=world_path,
                on_progress=on_progress,
            )
            self.stdout.write(text)
            self.stdout.flush()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        finally:
            runner.teardown_databases(old_config)
            teardown_test_environment()
