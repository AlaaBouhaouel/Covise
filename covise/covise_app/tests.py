from django.test import TestCase
from django.urls import reverse

from .models import User, WaitlistEntry


class WaitlistEntryModelTests(TestCase):
    def test_status_defaults_to_pending(self):
        entry = WaitlistEntry.objects.create(
            full_name="Test User",
            phone_number="+966500000000",
            email="test@example.com",
            country="Saudi Arabia",
            linkedin="https://www.linkedin.com/in/test-user/",
            my_referral_code="CV-TEST123",
        )

        self.assertEqual(entry.status, WaitlistEntry.Status.PENDING)

    def test_status_choices_include_expected_values(self):
        self.assertEqual(
            {value for value, _ in WaitlistEntry.Status.choices},
            {"pending", "approved", "activated", "rejected"},
        )


class AuthEmailNormalizationTests(TestCase):
    def test_create_user_normalizes_full_email_to_lowercase(self):
        user = User.objects.create_user(
            email="Mixed.Case@Example.COM",
            password="safe-password-123",
        )

        self.assertEqual(user.email, "mixed.case@example.com")

    def test_login_accepts_legacy_user_with_mixed_case_email(self):
        User.objects.create_user(
            email="Legacy.User@Example.com",
            password="safe-password-123",
        )

        response = self.client.post(
            reverse("Login"),
            {
                "email": "legacy.user@example.com",
                "password": "safe-password-123",
            },
        )

        self.assertEqual(response.status_code, 302)

    def test_signin_accepts_approved_waitlist_with_mixed_case_email(self):
        WaitlistEntry.objects.create(
            full_name="Approved User",
            phone_number="+966500000001",
            email="Approved.User@Example.com",
            country="Saudi Arabia",
            linkedin="https://www.linkedin.com/in/approved-user/",
            my_referral_code="CV-APPROVED1",
            status=WaitlistEntry.Status.APPROVED,
        )

        response = self.client.post(
            reverse("Sign In"),
            {
                "email": "approved.user@example.com",
                "password": "safe-password-123",
                "confirm_password": "safe-password-123",
            },
        )

        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(email="approved.user@example.com")
        self.assertTrue(created_user.check_password("safe-password-123"))
