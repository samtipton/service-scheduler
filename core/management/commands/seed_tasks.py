from django.core.management.base import BaseCommand
from pathlib import Path
import csv
from schedules.models import Service, Task


class Command(BaseCommand):
    help = "Seeds tasks into the database from CSV files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixtures-path",
            type=str,
            help="Path to the fixtures directory containing CSV files",
        )

    def handle(self, *args, **options):
        if options["fixtures_path"]:
            self.base_path = Path(options["fixtures_path"])
        else:
            self.base_path = (
                Path(__file__).resolve().parent.parent.parent
            ) / "fixtures"

        self.stdout.write("Updating Tasks")
        self.seed_tasks()
        self.stdout.write(self.style.SUCCESS("Done."))

    def seed_tasks(self):
        # Read task IDs and service information from service-times.csv
        service_times_path = self.base_path / "service-times.csv"
        task_ids = []
        service_task_map = {}

        with open(service_times_path, "r") as f:
            reader = csv.reader(f)
            # First row contains task IDs
            header = next(reader)
            task_ids = header[1:]  # Skip the first column which is empty

            # Read service to task mapping
            for row in reader:
                service_name = row[0]
                service_task_map[service_name] = {}
                for i, value in enumerate(row[1:], 1):
                    if value == "1":
                        service_task_map[service_name][header[i]] = True

        # Read task names from duty-names.csv
        duty_names_path = self.base_path / "duty-names.csv"
        task_names = {}

        with open(duty_names_path, "r") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if len(row) >= 2:
                    task_id = row[0]
                    task_name = row[1]
                    task_names[task_id] = task_name

        # Read time periods from duty-codes.csv
        duty_codes_path = self.base_path / "duty-codes.csv"
        time_periods = {}

        with open(duty_codes_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            time_period_row = next(reader)
            for i, task_id in enumerate(header):
                time_periods[task_id] = time_period_row[i]

        # Read exclusions from exclusions.csv
        exclusions_path = self.base_path / "exclusions.csv"
        task_exclusions = {}

        with open(exclusions_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            task_ids_in_exclusions = header[1:]  # Skip the first column

            for row in reader:
                task_id = row[0]
                task_exclusions[task_id] = []

                for i, value in enumerate(row[1:], 0):
                    if value == "1":
                        excluded_task_id = task_ids_in_exclusions[i]
                        task_exclusions[task_id].append(excluded_task_id)

        # Get existing services
        services = {service.name: service for service in Service.objects.all()}

        # Create or update tasks
        created_tasks = []
        for task_id in task_ids:
            if task_id == "lords_supper_prep":
                continue

            # Find which service this task belongs to
            service_name = None
            for svc_name, tasks in service_task_map.items():
                if task_id in tasks:
                    service_name = svc_name
                    break

            if not service_name or service_name not in services:
                self.stdout.write(
                    self.style.WARNING(f"Service not found for task: {task_id}")
                )
                continue

            task_name = task_names.get(task_id, f"Unknown Task ({task_id})")
            time_period = time_periods.get(task_id, Task.SUNDAY)  # Default to Sunday

            # Create or update the task
            task, created = Task.objects.get_or_create(
                id=task_id,
                name=task_name,
                description="",
                service=services[service_name],
                time_period=time_period,
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Task: {task}"))

            created_tasks.append(task)

        # Add exclusions
        for task in created_tasks:
            if task.id in task_exclusions:
                for excluded_task_id in task_exclusions[task.id]:
                    excluded_task = Task.objects.filter(id=excluded_task_id).first()
                    if (
                        excluded_task
                        and not task.excludes.filter(id=excluded_task_id).exists()
                    ):
                        task.excludes.add(excluded_task)
