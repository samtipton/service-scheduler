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

    def __str__(self):
        return f"{self.name} on day {self.day_of_week} at {self.start_time}"


class Task(models.Model):
    id = models.CharField(primary_key=True, max_length=64, unique=True)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    service = models.ForeignKey(Service, on_delete=models.RESTRICT)
    excludes = models.ManyToManyField("self", symmetrical=True, blank=True)

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

    def __str__(self):
        return f"{self.name} ({self.task_id}) - {self.description})"


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
        return f"{self.user} -> {self.task_id} ({self.value})"

    class Meta:
        unique_together = ["user", "task"]
        ordering = ["-updated_at"]

    objects = TaskPreferenceManager()
