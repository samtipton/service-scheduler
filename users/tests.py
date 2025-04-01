from django.db import IntegrityError
from django.test import TestCase

from users.models import User


class UserModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

    def test_user_creation(self):
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.first_name, "Test")
        self.assertEqual(self.user.last_name, "User")
        self.assertEqual(
            User.objects.filter(email="test@example.com").first(), self.user
        )

    def test_update_or_create_update(self):
        User.objects.update_or_create(
            email="test@example.com",
            defaults={**dict(self.user.__dict__), "last_name": "Userson"},
        )
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.all().first().last_name, "Userson")

    def test_update_or_create_create(self):
        user, created = User.objects.update_or_create(
            email="test2@example.com",
            first_name="Test",
            last_name="User",
        )
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(user.email, "test2@example.com")

    def test_unique_email(self):
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="test@example.com", first_name="Test", last_name="User"
            )

    def test_nonunique_names_allowed(self):
        User.objects.create_user(
            email="test2@example.com", first_name="Test", last_name="User"
        )

    def test_default_username_is_full_name(self):
        self.assertEqual(self.user.username, "Test User")

    def test_default_username_is_full_name_not_capitalized(self):
        user = User.objects.create_user(
            email="test3@example.com", first_name="test", last_name="user"
        )
        self.assertEqual(user.username, "test user")

    def test_user_manager_get_by_natural_key(self):
        user = User.objects.get_by_natural_key("test@example.com")
        self.assertEqual(user, self.user)

    def test_user_creation_without_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email=None, first_name="Test", last_name="User")

    def test_user_creation_without_first_name(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email="test@example.com", first_name=None, last_name="User"
            )

    def test_user_creation_without_last_name(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email="test@example.com", first_name="Test", last_name=None
            )

    def test_user_creation_with_empty_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", first_name="Test", last_name="User")

    def test_user_creation_with_empty_first_name(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email="test@example.com", first_name="", last_name="User"
            )

    def test_user_creation_with_empty_last_name(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email="test@example.com", first_name="Test", last_name=""
            )
