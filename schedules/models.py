from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator


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
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    service = models.ForeignKey(Service, on_delete=models.RESTRICT)
    excludes = models.ManyToManyField("self", symmetrical=True, blank=True)

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
        return f"{self.id}"


class Assignment(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.RESTRICT)
    task = models.ForeignKey(Task, on_delete=models.RESTRICT)
    assigned_at = models.DateTimeField(db_index=True)

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
