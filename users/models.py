from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password
from django.contrib.auth.validators import UnicodeUsernameValidator

from django.contrib import admin


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, first_name, last_name, password=None, **extra_fields):
        """
        Create and save a user with the given email, first name, and last name and password
        adapted from django.contrib.auth.models.UserManager
        """
        if not email:
            raise ValueError("The given email must be set")

        if not first_name:
            raise ValueError("The given first name must be set")

        if not last_name:
            raise ValueError("The given last name must be set")

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            username=f"{first_name} {last_name}",
            **extra_fields,
        )
        user.password = make_password(password)

        user.save(using=self._db)
        return user

    def create_user(self, email, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, first_name, last_name, password, **extra_fields)

    def create_superuser(
        self, email, first_name, last_name, password=None, **extra_fields
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, first_name, last_name, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model that uses email as the username field.
    First and last name are required.
    """

    username = models.CharField(
        "username",
        max_length=254,
        unique=False,
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
        blank=True,
    )

    email = models.EmailField("email", max_length=254, unique=True)
    first_name = models.CharField("first name", max_length=150)
    last_name = models.CharField("last name", max_length=150)

    # TODO: add phone number field

    @property
    def eligible_tasks(self):
        return self.tasks_with_preferences.filter(taskpreference__value__gt=0)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.username:
            self.username = (
                f"{self.first_name.capitalize()} {self.last_name.capitalize()}"
            )

    @admin.display(description="Lifetime Assignments", ordering="assignment_count")
    def assignment_count(self):
        """
        Count the number of assignments for this user.
        Uses a reverse relationship to avoid circular imports.
        """
        return self.past_assignments.count()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
