from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from schedules.models import TaskPreference, Task
from collections import defaultdict


class Command(BaseCommand):
    help = "Generate a report showing task preferences for all users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tasks",
            nargs="+",
            type=str,
            help="List of task IDs to include in the report (e.g., --tasks task1 task2)",
        )
        parser.add_argument(
            "--show-values",
            action="store_true",
            help="Show actual preference values instead of Yes/No",
        )
        parser.add_argument(
            "--only-yes",
            action="store_true",
            help="Show only users who have at least one preference > 0 for the displayed tasks",
        )
        parser.add_argument(
            "--only-no",
            action="store_true",
            help="Show only users who have all preferences = 0 for the displayed tasks",
        )
        parser.add_argument(
            "--name-only",
            action="store_true",
            help="Show task names as column headers (instead of task IDs) and only user names in rows",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        # Get task filter if provided
        task_ids = options.get("tasks")
        show_values = options.get("show_values", False)
        only_yes = options.get("only_yes", False)
        only_no = options.get("only_no", False)
        name_only = options.get("name_only", False)

        # Check for conflicting flags
        if only_yes and only_no:
            self.stdout.write(
                self.style.ERROR("Cannot use both --only-yes and --only-no together")
            )
            return

        # Build query for tasks
        if task_ids:
            tasks = Task.objects.filter(id__in=task_ids).order_by("order", "id")
            if not tasks.exists():
                self.stdout.write(
                    self.style.ERROR(f'No tasks found with IDs: {", ".join(task_ids)}')
                )
                return
        else:
            tasks = Task.objects.all().order_by("order", "id")

        # Get all users (active by default, or all if you prefer)
        users = User.objects.filter(is_active=True).order_by("username")

        if not users.exists():
            self.stdout.write(self.style.WARNING("No active users found"))
            return

        if not tasks.exists():
            self.stdout.write(self.style.WARNING("No tasks found"))
            return

        # Build a mapping of (user_id, task_id) -> preference value
        preferences_dict = {}
        preferences = TaskPreference.objects.filter(
            user__in=users, task__in=tasks
        ).select_related("user", "task")

        for pref in preferences:
            preferences_dict[(pref.user_id, pref.task_id)] = pref.value

        # Filter users based on --only-yes or --only-no flags
        if only_yes or only_no:
            filtered_users = []
            for user in users:
                # Check if user has any preference > 0 for the displayed tasks
                has_yes = any(
                    preferences_dict.get((user.id, task.id), 0) > 0 for task in tasks
                )

                if only_yes and has_yes:
                    filtered_users.append(user)
                elif only_no and not has_yes:
                    filtered_users.append(user)

            users = filtered_users

            if not users:
                filter_type = "with at least one 'Yes'" if only_yes else "with all 'No'"
                self.stdout.write(
                    self.style.WARNING(
                        f"No users found {filter_type} for the selected tasks"
                    )
                )
                return

        # Print header
        self.stdout.write("\n")
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("Task Preferences Report"))
        if task_ids:
            self.stdout.write(
                self.style.SUCCESS(f'Filtered tasks: {", ".join(task_ids)}')
            )
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write("\n")

        if name_only:
            # Name-only view: user names as rows, task names as column headers
            # Calculate column widths
            user_col_width = max(len(u.username) for u in users)

            # Calculate task column width based on longest task name
            if show_values:
                # For numeric values, we need space for decimals
                task_col_width = max(12, max(len(task.name) for task in tasks))
            else:
                # For Yes/No, use max of task names and "Yes"/"No"
                task_col_width = max(4, max(len(task.name) for task in tasks))

            # Build header row (just task names, no "User" label)
            header = f"{'':<{user_col_width}}"
            for task in tasks:
                header += f" | {task.name:^{task_col_width}}"
            self.stdout.write(self.style.HTTP_INFO(header))

            # Print separator
            separator = "-" * user_col_width
            for _ in tasks:
                separator += "-+-" + "-" * task_col_width
            self.stdout.write(separator)

            # Print data rows (one per user)
            for user in users:
                row = f"{user.username:<{user_col_width}}"
                for task in tasks:
                    value = preferences_dict.get((user.id, task.id), 0)

                    if show_values:
                        cell = f"{value:>{task_col_width}.2f}"
                    else:
                        cell = "Yes" if value > 0 else "No"
                        cell = f"{cell:^{task_col_width}}"

                    # Color code the cells
                    if value > 0:
                        cell_styled = self.style.SUCCESS(cell)
                    else:
                        cell_styled = self.style.WARNING(cell)

                    row += f" | {cell_styled}"

                self.stdout.write(row)
        else:
            # Standard view: users as rows, tasks as columns
            # Calculate column widths
            user_col_width = max(len("User"), max(len(u.username) for u in users))

            # Calculate task column width based on longest task ID
            if show_values:
                # For numeric values, we need space for decimals
                task_col_width = max(12, max(len(task.id) for task in tasks))
            else:
                # For Yes/No, use max of task IDs and "Yes"/"No"
                task_col_width = max(4, max(len(task.id) for task in tasks))

            # Build header row
            header = f"{'User':<{user_col_width}}"
            for task in tasks:
                header += f" | {task.id:^{task_col_width}}"
            self.stdout.write(self.style.HTTP_INFO(header))

            # Print separator
            separator = "-" * user_col_width
            for _ in tasks:
                separator += "-+-" + "-" * task_col_width
            self.stdout.write(separator)

            # Print data rows (one per user)
            for user in users:
                row = f"{user.username:<{user_col_width}}"
                for task in tasks:
                    value = preferences_dict.get((user.id, task.id), 0)

                    if show_values:
                        cell = f"{value:>{task_col_width}.2f}"
                    else:
                        cell = "Yes" if value > 0 else "No"
                        cell = f"{cell:^{task_col_width}}"

                    # Color code the cells
                    if value > 0:
                        cell_styled = self.style.SUCCESS(cell)
                    else:
                        cell_styled = self.style.WARNING(cell)

                    row += f" | {cell_styled}"

                self.stdout.write(row)

        # Print footer with summary
        self.stdout.write("\n")
        self.stdout.write(self.style.SUCCESS("=" * 80))

        # Handle users as list or queryset
        user_count = len(users) if isinstance(users, list) else users.count()
        task_count = tasks.count()

        self.stdout.write(f"Total users: {user_count}")
        self.stdout.write(f"Total tasks: {task_count}")

        # Calculate some statistics (only for displayed users/tasks)
        displayed_preferences = [
            preferences_dict.get((user.id, task.id), 0)
            for user in users
            for task in tasks
        ]
        total_preferences = len([v for v in displayed_preferences if v > 0])
        possible_preferences = user_count * task_count

        self.stdout.write(
            f"Preferences set (>0): {total_preferences} / {possible_preferences}"
        )
        if possible_preferences > 0:
            percentage = (total_preferences / possible_preferences) * 100
            self.stdout.write(f"Coverage: {percentage:.1f}%")
        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write("\n")
