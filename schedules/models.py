from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from schedules.decorators import round_decimal


class Schedule(models.Model):
    """One month of assignments. History is the Assignment rows, not a parent schedule."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date = models.DateField(help_text="The month and year this schedule is for")
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="created_schedules",
        help_text="User who created this schedule",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.name} - {self.date.strftime('%B %Y')}"

    def can_be_deleted_by(self, user):
        """Creator who can still edit, or an admin of this schedule's group.

        Staff and superuser do not get this in the app. They use Django admin.
        """
        if user is None or not user.is_authenticated:
            return False
        from users.access import can_admin, can_schedule

        if can_admin(user, self.group_id):
            return True
        return user.pk == self.user_id and can_schedule(user, self.group_id)

    def generate_assignment_stats(self):
        """Generate assignment stats for this schedule.
        For user/task combinations with assignments in this schedule, create new stats.
        For all other combinations, reuse the latest existing stats.
        Only creates stats for users who have assignments or preferences.

        Note: This is the legacy bulk method. Stats are now automatically created
        via signal handler when assignments are created.
        This method is kept for backward compatibility and bulk regeneration.
        """
        # Clean up old stats before creating new ones
        self._cleanup_old_stats()

        # Get all user/task combinations that have assignments in this schedule
        schedule_assignments = set(
            Assignment.objects.filter(schedule=self)
            .values_list("user_id", "task_id")
            .distinct()
        )
        print(f"Found {len(schedule_assignments)} assignments in this schedule")

        # Get users who have assignments in this schedule
        users_with_assignments = (
            get_user_model().objects.filter(past_assignments__schedule=self).distinct()
        )
        print(f"Found {users_with_assignments.count()} users with assignments")

        # Get users who have preferences
        users_with_preferences = (
            get_user_model()
            .objects.filter(taskpreference__value__gt=0, is_active=True)
            .distinct()
        )
        print(f"Found {users_with_preferences.count()} users with preferences")

        # Combine both sets of users
        relevant_users = (users_with_assignments | users_with_preferences).distinct()
        print(f"Total relevant users: {relevant_users.count()}")

        # Get tasks that have preferences or assignments
        relevant_tasks = Task.objects.filter(
            models.Q(users_with_preferences__in=relevant_users)
            | models.Q(assignment__schedule=self)
        ).distinct()
        print(f"Found {relevant_tasks.count()} relevant tasks")

        # Get all existing stats for relevant user/task combinations in a single query
        latest_stats = {
            (stat.user_id, stat.task_id): stat
            for stat in AssignmentStats.objects.filter(
                user__in=relevant_users,
                task__in=relevant_tasks,
            )
            .order_by("user_id", "task_id", "-created_at")
            .distinct("user_id", "task_id")
        }
        print(f"Found {len(latest_stats)} existing stats to potentially reuse")

        # Prepare lists for bulk operations
        stats_to_create = []
        stats_to_update = []
        created_from_assignments = 0
        created_from_no_existing = 0

        # Process only relevant user/task combinations
        for user in relevant_users:
            # Get tasks this user is eligible for (has preferences > 0)
            user_tasks = Task.objects.filter(
                users_with_preferences=user, taskpreference__value__gt=0
            ).distinct()
            print(
                f"User {user.username} has {user_tasks.count()} tasks with preferences"
            )

            for task in user_tasks:
                user_task_key = (user.id, task.id)

                if user_task_key in schedule_assignments:
                    # Create new stat for assignments in this schedule
                    stats_to_create.append(
                        AssignmentStats(
                            user=user,
                            task=task,
                            ideal_average=0,  # Will be calculated on save
                            actual_average=0,  # Will be calculated on save
                            assignment_delta=0,  # Will be calculated on save
                        )
                    )
                    created_from_assignments += 1
                else:
                    # Try to reuse latest stat
                    latest_stat = latest_stats.get(user_task_key)
                    if latest_stat:
                        # Always reuse the latest stat if it exists
                        stats_to_update.append(latest_stat)
                    else:
                        stats_to_create.append(
                            AssignmentStats(
                                user=user,
                                task=task,
                                ideal_average=0,  # Will be calculated below
                                actual_average=0,  # Will be calculated below
                                assignment_delta=0,  # Will be calculated below
                            )
                        )
                        created_from_no_existing += 1

        # Bulk create new stats
        if stats_to_create:
            new_stats = AssignmentStats.objects.bulk_create(stats_to_create)
            # Calculate values for each stat
            for stat in new_stats:
                stat.ideal_average = stat.calculate_ideal_average()
                stat.actual_average = stat.calculate_actual_average()
                stat.assignment_delta = stat.calculate_assignment_delta()
                stat.schedule.add(self)
            # Bulk update all at once
            AssignmentStats.objects.bulk_update(
                new_stats, ["ideal_average", "actual_average", "assignment_delta"]
            )
            print(f"Created {len(new_stats)} new stats:")
            print(f"  - {created_from_assignments} from assignments in this schedule")
            print(f"  - {created_from_no_existing} from no existing stats")
            print(
                f"  - {len(new_stats) - created_from_assignments - created_from_no_existing} from other reasons"
            )

        # Add schedule to existing stats
        if stats_to_update:
            # Need to use add() for each stat since it's a ManyToManyField
            for stat in stats_to_update:
                if self not in stat.schedule.all():
                    stat.schedule.add(self)
            print(f"Updated {len(stats_to_update)} existing stats")

    def _cleanup_old_stats(self):
        """Clean up old assignment stats to prevent database bloat"""
        self.assignment_stats.all().delete()

    def force_recalculate_stats(self):
        """Force recalculation of assignment stats for this schedule"""
        self._cleanup_old_stats()
        self.generate_assignment_stats()

    group = models.ForeignKey(
        "users.Group",
        on_delete=models.CASCADE,
        related_name="schedules",
    )

    def save(self, *args, **kwargs):
        """Update statistics before saving"""
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    # TODO this might make more sense then creating all assignments
    # and passing the schedule in, but we'll see. should definitely bulk insert if we can
    def create_assignment(self, user, task, assigned_at=None):
        """Create a new assignment for this schedule"""
        if assigned_at is None:
            assigned_at = timezone.now()

        return Assignment.objects.create(
            schedule=self, user=user, task=task, assigned_at=assigned_at
        )

    def get_assignments(self):
        """Get all assignments in this schedule"""
        return Assignment.objects.filter(schedule=self)


class Service(models.Model):
    name = models.CharField(max_length=100)
    day_of_week = models.IntegerField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(6)]
    )
    start_time = models.TimeField()
    group = models.ForeignKey(
        "users.Group",
        on_delete=models.CASCADE,
        related_name="services",
    )

    class Meta:
        ordering = [
            # Put services with None day_of_week at the end
            models.Case(
                models.When(day_of_week__isnull=True, then=models.Value(999)),
                default="day_of_week",
                output_field=models.IntegerField(),
            ),
            "start_time",
        ]

    def __str__(self):
        return f"{self.name} on day {self.day_of_week} at {self.start_time}"


class TaskManager(models.Manager):
    def is_excluded(self, task_id1, task_id2):
        return self.filter(id=task_id1, excludes__id=task_id2).exists()


class Task(models.Model):
    id = models.CharField(primary_key=True, max_length=64, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    service = models.ForeignKey(
        Service, on_delete=models.RESTRICT, related_name="tasks"
    )
    excludes = models.ManyToManyField("self", symmetrical=True, blank=True)
    users_with_preferences = models.ManyToManyField(
        get_user_model(),
        through="TaskPreference",
        related_name="tasks_with_preferences",
    )

    # TODO Do we need time period, or is service relationship enough?
    SUNDAY = "0"
    MONDAY = "1"
    TUESDAY = "2"
    WEDNESDAY = "3"
    THURSDAY = "4"
    FRIDAY = "5"
    SATURDAY = "6"
    WEEKLY = "w"
    MONTHLY = "m"
    TIME_PERIOD_CHOICES = {
        SUNDAY: "Sunday",
        MONDAY: "Monday",
        TUESDAY: "Tuesday",
        WEDNESDAY: "Wednesday",
        THURSDAY: "Thursday",
        FRIDAY: "Friday",
        SATURDAY: "Saturday",
        WEEKLY: "Weekly",
        MONTHLY: "Monthly",
    }

    time_period = models.CharField(max_length=10, choices=TIME_PERIOD_CHOICES)

    # id stays a globally unique code (song_leader, lesson). A second group's
    # copy needs a different id. Do not switch this primary key to AutoField.

    objects = TaskManager()
    group = models.ForeignKey(
        "users.Group",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    order = models.IntegerField(default=0, help_text="Used for ordering tasks")
    rotation_group = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text=(
            "Tasks that share this label are one family for adjacent-week "
            "rotation (e.g. Sunday and Wednesday song leader). Blank means "
            "no family."
        ),
    )

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        if self.group_id is None and self.service_id:
            self.group_id = self.service.group_id
        super().save(*args, **kwargs)
        self.excludes.add(self)

    def is_excluded(self, task):
        return self.excludes.filter(id=task.id).exists()

    def __str__(self):
        return self.id

    def get_eligible_users(self):
        """Get all users who are eligible for this task"""
        return self.users_with_preferences.filter(
            taskpreference__value__gt=0, is_active=True
        ).distinct()


class Assignment(models.Model):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.RESTRICT,
        related_name="past_assignments",
    )
    task = models.ForeignKey(Task, on_delete=models.RESTRICT)
    assigned_at = models.DateTimeField()
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name="assignments",
        null=True,
        blank=True,
        db_index=True,
    )
    group = models.ForeignKey(
        "users.Group",
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    def save(self, *args, **kwargs):
        if self.group_id is None and self.schedule_id:
            self.group_id = self.schedule.group_id
        if self.group_id is None and self.task_id:
            self.group_id = self.task.group_id
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.assigned_at.strftime('%Y-%m-%d %H:%M')}-{self.task_id} -> {self.user}"


class TaskPreferenceManager(models.Manager):
    def is_eligible(self, user, task):
        """
        Check if a user is eligible for a task based on their preference value
        Returns True if user has a preference > 0, False otherwise
        """
        pref = self.filter(user=user, task_id=task).first()
        return pref is not None and pref.value > 0

    def bias_for_task(self, user, task):
        """
        Calculate the bias for a task based on the preferences of the users
        """
        pref = self.filter(user=user, task_id=task).first()
        return pref.value if pref else 0


class TaskPreference(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.RESTRICT)
    value = models.FloatField(validators=[MinValueValidator(0.0)])
    updated_at = models.DateField(auto_now_add=True)
    group = models.ForeignKey(
        "users.Group",
        on_delete=models.CASCADE,
        related_name="task_preferences",
    )

    def save(self, *args, **kwargs):
        if self.group_id is None and self.task_id:
            self.group_id = self.task.group_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.task_id}"

    class Meta:
        unique_together = ["user", "task"]
        ordering = ["-updated_at"]

    objects = TaskPreferenceManager()


class TaskRequires(models.Model):
    """When this person is assigned `task`, also assign `requires` the same week.

    Skips the exclusion between those two tasks for this person only.
    Directional: they can still hold `requires` without `task`.
    """

    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="task_requires"
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="requirements"
    )
    requires = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="required_by"
    )

    class Meta:
        unique_together = ["user", "task", "requires"]
        verbose_name_plural = "task requires"

    def __str__(self):
        return f"{self.user_id}: {self.task_id} requires {self.requires_id}"


class AssignmentStats(models.Model):
    DECIMAL_PLACES = 8
    MAX_DIGITS = 8 + DECIMAL_PLACES

    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="assignment_stats"
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="assignment_stats"
    )

    # Is it possible to do this in admin?
    # snapshot of assignment stats at the time this schedule was last comitted
    schedule = models.ManyToManyField(Schedule, related_name="assignment_stats")

    """ Expected average of assignment frequency with bias taken into account """
    ideal_average = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=DECIMAL_PLACES, null=True
    )

    """ Actual average of assignment frequency """
    actual_average = models.DecimalField(
        max_digits=MAX_DIGITS, decimal_places=DECIMAL_PLACES, null=True
    )

    """ Relative error between actual and ideal average """
    assignment_delta = models.DecimalField(
        max_digits=1 + DECIMAL_PLACES, decimal_places=DECIMAL_PLACES, null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "task"]),
            models.Index(fields=["task", "user"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]
        get_latest_by = "created_at"

    def __str__(self):
        return f"{self.user.username} {self.task.name} assignment delta: {self.assignment_delta}"

    @classmethod
    def update_or_create_for_assignment(cls, user, task, schedule):
        """
        Update or create AssignmentStats for a specific user/task/schedule combination.
        This is called whenever an assignment is created or updated.

        If a schedule is provided, we look for a stat already associated with that schedule.
        If no schedule or no existing stat, we look for the most recent stat to update.
        Only creates a new stat if none exists for this user/task combination.
        """
        stat = None

        # If schedule is provided, try to find existing stat for this schedule
        if schedule:
            # Check if there's already a stat for this user/task associated with this schedule
            existing_stats = cls.objects.filter(
                user=user, task=task, schedule=schedule
            ).order_by("-created_at")

            if existing_stats.exists():
                stat = existing_stats.first()

        # If we don't have a stat yet, try to get the most recent one for this user/task
        if stat is None:
            stat = (
                cls.objects.filter(user=user, task=task).order_by("-created_at").first()
            )

        # If we still don't have a stat, create a new one
        if stat is None:
            stat = cls.objects.create(
                user=user,
                task=task,
                ideal_average=0,  # Will be calculated below
                actual_average=0,  # Will be calculated below
                assignment_delta=0,  # Will be calculated below
            )

        # Calculate/update values
        stat.ideal_average = stat.calculate_ideal_average()
        stat.actual_average = stat.calculate_actual_average()
        stat.assignment_delta = stat.calculate_assignment_delta()
        stat.save()

        # Associate with the schedule if provided and not already associated
        if schedule and schedule not in stat.schedule.all():
            stat.schedule.add(schedule)

        return stat

    @round_decimal(places=DECIMAL_PLACES)
    def calculate_actual_average(self) -> Decimal:
        """Calculate the actual average for this user/task combination"""
        total_assignments = Assignment.objects.filter(task=self.task).count()
        if total_assignments == 0:
            return 0
        user_assignments = Assignment.objects.filter(
            task=self.task, user=self.user
        ).count()
        return user_assignments / total_assignments

    @round_decimal(places=DECIMAL_PLACES)
    def calculate_ideal_average(self) -> Decimal:
        """Calculate the ideal average for this task based on eligible users and their preferences"""
        eligible_users = self.task.get_eligible_users()
        if not eligible_users.exists():
            return 0

        # Get all preferences for eligible users
        preferences = TaskPreference.objects.filter(
            task=self.task, user__in=eligible_users
        )

        # Calculate total preference weight
        total_weight = sum(pref.value for pref in preferences)
        if total_weight == 0:
            # If all preferences are 0, distribute evenly
            return 1.0 / len(eligible_users)

        # Get this user's preference
        user_pref = preferences.filter(user=self.user).first()
        if not user_pref:
            return 0

        # Calculate weighted ideal average
        return user_pref.value / total_weight

    @round_decimal(places=DECIMAL_PLACES)
    def calculate_assignment_delta(self) -> Decimal:
        """Calculate how much more/less than ideal this user is assigned
        Returns a percentage where:
        - 0% means exactly at ideal
        - Positive means assigned more than ideal (e.g., 50% means 50% more than ideal)
        - Negative means assigned less than ideal (e.g., -50% means 50% less than ideal)
        """
        if not self.ideal_average or self.ideal_average == Decimal("0"):
            self.ideal_average = self.calculate_ideal_average()
        if not self.actual_average:
            self.actual_average = self.calculate_actual_average()

        if self.ideal_average == Decimal("0"):
            return 0

        return (self.actual_average - self.ideal_average) / self.ideal_average

    def save(self, *args, **kwargs):
        """Update statistics before saving"""
        if not self.ideal_average:
            self.ideal_average = self.calculate_ideal_average()
        if not self.actual_average:
            self.actual_average = self.calculate_actual_average()
        if not self.assignment_delta:
            self.assignment_delta = self.calculate_assignment_delta()
        super().save(*args, **kwargs)


# Signal handler to update AssignmentStats whenever an Assignment is created or updated
@receiver(post_save, sender=Assignment)
def update_assignment_stats(sender, instance, created, **kwargs):
    """
    Update AssignmentStats whenever an assignment is created or updated.
    This keeps the snapshot for this user, task, and schedule current.

    AssignmentStats are snapshots tied to a specific schedule, so we only update
    the stat for this specific user/task/schedule combination.
    """
    if instance.user and instance.task:
        AssignmentStats.update_or_create_for_assignment(
            user=instance.user, task=instance.task, schedule=instance.schedule
        )


# Do not delete AssignmentStats when a Schedule is deleted or unlinked.
# The M2M through rows for that schedule go away; the stat rows stay.
# History for the solver is Assignment; throwing away stats on schedule
# delete was wiping snapshots still useful for datalist sort.
