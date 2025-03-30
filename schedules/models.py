from datetime import date, timedelta
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from schedules.decorators import round_decimal


class ScheduleManager(models.Manager):
    def get_latest_selected(self):
        """Get the most recent selected schedule"""
        return self.filter(is_official=True).order_by("-date").first()

    def create_from_base(self, name, date, user, base_schedule=None, description=None):
        """
        Create a new schedule based on an existing one or from scratch.
        """
        # If no base schedule provided, use the most recent selected schedule
        if base_schedule is None:
            base_schedule = self.get_latest_selected()

        # Create the new schedule
        schedule = self.create(
            name=name,
            date=date,
            user=user,
            base_schedule=base_schedule,
            description=description,
        )

        return schedule


class Schedule(models.Model):
    """
    A Schedule represents a collection of assignments for a specific month and year.
    It works similar to git commits, with each schedule potentially building on a previous one.
    """

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

    # TODO add group

    # The base schedule this one builds upon (like a parent commit)
    base_schedule = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_schedules",
        help_text="Previous schedule this one builds upon",
    )

    # Whether this schedule has been selected as the official one
    is_official = models.BooleanField(
        default=False,
        help_text="Whether this schedule is selected as the official schedule for the month",
    )

    objects = ScheduleManager()

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        status = "Selected" if self.is_official else "Draft"
        return f"{self.name} ({status}) - {self.date.strftime('%B %Y')}"

    def select_as_official(self):
        """Select this schedule as the official one for its month/year"""

        month_start = date(self.date.year, self.date.month, 1)
        month_end = date(
            self.date.year + (self.date.month // 12), ((self.date.month % 12) + 1), 1
        ) - timedelta(days=1)

        Schedule.objects.filter(
            date__gte=month_start, date__lte=month_end, is_official=True
        ).update(is_official=False)

        # Then mark this one as selected
        self.is_official = True
        self.save()

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

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class Service(models.Model):
    name = models.CharField(max_length=100)
    day_of_week = models.IntegerField(
        blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(6)]
    )
    start_time = models.TimeField()

    # TODO add groups
    # group = models.ForeignKey(Group, on_delete=models.RESTRICT)

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

    # TODO We can add unique_together with group later when groups are implemented
    # class Meta:
    #     unique_together = ['task_id', 'group']

    objects = TaskManager()
    order = models.IntegerField(default=0, help_text="Used for ordering tasks")

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.excludes.add(self)

    def is_excluded(self, task):
        return self.excludes.filter(id=task.id).exists()

    def __str__(self):
        return self.id

    def get_eligible_users(self):
        """Get all users who are eligible for this task"""
        return self.users_with_preferences.filter(
            taskpreference__value__gt=0
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
        null=True,  # Allow null for backward compatibility
        blank=True,
        db_index=True,
    )

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

    def __str__(self):
        return f"{self.task_id}"

    class Meta:
        unique_together = ["user", "task"]
        ordering = ["-updated_at"]

    objects = TaskPreferenceManager()


class AssignmentStats(models.Model):
    DECIMAL_PLACES = 8
    MAX_DIGITS = 8 + DECIMAL_PLACES

    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="assignment_stats"
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="assignment_stats"
    )

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
