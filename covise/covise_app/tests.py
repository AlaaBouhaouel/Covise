from django.test import TestCase

from .models import WaitlistEntry


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
