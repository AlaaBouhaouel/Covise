import json
import shutil
from unittest.mock import patch
from tempfile import mkdtemp
from datetime import timedelta

from botocore.exceptions import ClientError

from django.core.management import call_command
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.test import RequestFactory
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .messaging import deliver_media_message, ensure_private_conversation_integrity
from .models import AccountDeletionRequest, AccountPauseRequest, BlockedUser, Conversation, ConversationRequest, ConversationUserState, DataDeletionRequest, DataExportRequest, Experiences, Message, MessageReceipt, Notification, OnboardingResponse, Post, PostImage, PostReaction, Profile, Project, SavedPost, SignInEvent, TwoFactorChallenge, User, UserPreference, WaitlistEmailVerification, WaitlistEntry
from .context_processors import user_ui_context
from .user_context import build_profile_context, build_ui_user_context, get_onboarding_skill_config
from .views import _attach_post_feed_metadata, _has_profile_completion, _home_sidebar_metrics, _render_post_content_html, _render_post_title_html, _safe_media_url, _searchable_users_for_home, _serialize_message, _waitlist_to_onboarding_initial_answers


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


class OnboardingSkillConfigTests(TestCase):
    def test_skill_config_has_fallback_options_when_boarding_json_has_no_skills_field(self):
        get_onboarding_skill_config.cache_clear()
        config = get_onboarding_skill_config()

        self.assertGreater(len(config["options"]), 0)
        self.assertIn("Backend engineer", config["options"])
        self.assertEqual(config["max_selected"], 8)


class CountryDisplayFormattingTests(TestCase):
    def test_profile_context_formats_slug_country_labels_for_display(self):
        user = User.objects.create_user(
            email="country-format@example.com",
            password="safe-password-123",
            full_name="Country Format User",
        )
        Profile.objects.create(
            user=user,
            full_name="Country Format User",
            country="saudi_arabia",
            has_accepted_platform_agreement=True,
        )

        context = build_profile_context(user)

        self.assertEqual(context["location"], "Saudi Arabia")

    def test_profile_context_formats_plain_lowercase_country_labels_for_display(self):
        user = User.objects.create_user(
            email="country-plain@example.com",
            password="safe-password-123",
            full_name="Country Plain User",
        )
        Profile.objects.create(
            user=user,
            full_name="Country Plain User",
            country="qatar",
            has_accepted_platform_agreement=True,
        )

        context = build_profile_context(user)

        self.assertEqual(context["location"], "Qatar")

    def test_post_feed_metadata_formats_slug_country_labels_for_display(self):
        user = User.objects.create_user(
            email="country-feed@example.com",
            password="safe-password-123",
            full_name="Country Feed User",
        )
        Profile.objects.create(
            user=user,
            full_name="Country Feed User",
            country="saudi_arabia",
            has_accepted_platform_agreement=True,
        )
        post = Post.objects.create(
            user=user,
            title="Test post",
            content="Testing country display in feed.",
            post_type=Post.PostType.UPDATE,
        )

        _attach_post_feed_metadata([post], current_user=user)

        self.assertEqual(post.feed_country_display, "Saudi Arabia")


class PublicIdentityPrivacyTests(TestCase):
    def test_searchable_users_do_not_expose_other_user_email_addresses(self):
        viewer = User.objects.create_user(
            email="viewer@example.com",
            password="safe-password-123",
            full_name="Viewer User",
        )
        candidate = User.objects.create_user(
            email="privatefounder@example.com",
            password="safe-password-123",
        )
        Profile.objects.create(
            user=candidate,
            country="qatar",
            bio="Building a private founder network.",
            has_accepted_platform_agreement=True,
        )

        searchable_users = _searchable_users_for_home(viewer)
        candidate_entry = next(item for item in searchable_users if item["id"] == str(candidate.id))

        self.assertEqual(candidate_entry["display_name"], "CoVise Member")
        self.assertNotIn("email", candidate_entry)
        self.assertNotIn("privatefounder@example.com", candidate_entry["search_text"].lower())

    def test_ui_user_context_uses_safe_public_fallback_name(self):
        user = User.objects.create_user(
            email="noname@example.com",
            password="safe-password-123",
        )

        helper_context = build_ui_user_context(user)

        self.assertEqual(helper_context["display_name"], "CoVise Member")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class PasswordResetFlowTests(TestCase):
    @patch("covise_app.forms.resend")
    def test_forgot_password_uses_covise_resend_sender(self, mock_resend):
        with patch("covise_app.forms.RESEND_API_KEY", "test-resend-key"):
            user = User.objects.create_user(
                email="reset-user@example.com",
                password="safe-password-123",
                full_name="Reset User",
            )

            response = self.client.post(
                reverse("Forgot Password"),
                {"email": "reset-user@example.com"},
            )

        self.assertRedirects(response, reverse("Forgot Password Sent"))
        mock_resend.Emails.send.assert_called_once()
        payload = mock_resend.Emails.send.call_args.args[0]
        self.assertEqual(payload["from"], "CoVise <founders@covise.net>")
        self.assertEqual(payload["to"], [user.email])
        self.assertIn("Reset your CoVise password", payload["subject"])
        self.assertIn("/reset/", payload["text"])


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
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

        self.assertIn(response.status_code, {301, 302})

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

        self.assertIn(response.status_code, {301, 302})
        created_user = User.objects.get(email="approved.user@example.com")
        self.assertTrue(created_user.check_password("safe-password-123"))

    @patch("covise_app.views.dispatch_notification")
    @patch("covise_app.views.resend")
    def test_signin_sends_account_alert_and_founders_request(self, mock_resend, dispatch_mock):
        waitlist_entry = WaitlistEntry.objects.create(
            full_name="Approved User",
            phone_number="+966500000001",
            email="Approved.User@Example.com",
            country="Saudi Arabia",
            linkedin="https://www.linkedin.com/in/approved-user/",
            venture_summary="Building a matching network for founder teams.",
            description="founder",
            my_referral_code="CV-APPROVED2",
            status=WaitlistEntry.Status.APPROVED,
        )

        with patch("covise_app.views.RESEND_API_KEY", "test-resend-key"):
            response = self.client.post(
                reverse("Sign In"),
                {
                    "email": "approved.user@example.com",
                    "password": "safe-password-123",
                    "confirm_password": "safe-password-123",
                },
            )

        self.assertIn(response.status_code, {301, 302})
        created_user = User.objects.get(email="approved.user@example.com")
        founders_user = User.objects.get(email="founders@covise.net")
        self.assertTrue(
            ConversationRequest.objects.filter(
                requester=founders_user,
                recipient=created_user,
                status=ConversationRequest.Status.PENDING,
            ).exists()
        )
        waitlist_entry.refresh_from_db()
        self.assertEqual(waitlist_entry.status, WaitlistEntry.Status.ACTIVATED)
        mock_resend.Emails.send.assert_called_once()
        payload = mock_resend.Emails.send.call_args.args[0]
        self.assertEqual(payload["to"], ["ellabouhawel@gmail.com", "small345az@gmail.com"])
        self.assertIn("New CoVise account created: Approved User", payload["subject"])
        dispatch_mock.assert_called_once()


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class SecurityAuthenticationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="secure@example.com",
            password="safe-password-123",
            full_name="Secure User",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Secure User",
            has_accepted_platform_agreement=True,
        )
        self.preferences = UserPreference.objects.create(user=self.user, two_factor_enabled=True)

    @patch("covise_app.views.EmailMessage.send", return_value=1)
    def test_login_requires_two_factor_code_when_enabled(self, _mock_send):
        response = self.client.post(
            reverse("Login"),
            {
                "email": "secure@example.com",
                "password": "safe-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Security Check")
        self.assertNotIn("_auth_user_id", self.client.session)

        challenge = TwoFactorChallenge.objects.get(user=self.user)
        response = self.client.post(
            reverse("Login"),
            {
                "challenge_id": str(challenge.id),
                "two_factor_code": challenge.code,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))
        challenge.refresh_from_db()
        self.assertIsNotNone(challenge.consumed_at)
        self.assertEqual(
            SignInEvent.objects.filter(user=self.user, status=SignInEvent.Status.SUCCESS).count(),
            1,
        )

    def test_failed_password_attempt_is_recorded_in_sign_in_history(self):
        response = self.client.post(
            reverse("Login"),
            {
                "email": "secure@example.com",
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 400)
        event = SignInEvent.objects.get(user=self.user)
        self.assertEqual(event.status, SignInEvent.Status.FAILURE)
        self.assertEqual(event.email, "secure@example.com")

    def test_settings_security_post_can_toggle_two_factor(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("Settings"),
            {
                "save_section": "security",
                "security_action": "disable_2fa",
            },
        )

        self.assertRedirects(response, f"{reverse('Settings')}?security=2fa-disabled")
        self.preferences.refresh_from_db()
        self.assertFalse(self.preferences.two_factor_enabled)

    def test_settings_account_can_update_full_name(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("Settings Section", args=["account"]),
            {
                "save_section": "personal_data",
                "full_name": "Updated Secure User",
                "email": self.user.email,
                "phone_number": "+966500000009",
            },
        )

        self.assertRedirects(response, f"{reverse('Settings Section', args=['account'])}?saved=1")
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Updated Secure User")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, "Updated Secure User")

    def test_settings_experiences_saves_timezone_aware_datetime_from_date_input(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("Settings Section", args=["experience-projects"]),
            {
                "save_section": "experiences",
                "title": "Operator",
                "date": "2022-06-01",
                "desc": "Ran early operations.",
            },
        )

        self.assertRedirects(response, f"{reverse('Settings Section', args=['experience-projects'])}?saved=1")
        experience = Experiences.objects.get(user=self.user, title="Operator")
        self.assertTrue(timezone.is_aware(experience.date))
        self.assertEqual(experience.date.date().isoformat(), "2022-06-01")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class AgreementWelcomeEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="agreement@example.com",
            password="safe-password-123",
            full_name="Agreement User",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            full_name="Agreement User",
            has_accepted_platform_agreement=False,
            onboarding_answers={
                "one_liner": "Building founder tools.",
                "looking_for_type": ["Technical co-founder"],
            },
        )
        UserPreference.objects.create(user=self.user)
        self.client.force_login(self.user)

    @patch("covise_app.views.resend")
    def test_accepting_agreement_sends_welcome_email_and_redirects(self, mock_resend):
        with patch("covise_app.views.RESEND_API_KEY", "test-resend-key"):
            response = self.client.post(
                reverse("Agreement"),
                {"agree": "on", "next": reverse("Home")},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Home"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_accepted_platform_agreement)
        self.assertTrue(self.profile.requires_intro_post)
        self.assertEqual(self.profile.platform_agreement_version, "2026.04")
        mock_resend.Emails.send.assert_called_once()
        payload = mock_resend.Emails.send.call_args.args[0]
        self.assertEqual(payload["subject"], "Welcome to CoVise")
        self.assertEqual(payload["to"], [self.user.email])
        self.assertIn("community access is now active", payload["html"])

    @patch("covise_app.views._send_platform_welcome_email", side_effect=RuntimeError("email failed"))
    def test_accepting_agreement_still_redirects_when_welcome_email_fails(self, _mock_send):
        response = self.client.post(
            reverse("Agreement"),
            {"agree": "on", "next": reverse("Home")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Home"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.has_accepted_platform_agreement)
        self.assertTrue(self.profile.requires_intro_post)

    def test_home_shows_intro_post_notice_when_first_post_is_required(self):
        self.profile.has_accepted_platform_agreement = True
        self.profile.requires_intro_post = True
        self.profile.save(update_fields=["has_accepted_platform_agreement", "requires_intro_post"])

        response = self.client.get(reverse("Home"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_intro_post_notice"])

    def test_intro_post_requirement_redirects_other_pages_to_create_post(self):
        self.profile.has_accepted_platform_agreement = True
        self.profile.requires_intro_post = True
        self.profile.save(update_fields=["has_accepted_platform_agreement", "requires_intro_post"])

        response = self.client.get(reverse("Profile"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Create Post"))

    def test_incomplete_profile_redirects_to_onboarding_before_agreement(self):
        self.profile.onboarding_answers = {}
        self.profile.save(update_fields=["onboarding_answers"])

        response = self.client.get(reverse("Home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('Onboarding')}?next={reverse('Home')}")

    def test_agreement_page_redirects_incomplete_profile_back_to_onboarding(self):
        self.profile.onboarding_answers = {}
        self.profile.save(update_fields=["onboarding_answers"])

        response = self.client.get(reverse("Agreement"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('Onboarding')}?next={reverse('Home')}")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class SignInOnboardingFlowTests(TestCase):
    @patch("covise_app.views._ensure_founders_team_request")
    @patch("covise_app.views._send_new_account_alert")
    def test_signin_redirects_new_member_to_onboarding_before_agreement(self, _mock_alert, _mock_founders_request):
        WaitlistEntry.objects.create(
            full_name="Approved User",
            phone_number="+966500000099",
            email="approved-flow@example.com",
            country="Saudi Arabia",
            linkedin="https://www.linkedin.com/in/approved-flow/",
            my_referral_code="CV-APPROVEDFLOW",
            status=WaitlistEntry.Status.APPROVED,
        )

        response = self.client.post(
            reverse("Sign In"),
            {
                "email": "approved-flow@example.com",
                "password": "safe-password-123",
                "confirm_password": "safe-password-123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('Onboarding')}?next={reverse('Home')}")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class ProfileSectionPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profile-sections@example.com",
            password="safe-password-123",
            full_name="Profile Sections User",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Profile Sections User",
            has_accepted_platform_agreement=True,
            onboarding_answers={
                "one_liner": "Building a founder platform.",
                "looking_for_type": ["Technical co-founder"],
            },
        )
        UserPreference.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_profile_section_pages_render_successfully(self):
        section_urls = [
            reverse("Profile Personal Data"),
            reverse("Profile Experience"),
            reverse("Profile Active Projects"),
            reverse("Profile Saved Posts"),
            reverse("Profile Posts"),
        ]

        for url in section_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_personal_data_page_shows_change_and_remove_photo_actions(self):
        response = self.client.get(reverse("Profile Personal Data"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Change")
        self.assertContains(response, "Remove")
        self.assertNotContains(response, "Apply Photo")

    @override_settings(
        DEBUG=True,
        SECURE_SSL_REDIRECT=False,
        ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
    )
    def test_profile_personal_data_uploads_profile_photo(self):
        response = self.client.post(
            reverse("Profile Personal Data"),
            {
                "email": self.user.email,
                "phone_number": "",
                "linkedin": "",
                "github": "",
                "proof_of_work_url": "",
                "location": "",
                "nationality": "",
                "bio": "",
                "skills": "",
                "profile_image": SimpleUploadedFile(
                    "avatar.png",
                    b"fake-image-bytes",
                    content_type="image/png",
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        profile = Profile.objects.get(user=self.user)
        self.assertTrue(bool(profile.profile_image))
        self.assertIn("profile_images/", profile.profile_image.name)
        profile.profile_image.delete(save=False)

    def test_profile_experience_saves_timezone_aware_datetime_from_date_input(self):
        response = self.client.post(
            reverse("Profile Experience"),
            {
                "title": "Founder",
                "date": "2022-06-01",
                "desc": "Built the first version.",
            },
        )

        self.assertRedirects(response, f"{reverse('Profile Experience')}?status=created")
        experience = Experiences.objects.get(user=self.user, title="Founder")
        self.assertTrue(timezone.is_aware(experience.date))
        self.assertEqual(experience.date.date().isoformat(), "2022-06-01")

@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class DataDeletionRequestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="deletion@example.com",
            password="safe-password-123",
            full_name="Deletion User",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            full_name="Deletion User",
            has_accepted_platform_agreement=True,
            platform_agreement_version="2026.04",
            bio="This should be wiped.",
            waitlist_snapshot={"email": "deletion@example.com"},
            onboarding_answers={"one_liner": "Wipe me"},
        )
        self.preferences = UserPreference.objects.create(user=self.user, two_factor_enabled=True)
        self.client.force_login(self.user)
        self.waitlist_entry = WaitlistEntry.objects.create(
            full_name="Deletion User",
            phone_number="+966500000010",
            email="deletion@example.com",
            country="Saudi Arabia",
            linkedin="https://www.linkedin.com/in/deletion-user/",
            status=WaitlistEntry.Status.ACTIVATED,
            my_referral_code="CV-DELETE01",
        )
        self.onboarding_response = OnboardingResponse.objects.create(
            email="deletion@example.com",
            answers={"one_liner": "Wipe me"},
        )
        self.profile.source_waitlist_entry = self.waitlist_entry
        self.profile.source_onboarding_response = self.onboarding_response
        self.profile.save(update_fields=["source_waitlist_entry", "source_onboarding_response"])
        WaitlistEmailVerification.objects.create(
            email="deletion@example.com",
            verification_code="123456",
        )

    @patch("covise_app.views.EmailMessage.send", return_value=1)
    def test_request_data_deletion_wipes_user_data_but_keeps_login_shell(self, _mock_send):
        post = Post.objects.create(
            user=self.user,
            title="Delete me",
            post_type=Post.PostType.UPDATE,
            content="This post should be deleted.",
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="safe-password-123",
            full_name="Other User",
        )
        Profile.objects.create(
            user=other_user,
            full_name="Other User",
            has_accepted_platform_agreement=True,
        )
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=self.user,
        )
        conversation.participants.add(self.user, other_user)
        Message.objects.create(
            conversation=conversation,
            sender=self.user,
            body="This message should be deleted.",
        )

        response = self.client.post(reverse("Request Data Deletion"))

        self.assertRedirects(response, f"{reverse('Settings')}?data_deletion=completed")
        deletion_request = DataDeletionRequest.objects.get(user=self.user)
        self.assertEqual(deletion_request.status, DataDeletionRequest.Status.COMPLETED)

        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.preferences.refresh_from_db()

        self.assertEqual(self.user.email, "deletion@example.com")
        self.assertEqual(self.user.full_name, "")
        self.assertEqual(self.profile.bio, "")
        self.assertEqual(self.profile.waitlist_snapshot, {})
        self.assertEqual(self.profile.onboarding_answers, {})
        self.assertTrue(self.profile.has_accepted_platform_agreement)
        self.assertTrue(self.preferences.two_factor_enabled)

        self.assertFalse(Post.objects.filter(id=post.id).exists())
        self.assertFalse(Message.objects.filter(sender=self.user).exists())
        self.assertFalse(WaitlistEntry.objects.filter(email="deletion@example.com").exists())
        self.assertFalse(OnboardingResponse.objects.filter(email="deletion@example.com").exists())
        self.assertFalse(WaitlistEmailVerification.objects.filter(email="deletion@example.com").exists())

    @patch("covise_app.views.EmailMessage.send", return_value=1)
    def test_settings_page_shows_completed_state_after_data_deletion(self, _mock_send):
        self.client.post(reverse("Request Data Deletion"))

        response = self.client.get(reverse("Settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete Data Again")
        self.assertContains(response, "Your login account stays active.")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class AccountRequestActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="requests@example.com",
            password="safe-password-123",
            full_name="Request User",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Request User",
            has_accepted_platform_agreement=True,
        )
        UserPreference.objects.create(user=self.user)
        self.client.force_login(self.user)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_request_data_export_creates_completed_request_and_emails_zip(self):
        response = self.client.post(reverse("Request Data Export"))

        self.assertRedirects(response, f"{reverse('Settings')}?data_export=completed")
        export_request = DataExportRequest.objects.get(user=self.user)
        self.assertEqual(export_request.status, DataExportRequest.Status.COMPLETED)
        self.assertEqual(len(mail.outbox), 1)
        attachment = mail.outbox[0].attachments[0]
        self.assertTrue(attachment[0].endswith(".zip"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_request_data_export_respects_next_subpage(self):
        response = self.client.post(
            reverse("Request Data Export"),
            {"next": reverse("Settings Section", args=["legal-compliance"])},
        )

        self.assertRedirects(response, f"{reverse('Settings Section', args=['legal-compliance'])}?data_export=completed")

    def test_pause_and_reactivate_account_creates_request_records(self):
        response = self.client.post(
            reverse("Request Account Pause"),
            {"action": "pause"},
        )

        self.assertRedirects(response, f"{reverse('Settings')}?account_pause=paused")
        profile = self.user.profile
        profile.refresh_from_db()
        self.assertTrue(profile.is_account_paused)
        self.assertEqual(AccountPauseRequest.objects.filter(user=self.user).count(), 1)

        response = self.client.post(
            reverse("Request Account Pause"),
            {"action": "reactivate"},
        )

        self.assertRedirects(response, f"{reverse('Settings')}?account_pause=reactivated")
        profile.refresh_from_db()
        self.assertFalse(profile.is_account_paused)
        self.assertEqual(AccountPauseRequest.objects.filter(user=self.user).count(), 2)

    def test_account_pause_respects_next_subpage(self):
        response = self.client.post(
            reverse("Request Account Pause"),
            {
                "action": "pause",
                "next": reverse("Settings Section", args=["danger-zone"]),
            },
        )

        self.assertRedirects(response, f"{reverse('Settings Section', args=['danger-zone'])}?account_pause=paused")

    def test_settings_hub_lists_section_links(self):
        response = self.client.get(reverse("Settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("Settings Section", args=["account"]))
        self.assertContains(response, reverse("Settings Section", args=["notifications"]))
        self.assertContains(response, "Experience &amp; Projects")

    def test_settings_subpage_renders_requested_section(self):
        response = self.client.get(reverse("Settings Section", args=["ai-preferences"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CoVise AI Agent is not available yet.")
        self.assertContains(response, 'data-unavailable="true"', html=False)

    def test_account_settings_section_shows_compact_photo_actions(self):
        response = self.client.get(reverse("Settings Section", args=["account"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile Photo")
        self.assertContains(response, "Change")
        self.assertContains(response, "Remove")

    def test_delete_account_creates_audit_request_before_deleting_user(self):
        with patch("covise_app.views.EmailMessage.send", return_value=1):
            response = self.client.post(
                reverse("Delete Account"),
                {
                    "confirm_delete": "DELETE",
                    "delete_feedback": "Testing delete",
                },
            )

        self.assertRedirects(response, reverse("Landing Page"))
        self.assertFalse(User.objects.filter(email="requests@example.com").exists())
        deletion_request = AccountDeletionRequest.objects.get(email_snapshot="requests@example.com")
        self.assertEqual(deletion_request.status, AccountDeletionRequest.Status.COMPLETED)

    def test_founders_admin_can_delete_another_account(self):
        founders_user = User.objects.create_user(
            email="founders@covise.net",
            password="safe-password-123",
            full_name="Founders",
        )
        Profile.objects.create(
            user=founders_user,
            full_name="Founders",
            has_accepted_platform_agreement=True,
        )
        target_user = User.objects.create_user(
            email="delete-target@example.com",
            password="safe-password-123",
            full_name="Delete Target",
        )
        Profile.objects.create(
            user=target_user,
            full_name="Delete Target",
            has_accepted_platform_agreement=True,
        )
        self.client.force_login(founders_user)

        response = self.client.post(
            reverse("Founders Delete Account", args=[target_user.id]),
            {
                "next": reverse("Home"),
                "delete_feedback": "Deleted by founders admin in test.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('Home')}?deleted_account=1")
        self.assertFalse(User.objects.filter(id=target_user.id).exists())
        deletion_request = AccountDeletionRequest.objects.get(email_snapshot="delete-target@example.com")
        self.assertEqual(deletion_request.status, AccountDeletionRequest.Status.COMPLETED)

    def test_non_founders_user_cannot_delete_another_account(self):
        target_user = User.objects.create_user(
            email="blocked-target@example.com",
            password="safe-password-123",
            full_name="Blocked Target",
        )
        Profile.objects.create(
            user=target_user,
            full_name="Blocked Target",
            has_accepted_platform_agreement=True,
        )

        response = self.client.post(reverse("Founders Delete Account", args=[target_user.id]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(id=target_user.id).exists())


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class PausedAccountBehaviorTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            email="viewer-paused@example.com",
            password="safe-password-123",
            full_name="Viewer User",
        )
        Profile.objects.create(
            user=self.viewer,
            full_name="Viewer User",
            has_accepted_platform_agreement=True,
        )
        UserPreference.objects.create(user=self.viewer)
        self.client.force_login(self.viewer)

    def test_paused_users_are_excluded_from_home_search(self):
        paused_user = User.objects.create_user(
            email="paused@example.com",
            password="safe-password-123",
            full_name="Paused User",
        )
        Profile.objects.create(
            user=paused_user,
            full_name="Paused User",
            has_accepted_platform_agreement=True,
            is_account_paused=True,
        )
        UserPreference.objects.create(user=paused_user, appear_in_search=True)

        response = self.client.get(reverse("Home"), follow=True)

        self.assertEqual(response.status_code, 200)
        searchable_names = {item["display_name"] for item in response.context["searchable_users"]}
        self.assertNotIn("Paused User", searchable_names)

    def test_paused_user_can_browse_but_cannot_submit_blocked_settings_forms(self):
        paused_user = User.objects.create_user(
            email="paused-self@example.com",
            password="safe-password-123",
            full_name="Paused Self",
        )
        Profile.objects.create(
            user=paused_user,
            full_name="Paused Self",
            has_accepted_platform_agreement=True,
            is_account_paused=True,
        )
        UserPreference.objects.create(user=paused_user)

        self.client.force_login(paused_user)

        response = self.client.get(reverse("Settings"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("Settings"),
            {
                "save_section": "personal_data",
                "phone_number": "+966500000011",
            },
        )

        self.assertRedirects(response, f"{reverse('Settings')}?account_pause=blocked")
class PreviewPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="preview@example.com",
            password="safe-password-123",
            full_name="Preview User",
        )

    def test_projects_page_renders_preview_shell(self):
        Project.objects.create(
            user=self.user,
            slug="preview-project",
            code="CV-1001",
            title="Preview Project",
            founder_name="Preview User",
            founder_initials="PU",
            city="Riyadh",
            country="Saudi Arabia",
            overview="Preview overview",
            is_active=True,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("Projects"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project hub coming soon.")
        self.assertContains(response, "This area is not available yet.")
        self.assertContains(response, "Preview Project")
        self.assertContains(response, 'aria-label="Projects"')
        self.assertNotContains(response, "Projects Preview")

    def test_workspace_page_renders_preview_shell(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("Workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workspace tools coming soon.")
        self.assertContains(response, "This area is not available yet.")
        self.assertContains(response, 'aria-label="Workspace"')
        self.assertNotContains(response, "Workspace Preview")


    def test_settings_page_marks_ai_permissions_unavailable(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("Settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CoVise AI Agent is not available yet.")
        self.assertContains(response, 'data-unavailable="true"', html=False)
        self.assertContains(response, "AI Activity Log not available yet")

    def test_settings_page_renders_security_state_from_real_data(self):
        UserPreference.objects.update_or_create(
            user=self.user,
            defaults={"two_factor_enabled": True},
        )
        SignInEvent.objects.create(
            user=self.user,
            email=self.user.email,
            status=SignInEvent.Status.FAILURE,
            browser="Chrome",
            operating_system="Windows",
            device_type=SignInEvent.DeviceType.DESKTOP,
            location="Unknown location",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("Settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Disable 2FA")
        self.assertContains(response, "Chrome - Windows")
        self.assertContains(response, "Failed attempt")

    def test_home_searchable_users_respects_search_visibility_and_blocks(self):
        visible_user = User.objects.create_user(
            email="visible@example.com",
            password="safe-password-123",
            full_name="Visible Founder",
        )
        hidden_user = User.objects.create_user(
            email="hidden@example.com",
            password="safe-password-123",
            full_name="Hidden Founder",
        )
        blocker_user = User.objects.create_user(
            email="blocked@example.com",
            password="safe-password-123",
            full_name="Blocked Founder",
        )

        Profile.objects.create(
            user=visible_user,
            country="Saudi Arabia",
            bio="Building a fintech network for founders.",
            current_role=["Founder"],
            skills=["Product Management", "Fundraising"],
        )
        Profile.objects.create(user=hidden_user, country="UAE", bio="Hidden profile")
        Profile.objects.create(user=blocker_user, country="Qatar", bio="Blocked profile")

        UserPreference.objects.create(user=hidden_user, appear_in_search=False)
        BlockedUser.objects.create(blocker=self.user, blocked=blocker_user)

        self.client.force_login(self.user)
        response = self.client.get(reverse("Home"))

        self.assertEqual(response.status_code, 200)
        searchable_users = response.context["searchable_users"]
        searchable_names = {item["display_name"] for item in searchable_users}

        self.assertIn("Visible Founder", searchable_names)
        self.assertNotIn("Hidden Founder", searchable_names)
        self.assertNotIn("Blocked Founder", searchable_names)
        visible_entry = next(item for item in searchable_users if item["display_name"] == "Visible Founder")
        self.assertEqual(visible_entry["profile_url"], reverse("Public Profile", args=[visible_user.id]))
        self.assertIn("fintech network", visible_entry["search_text"].lower())

    def test_home_community_pulse_uses_approved_and_activated_waitlist_counts(self):
        Profile.objects.create(
            user=self.user,
            full_name="Preview User",
            country="Saudi Arabia",
            linkedin="https://www.linkedin.com/in/preview-user/",
            has_accepted_platform_agreement=True,
            onboarding_answers={
                "one_liner": "Building community intelligence.",
                "looking_for_type": ["Technical co-founder"],
            },
        )
        WaitlistEntry.objects.create(
            full_name="Approved One",
            phone_number="+966500000001",
            email="approved-one@example.com",
            country="Saudi Arabia",
            linkedin="https://www.linkedin.com/in/approved-one/",
            status=WaitlistEntry.Status.APPROVED,
            my_referral_code="CV-APR001",
        )
        WaitlistEntry.objects.create(
            full_name="Approved Two",
            phone_number="+966500000002",
            email="approved-two@example.com",
            custom_country="Japan",
            linkedin="https://www.linkedin.com/in/approved-two/",
            status=WaitlistEntry.Status.APPROVED,
            my_referral_code="CV-APR002",
        )
        WaitlistEntry.objects.create(
            full_name="Activated Founder",
            phone_number="+966500000003",
            email="activated@example.com",
            country="UAE",
            linkedin="https://www.linkedin.com/in/activated-founder/",
            status=WaitlistEntry.Status.ACTIVATED,
            my_referral_code="CV-ACT001",
        )
        older_activated_entry = WaitlistEntry.objects.create(
            full_name="Older Activated Founder",
            phone_number="+966500000004",
            email="older-activated@example.com",
            country="Bahrain",
            linkedin="https://www.linkedin.com/in/older-activated-founder/",
            status=WaitlistEntry.Status.ACTIVATED,
            my_referral_code="CV-ACT002",
        )
        WaitlistEmailVerification.objects.create(email="verification-one@example.com")
        WaitlistEmailVerification.objects.create(email="verification-two@example.com")
        WaitlistEmailVerification.objects.create(email="verification-three@example.com")
        Post.objects.create(
            user=self.user,
            title="First pulse post",
            post_type=Post.PostType.UPDATE,
            content="Community pulse test post one.",
        )
        Post.objects.create(
            user=self.user,
            title="Second pulse post",
            post_type=Post.PostType.UPDATE,
            content="Community pulse test post two.",
        )
        activated_user = User.objects.create_user(
            email="activated@example.com",
            full_name="Activated Founder",
            password="password123",
        )
        Profile.objects.create(
            user=activated_user,
            full_name="Activated Founder",
            source_waitlist_entry=WaitlistEntry.objects.get(email="activated@example.com"),
            has_accepted_platform_agreement=True,
        )
        older_activated_user = User.objects.create_user(
            email="older-activated@example.com",
            full_name="Older Activated Founder",
            password="password123",
        )
        Profile.objects.create(
            user=older_activated_user,
            full_name="Older Activated Founder",
            source_waitlist_entry=older_activated_entry,
            has_accepted_platform_agreement=True,
        )
        User.objects.filter(id=older_activated_user.id).update(
            date_joined=timezone.now() - timezone.timedelta(days=10)
        )

        metrics = _home_sidebar_metrics(self.user)
        self.assertEqual(metrics["verified_founders_count"], 4)
        self.assertEqual(metrics["waitlist_count"], 3)
        self.assertEqual(metrics["countries_involved_count"], 4)
        self.assertEqual(metrics["posts_count"], 2)
        self.assertEqual(metrics["verified_founders_delta"], "1+ Joined this week")
        self.assertEqual(metrics["waitlist_delta"], "3+ today")
        self.assertEqual(metrics["countries_involved_delta"], "UAE, Saudi Arabia, ...")
        self.assertEqual(metrics["posts_delta"], "2+ today")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class OnboardingPrefillTests(TestCase):
    def test_waitlist_answers_prefill_building_text_and_matching_choice(self):
        initial_answers = _waitlist_to_onboarding_initial_answers(
            {
                "email": "waitlist@example.com",
                "description": "developer",
                "venture_summary": "We are building an AI workflow copilot for finance teams.",
                "country": "saudi_arabia",
                "linkedin": "https://linkedin.com/in/waitlist-user",
            }
        )

        self.assertEqual(initial_answers["email"], "waitlist@example.com")
        self.assertEqual(initial_answers["user_type"], "developer")
        self.assertEqual(
            initial_answers["one_liner"],
            "We are building an AI workflow copilot for finance teams.",
        )
        self.assertNotIn("location", initial_answers)
        self.assertNotIn("profile_links", initial_answers)

    def test_profile_completion_no_longer_requires_location_or_links(self):
        user = User.objects.create_user(
            email="onboarding-prefill@example.com",
            password="safe-password-123",
            full_name="Onboarding Prefill",
        )
        profile = Profile.objects.create(
            user=user,
            full_name="Onboarding Prefill",
            one_liner="Building an operator network for founders.",
            looking_for_type="Technical co-founder",
            has_accepted_platform_agreement=True,
        )

        self.assertTrue(_has_profile_completion(profile))

    def test_onboarding_intent_redirect_starts_at_first_matching_extended_step(self):
        user = User.objects.create_user(
            email="intent-step@example.com",
            password="safe-password-123",
            full_name="Intent Step",
        )
        Profile.objects.create(
            user=user,
            full_name="Intent Step",
            has_accepted_platform_agreement=True,
            waitlist_snapshot={
                "email": "intent-step@example.com",
                "description": "developer",
                "venture_summary": "Building internal AI tooling for operators.",
            },
            onboarding_answers={
                "user_type": "developer",
                "one_liner": "Building internal AI tooling for operators.",
                "looking_for_type": "Technical co-founder",
            },
        )

        self.client.force_login(user)
        response = self.client.get(f"{reverse('Onboarding')}?step=intent")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["onboarding_start_step_id"], "S3_specialist")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class ProfilePageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="safe-password-123",
            full_name="Owner User",
        )
        self.viewer = User.objects.create_user(
            email="viewer@example.com",
            password="safe-password-123",
            full_name="Viewer User",
        )
        self.author = User.objects.create_user(
            email="author@example.com",
            password="safe-password-123",
            full_name="Author User",
        )

        self.profile = Profile.objects.create(
            user=self.user,
            full_name="Owner User",
            country="Saudi Arabia",
            bio="Building something serious.",
            current_role=["Founder"],
            cofounders_needed=["1"],
            looking_for_type=["Technical Cofounder"],
            looking_for_skills=["Engineering"],
            skills=["Product Management"],
            onboarding_answers={"show_cofounder_badge": True},
            has_accepted_platform_agreement=True,
        )
        Profile.objects.create(
            user=self.viewer,
            full_name="Viewer User",
            has_accepted_platform_agreement=True,
        )
        Profile.objects.create(
            user=self.author,
            full_name="Author User",
            has_accepted_platform_agreement=True,
        )

        self.own_post = Post.objects.create(
            user=self.user,
            title="AMA Launch Notes",
            post_type=Post.PostType.AMA,
            content="Ask me anything about our traction.",
        )
        self.saved_post = Post.objects.create(
            user=self.author,
            title="Saved Founder Update",
            post_type=Post.PostType.UPDATE,
            content="A useful post worth bookmarking.",
        )
        SavedPost.objects.create(user=self.user, post=self.saved_post)

    def test_owner_profile_shows_saved_posts_section(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("Profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saved Posts")
        self.assertContains(response, self.saved_post.title)

    def test_public_profile_hides_saved_posts_section(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("Public Profile", args=[self.user.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Saved Posts")
        self.assertNotContains(response, self.saved_post.title)

    def test_public_profile_request_button_shows_cancel_for_outgoing_pending_request(self):
        ConversationRequest.objects.create(
            requester=self.viewer,
            recipient=self.user,
            status=ConversationRequest.Status.PENDING,
        )
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("Public Profile", args=[self.user.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_pending_outgoing_request"])
        self.assertContains(response, "Cancel Request")

    def test_profile_post_metadata_omits_post_type_label(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("Profile"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.own_post.get_post_type_display())

    def test_profile_hero_badge_renders_when_enabled(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("Profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["profile_show_cofounder_badge"])
        self.assertContains(response, "Looking for Cofounder")

    def test_profile_hero_badge_hidden_when_disabled(self):
        self.profile.onboarding_answers = {"show_cofounder_badge": False}
        self.profile.save(update_fields=["onboarding_answers"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("Profile"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["profile_show_cofounder_badge"])
        self.assertNotContains(response, "Looking for Cofounder")

    def test_profile_card_includes_badge_state_in_context_and_html(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("Profile Card"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["profile_card"]["show_cofounder_badge"])
        self.assertContains(response, 'id="card-cofounder-badge"')
        self.assertContains(response, "Looking for Cofounder")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class CreatePostAlertEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="poster@example.com",
            password="safe-password-123",
            full_name="Poster User",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Poster User",
            has_accepted_platform_agreement=True,
            onboarding_answers={
                "one_liner": "Building founder tooling.",
                "looking_for_type": ["Pilot customers"],
            },
        )

    @override_settings(
        SITE_URL="https://covise.net",
        POST_ALERT_EMAILS=["ellabouhawel@gmail.com", "small345az@gmail.com"],
    )
    @patch("covise_app.views.resend")
    def test_create_post_emails_alert_recipients_with_post_details(self, mock_resend):
        with patch("covise_app.views.RESEND_API_KEY", "test-resend-key"):
            self.client.force_login(self.user)

            response = self.client.post(
                reverse("Create Post"),
                {
                    "title": "Founder update",
                    "post_type": Post.PostType.UPDATE,
                    "content": "We launched in Riyadh.\nLooking for pilot customers.",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Post.objects.count(), 1)
        mock_resend.Emails.send.assert_called_once()

        payload = mock_resend.Emails.send.call_args.args[0]
        created_post = Post.objects.get()

        self.assertEqual(
            payload["to"],
            ["ellabouhawel@gmail.com"],
        )
        self.assertEqual(payload["subject"], "New CoVise post: Founder update")
        self.assertIn("Poster User (poster@example.com)", payload["html"])
        self.assertIn("Founder update", payload["html"])
        self.assertIn("We launched in Riyadh.<br>Looking for pilot customers.", payload["html"])
        self.assertIn(f"https://covise.net/posts/{created_post.id}/", payload["html"])


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class CreatePostTemplatePrefillTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="templates@example.com",
            password="safe-password-123",
            full_name="Template User",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            full_name="Template User",
            country="Saudi Arabia",
            bio="Former operator building workflow tools for founder teams.",
            has_accepted_platform_agreement=True,
            stage=["MVP"],
            one_liner=["A founder workflow platform for lean teams"],
            looking_for_type=["Technical co-founder"],
            looking_for_skills=["Backend engineer"],
            cofounder_commitment=["Full-time"],
            founder_timeline=["Launching pilots this quarter"],
            skills=["Product strategy", "Go-to-market"],
            onboarding_answers={
                "local_partner_need": "Helping founders run their teams without operational sprawl",
            },
        )

    def test_non_free_intent_templates_prefill_from_profile_data(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("Create Post"))

        self.assertEqual(response.status_code, 200)
        template_payloads = response.context["template_payloads"]

        self.assertEqual(
            template_payloads["find_cofounder"]["title"],
            "Looking for backend engineer to build a founder workflow platform for lean teams",
        )
        self.assertIn("A founder workflow platform for lean teams", template_payloads["find_cofounder"]["content"])
        self.assertIn("Backend engineer", template_payloads["find_cofounder"]["content"])
        self.assertIn("Full-time", template_payloads["find_cofounder"]["content"])
        self.assertIn("Saudi Arabia", template_payloads["find_cofounder"]["content"])

        self.assertEqual(
            template_payloads["ask_advice"]["title"],
            "Need advice on helping founders run their teams without operational sprawl",
        )
        self.assertIn("Former operator building workflow tools for founder teams.", template_payloads["ask_advice"]["content"])
        self.assertIn("Technical co-founder", template_payloads["ask_advice"]["content"])

        self.assertEqual(
            template_payloads["share_update"]["title"],
            "Update on A founder workflow platform for lean teams",
        )
        self.assertIn("Launching pilots this quarter", template_payloads["share_update"]["content"])
        self.assertIn("Technical co-founder", template_payloads["share_update"]["content"])
        self.assertIn("MVP / Saudi Arabia", template_payloads["share_update"]["content"])

    def test_first_post_editor_starts_blank_but_stays_in_introduction_mode(self):
        first_post_user = User.objects.create_user(
            email="first-post@example.com",
            password="safe-password-123",
            full_name="First Post User",
        )
        Profile.objects.create(
            user=first_post_user,
            full_name="First Post User",
            has_accepted_platform_agreement=True,
        )
        self.client.force_login(first_post_user)

        response = self.client.get(reverse("Create Post"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_first_post"])
        self.assertEqual(response.context["form_data"]["title"], "")
        self.assertEqual(response.context["form_data"]["content"], "")
        self.assertEqual(response.context["form_data"]["post_type"], Post.PostType.UPDATE)

    @patch("covise_app.views._send_post_alert_email")
    @patch("covise_app.views._create_post_mention_notifications")
    @patch("covise_app.views._create_post_notifications")
    def test_first_successful_post_clears_intro_post_requirement(self, _mock_notifications, _mock_mentions, _mock_email):
        self.profile.requires_intro_post = True
        self.profile.save(update_fields=["requires_intro_post"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("Create Post"),
            {
                "title": "My introduction",
                "post_type": Post.PostType.UPDATE,
                "content": "Hello everyone, excited to build with this network.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.requires_intro_post)

    def test_first_update_post_displays_as_introduction(self):
        self.client.force_login(self.user)
        first_post = Post.objects.create(
            user=self.user,
            title="My own intro",
            post_type=Post.PostType.UPDATE,
            content="Free form introduction content.",
        )

        response = self.client.get(reverse("Post Detail", args=[first_post.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Introduction")

    def test_non_free_intent_templates_fallback_to_dot_placeholders_when_profile_is_missing(self):
        self.profile.bio = ""
        self.profile.country = ""
        self.profile.stage = None
        self.profile.one_liner = None
        self.profile.looking_for_type = None
        self.profile.looking_for_skills = None
        self.profile.cofounder_commitment = None
        self.profile.founder_timeline = None
        self.profile.skills = None
        self.profile.onboarding_answers = {}
        self.profile.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse("Create Post"))

        self.assertEqual(response.status_code, 200)
        template_payloads = response.context["template_payloads"]

        self.assertEqual(
            template_payloads["find_cofounder"]["title"],
            "Looking for [who I'm looking for] to build [what I'm building]",
        )
        self.assertIn("[What I'm building]", template_payloads["find_cofounder"]["content"])
        self.assertIn("[Who I'm looking for]", template_payloads["find_cofounder"]["content"])
        self.assertEqual(
            template_payloads["ask_advice"]["title"],
            "Need advice on [the challenge I'm facing]",
        )
        self.assertIn("[Context]", template_payloads["ask_advice"]["content"])
        self.assertIn("[The challenge I'm facing]", template_payloads["ask_advice"]["content"])
        self.assertEqual(
            template_payloads["share_update"]["title"],
            "Update on [What I'm building]",
        )
        self.assertIn("[What we shipped / achieved]", template_payloads["share_update"]["content"])
        self.assertIn("Building in [Industry / Stage / Location]", template_payloads["share_update"]["content"])


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class DeletePostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="delete-post-owner@example.com",
            password="safe-password-123",
            full_name="Delete Post Owner",
        )
        self.other_user = User.objects.create_user(
            email="delete-post-other@example.com",
            password="safe-password-123",
            full_name="Delete Post Other",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Delete Post Owner",
            has_accepted_platform_agreement=True,
        )
        Profile.objects.create(
            user=self.other_user,
            full_name="Delete Post Other",
            has_accepted_platform_agreement=True,
        )

    def test_post_owner_can_delete_post_and_return_to_home(self):
        post = Post.objects.create(
            user=self.user,
            title="Delete me",
            post_type=Post.PostType.UPDATE,
            content="Delete this post from the feed.",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("Delete Post", args=[post.id]),
            {"next": reverse("Home")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Home"))
        self.assertFalse(Post.objects.filter(id=post.id).exists())

    def test_non_owner_cannot_delete_post(self):
        post = Post.objects.create(
            user=self.user,
            title="Keep me",
            post_type=Post.PostType.UPDATE,
            content="Another user should not delete this.",
        )
        self.client.force_login(self.other_user)

        response = self.client.post(reverse("Delete Post", args=[post.id]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(id=post.id).exists())

    def test_founders_admin_can_delete_any_post(self):
        founders_user = User.objects.create_user(
            email="founders@covise.net",
            password="safe-password-123",
            full_name="Founders",
        )
        Profile.objects.create(
            user=founders_user,
            full_name="Founders",
            has_accepted_platform_agreement=True,
        )
        post = Post.objects.create(
            user=self.user,
            title="Founders can remove me",
            post_type=Post.PostType.UPDATE,
            content="This post should be removable by founders admin.",
        )
        self.client.force_login(founders_user)

        response = self.client.post(
            reverse("Delete Post", args=[post.id]),
            {"next": reverse("Home")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Home"))
        self.assertFalse(Post.objects.filter(id=post.id).exists())


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class EditPostTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="edit-post-owner@example.com",
            password="safe-password-123",
            full_name="Edit Post Owner",
        )
        self.other_user = User.objects.create_user(
            email="edit-post-other@example.com",
            password="safe-password-123",
            full_name="Edit Post Other",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Edit Post Owner",
            has_accepted_platform_agreement=True,
        )
        Profile.objects.create(
            user=self.other_user,
            full_name="Edit Post Other",
            has_accepted_platform_agreement=True,
        )

    def test_post_owner_can_edit_post(self):
        post = Post.objects.create(
            user=self.user,
            title="Original title",
            post_type=Post.PostType.UPDATE,
            content="Original content",
            quote_content="Original quote",
            quote_color="#1e3a5f",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("Edit Post", args=[post.id]),
            {
                "title": "Updated title",
                "post_type": Post.PostType.ASK,
                "content": "Updated content with @nobody",
                "quote_content": "Updated quote",
                "quote_color": "#2d1b4e",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Post Detail", args=[post.id]))
        post.refresh_from_db()
        self.assertEqual(post.title, "Updated title")
        self.assertEqual(post.post_type, Post.PostType.ASK)
        self.assertEqual(post.content, "Updated content with @nobody")
        self.assertEqual(post.quote_content, "Updated quote")
        self.assertEqual(post.quote_color, "#2d1b4e")

    def test_non_owner_cannot_edit_post(self):
        post = Post.objects.create(
            user=self.user,
            title="Owner post",
            post_type=Post.PostType.UPDATE,
            content="Leave this alone.",
        )
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("Edit Post", args=[post.id]))

        self.assertEqual(response.status_code, 403)


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class PostReactionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="post-reactor@example.com",
            password="safe-password-123",
            full_name="Post Reactor",
        )
        self.author = User.objects.create_user(
            email="post-author@example.com",
            password="safe-password-123",
            full_name="Post Author",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Post Reactor",
            has_accepted_platform_agreement=True,
        )
        Profile.objects.create(
            user=self.author,
            full_name="Post Author",
            has_accepted_platform_agreement=True,
        )
        self.post = Post.objects.create(
            user=self.author,
            title="Reaction Post",
            post_type=Post.PostType.UPDATE,
            content="Testing persisted post reactions.",
        )
        self.client.force_login(self.user)

    def test_toggle_post_reaction_persists_like_and_marks_detail_viewer_state(self):
        response = self.client.post(reverse("Toggle Post Reaction", args=[self.post.id, "thumbs_up"]))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "ok": True,
                "reaction_counts": {
                    "thumbs_up": 1,
                    "thumbs_down": 0,
                },
                "user_reaction": "thumbs_up",
            },
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.likes_number, 1)
        self.assertTrue(
            PostReaction.objects.filter(
                user=self.user,
                post=self.post,
                reaction=PostReaction.ReactionType.THUMBS_UP,
            ).exists()
        )

        detail_response = self.client.get(reverse("Post Detail", args=[self.post.id]))

        self.assertEqual(detail_response.status_code, 200)
        self.assertTrue(detail_response.context["post"].viewer_liked)
        self.assertEqual(detail_response.context["post"].likes_number, 1)

    def test_toggle_post_reaction_switches_and_removes_existing_reaction(self):
        PostReaction.objects.create(
            user=self.user,
            post=self.post,
            reaction=PostReaction.ReactionType.THUMBS_UP,
        )
        self.post.likes_number = 1
        self.post.save(update_fields=["likes_number"])

        switch_response = self.client.post(reverse("Toggle Post Reaction", args=[self.post.id, "thumbs_down"]))

        self.assertEqual(switch_response.status_code, 200)
        self.assertJSONEqual(
            switch_response.content,
            {
                "ok": True,
                "reaction_counts": {
                    "thumbs_up": 0,
                    "thumbs_down": 1,
                },
                "user_reaction": "thumbs_down",
            },
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.likes_number, 0)
        self.assertTrue(
            PostReaction.objects.filter(
                user=self.user,
                post=self.post,
                reaction=PostReaction.ReactionType.THUMBS_DOWN,
            ).exists()
        )

        remove_response = self.client.post(reverse("Toggle Post Reaction", args=[self.post.id, "thumbs_down"]))

        self.assertEqual(remove_response.status_code, 200)
        self.assertJSONEqual(
            remove_response.content,
            {
                "ok": True,
                "reaction_counts": {
                    "thumbs_up": 0,
                    "thumbs_down": 0,
                },
                "user_reaction": "",
            },
        )
        self.assertFalse(PostReaction.objects.filter(user=self.user, post=self.post).exists())


class PostContentFormattingTests(TestCase):
    def test_render_post_content_html_formats_bold_and_italic_markers(self):
        post = Post(
            title="Formatting",
            content="This is **bold** and this is *italic*.",
        )
        post.mentions_cache = []

        rendered = _render_post_content_html(post)

        self.assertIn("<strong>bold</strong>", rendered)
        self.assertIn("<em>italic</em>", rendered)
        self.assertNotIn("**bold**", rendered)
        self.assertNotIn("*italic*", rendered)

    def test_render_post_title_html_formats_bold_markers(self):
        rendered = _render_post_title_html("A **bold** title")

        self.assertIn("<strong>bold</strong>", rendered)
        self.assertNotIn("**bold**", rendered)


@override_settings(
    DEBUG=False,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
    AWS_ACCESS_KEY_ID="test-access-key",
    AWS_SECRET_ACCESS_KEY="test-secret-key",
    AWS_STORAGE_BUCKET_NAME="covise-posts-test",
    AWS_S3_REGION_NAME="eu-central-1",
)
class PostImageStorageTests(TestCase):
    PNG_BYTES = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="storage@example.com",
            password="safe-password-123",
            full_name="Storage User",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Storage User",
            country="Saudi Arabia",
            linkedin="https://www.linkedin.com/in/storage-user/",
            has_accepted_platform_agreement=True,
            onboarding_answers={
                "one_liner": "Building a production-safe media pipeline.",
                "looking_for_type": ["Technical co-founder"],
                "profile_links": ["https://www.linkedin.com/in/storage-user/"],
            },
        )

    def _missing_s3_object(self, *args, **kwargs):
        raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")

    @patch("covise_app.views.RESEND_API_KEY", "")
    @patch("covise_app.storage.boto3.client")
    def test_create_post_uploads_gallery_images_to_s3_and_keeps_s3_url_on_model(self, mock_boto_client):
        mock_s3 = mock_boto_client.return_value
        mock_s3.head_object.side_effect = self._missing_s3_object
        mock_s3.generate_presigned_url.side_effect = (
            lambda operation, Params=None, ExpiresIn=None: (
                f"https://signed.example/{Params['Key']}?expires={ExpiresIn}"
            )
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("Create Post"),
            {
                "title": "Shipping with S3",
                "post_type": Post.PostType.UPDATE,
                "content": "Testing production image storage.",
                "images": SimpleUploadedFile(
                    "launch.png",
                    self.PNG_BYTES,
                    content_type="image/png",
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Post.objects.count(), 1)
        self.assertEqual(PostImage.objects.count(), 1)

        saved_image = PostImage.objects.get()
        self.assertTrue(saved_image.image.name.startswith("post_images/"))
        self.assertEqual(
            saved_image.image.url,
            f"https://signed.example/{saved_image.image.name}?expires=3600",
        )

        mock_s3.upload_fileobj.assert_called_once()
        upload_args = mock_s3.upload_fileobj.call_args.args
        upload_extra_args = mock_s3.upload_fileobj.call_args.kwargs["ExtraArgs"]
        self.assertEqual(upload_args[1], "covise-posts-test")
        self.assertEqual(upload_args[2], saved_image.image.name)
        self.assertEqual(upload_extra_args["ContentType"], "image/png")
        self.assertEqual(upload_extra_args["ServerSideEncryption"], "AES256")

    @patch("covise_app.views.RESEND_API_KEY", "")
    @patch("covise_app.storage.boto3.client")
    def test_uploaded_s3_gallery_image_reaches_post_detail_and_home_feed(self, mock_boto_client):
        mock_s3 = mock_boto_client.return_value
        mock_s3.head_object.side_effect = self._missing_s3_object
        mock_s3.generate_presigned_url.side_effect = (
            lambda operation, Params=None, ExpiresIn=None: (
                f"https://signed.example/{Params['Key']}?expires={ExpiresIn}"
            )
        )

        self.client.force_login(self.user)
        create_response = self.client.post(
            reverse("Create Post"),
            {
                "title": "S3 feed coverage",
                "post_type": Post.PostType.UPDATE,
                "content": "This post should render the same S3 image everywhere.",
                "images": SimpleUploadedFile(
                    "coverage.png",
                    self.PNG_BYTES,
                    content_type="image/png",
                ),
            },
        )

        self.assertEqual(create_response.status_code, 302)
        created_post = Post.objects.get()
        saved_image = PostImage.objects.get(post=created_post)
        expected_url = (
            f"https://signed.example/{saved_image.image.name}?expires=3600"
        )

        detail_response = self.client.get(reverse("Post Detail", args=[created_post.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.context["post"].feed_images[0]["url"], expected_url)
        self.assertContains(detail_response, expected_url)

        home_response = self.client.get(reverse("Home"))
        self.assertEqual(home_response.status_code, 200)
        feed_post = next(item for item in home_response.context["posts"] if item.id == created_post.id)
        self.assertEqual(feed_post.feed_images[0]["url"], expected_url)
        self.assertContains(home_response, expected_url)

    @patch("covise_app.storage.boto3.client")
    def test_profile_image_uses_s3_url_in_shared_ui_contexts_and_rendered_pages(self, mock_boto_client):
        mock_s3 = mock_boto_client.return_value
        mock_s3.head_object.side_effect = self._missing_s3_object
        mock_s3.generate_presigned_url.side_effect = (
            lambda operation, Params=None, ExpiresIn=None: (
                f"https://signed.example/{Params['Key']}?expires={ExpiresIn}"
            )
        )

        self.user.profile.profile_image = SimpleUploadedFile(
            "avatar.png",
            self.PNG_BYTES,
            content_type="image/png",
        )
        self.user.profile.save(update_fields=["profile_image"])

        expected_url = (
            f"https://signed.example/{self.user.profile.profile_image.name}?expires=3600"
        )

        helper_context = build_ui_user_context(self.user)
        self.assertEqual(helper_context["avatar_url"], expected_url)

        request = self.factory.get(reverse("Settings"))
        request.user = self.user
        processor_context = user_ui_context(request)
        self.assertEqual(processor_context["ui_user"]["avatar_url"], expected_url)

        self.client.force_login(self.user)
        settings_response = self.client.get(reverse("Settings"))
        self.assertEqual(settings_response.status_code, 200)
        self.assertContains(settings_response, expected_url)

    def test_post_images_still_use_local_media_storage_in_debug(self):
        temp_media_root = mkdtemp(dir=".")
        try:
            with override_settings(DEBUG=True, MEDIA_ROOT=temp_media_root, MEDIA_URL="/media/"):
                image_field = PostImage._meta.get_field("image")
                image_url = image_field.storage.url("post_images/local.png")

                self.assertFalse(image_field.storage._use_s3())
                self.assertEqual(image_url, "/media/post_images/local.png")
        finally:
            shutil.rmtree(temp_media_root, ignore_errors=True)

    def test_safe_media_url_keeps_local_media_relative(self):
        temp_media_root = mkdtemp(dir=".")
        try:
            with override_settings(
                DEBUG=True,
                MEDIA_ROOT=temp_media_root,
                MEDIA_URL="/media/",
                SITE_URL="https://covise.net",
            ):
                image_field = PostImage._meta.get_field("image")
                field_file = image_field.attr_class(
                    instance=PostImage(),
                    field=image_field,
                    name="post_images/local.png",
                )
                self.assertEqual(_safe_media_url(field_file), "/media/post_images/local.png")
        finally:
            shutil.rmtree(temp_media_root, ignore_errors=True)

    def test_presigned_media_urls_use_regional_bucket_host(self):
        image_field = PostImage._meta.get_field("image")

        url = image_field.storage._s3_presigned_url("profile_images/test.png")

        self.assertIn(
            "covise-posts-test.s3.eu-central-1.amazonaws.com/profile_images/test.png",
            url,
        )
        self.assertNotIn(
            "covise-posts-test.s3.amazonaws.com/profile_images/test.png",
            url,
        )


@override_settings(
    DEBUG=False,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"],
    AWS_ACCESS_KEY_ID="test-access-key",
    AWS_SECRET_ACCESS_KEY="test-secret-key",
    AWS_STORAGE_BUCKET_NAME="covise-posts-test",
    AWS_S3_REGION_NAME="eu-central-1",
)
class MessageAttachmentStorageTests(TestCase):
    TXT_BYTES = b"hello from covise chat"

    def setUp(self):
        self.sender = User.objects.create_user(
            email="sender@example.com",
            password="safe-password-123",
            full_name="Sender User",
        )
        self.recipient = User.objects.create_user(
            email="recipient@example.com",
            password="safe-password-123",
            full_name="Recipient User",
        )
        Profile.objects.create(user=self.sender, full_name="Sender User", has_accepted_platform_agreement=True)
        Profile.objects.create(user=self.recipient, full_name="Recipient User", has_accepted_platform_agreement=True)
        UserPreference.objects.create(user=self.sender)
        UserPreference.objects.create(user=self.recipient)
        self.conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=self.sender,
        )
        self.conversation.participants.add(self.sender, self.recipient)

    def _missing_s3_object(self, *args, **kwargs):
        raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")

    @patch("covise_app.messaging.dispatch_notification")
    @patch("covise_app.storage.boto3.client")
    def test_message_attachment_uploads_to_s3_and_serializes_stable_media_path(self, mock_boto_client, _mock_dispatch_notification):
        mock_s3 = mock_boto_client.return_value
        mock_s3.head_object.side_effect = self._missing_s3_object
        mock_s3.generate_presigned_url.side_effect = (
            lambda operation, Params=None, ExpiresIn=None: (
                f"https://signed.example/{Params['Key']}?expires={ExpiresIn}"
            )
        )

        send_result = deliver_media_message(
            conversation_id=self.conversation.id,
            sender=self.sender,
            uploaded_file=SimpleUploadedFile(
                "notes.txt",
                self.TXT_BYTES,
                content_type="text/plain",
            ),
            requested_type=Message.MessageType.FILE,
            caption="Attached notes",
        )

        message = send_result["message"]
        self.assertEqual(message.message_type, Message.MessageType.FILE)
        self.assertTrue(message.attachment_file.name.startswith("chat_media/"))

        expected_url = (
            f"https://signed.example/{message.attachment_file.name}?expires=3600"
        )
        self.assertEqual(message.attachment_file.url, expected_url)

        serialized = _serialize_message(message, viewer=self.sender)
        self.assertEqual(
            serialized["attachment_url"],
            "https://covise.net" + reverse("Messaging Message Media", args=[message.id]),
        )
        self.assertEqual(serialized["attachment_name"], "notes.txt")

        upload_args = mock_s3.upload_fileobj.call_args.args
        upload_extra_args = mock_s3.upload_fileobj.call_args.kwargs["ExtraArgs"]
        self.assertEqual(upload_args[1], "covise-posts-test")
        self.assertEqual(upload_args[2], message.attachment_file.name)
        self.assertEqual(upload_extra_args["ContentType"], "text/plain")
        self.assertEqual(upload_extra_args["ServerSideEncryption"], "AES256")


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class MessagingConversationNormalizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="messages-owner@example.com",
            password="safe-password-123",
            full_name="Messages Owner",
        )
        self.other_user = User.objects.create_user(
            email="messages-partner@example.com",
            password="safe-password-123",
            full_name="Messages Partner",
        )
        Profile.objects.create(
            user=self.user,
            full_name="Messages Owner",
            has_accepted_platform_agreement=True,
            onboarding_answers={
                "one_liner": "Building the next venture stack",
                "looking_for_type": "cofounder",
            },
        )
        Profile.objects.create(
            user=self.other_user,
            full_name="Messages Partner",
            has_accepted_platform_agreement=True,
            onboarding_answers={
                "one_liner": "Looking for strong operators",
                "looking_for_type": "partner",
            },
        )
        self.client.force_login(self.user)

    def _create_private_conversation(self, *, created_by):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=created_by,
        )
        conversation.participants.add(self.user, self.other_user)
        return conversation

    def _create_group_conversation(self, *, created_by, participant):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.GROUP,
            created_by=created_by,
            group_name="Founder Circle",
        )
        conversation.participants.add(self.user, participant)
        return conversation

    def _create_message_at(self, conversation, sender, body, created_at):
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            body=body,
        )
        Message.objects.filter(id=message.id).update(created_at=created_at)
        message.created_at = created_at
        conversation.last_message_at = created_at
        conversation.save(update_fields=["last_message_at"])
        return message

    def test_messages_page_defaults_to_newest_direct_conversation_and_removes_fake_placeholder_content(self):
        third_user = User.objects.create_user(
            email="messages-third@example.com",
            password="safe-password-123",
            full_name="Messages Third",
        )
        Profile.objects.create(
            user=third_user,
            full_name="Messages Third",
            has_accepted_platform_agreement=True,
        )

        older_direct = self._create_private_conversation(created_by=self.user)
        newer_direct = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=self.user,
        )
        newer_direct.participants.add(self.user, third_user)
        group_conversation = self._create_group_conversation(created_by=self.user, participant=self.other_user)

        now = timezone.now()
        self._create_message_at(older_direct, self.other_user, "Older direct thread", now - timedelta(hours=3))
        self._create_message_at(newer_direct, third_user, "Newest direct thread", now - timedelta(hours=2))
        self._create_message_at(group_conversation, self.other_user, "Newest group thread", now - timedelta(hours=1))

        response = self.client.get(reverse("Messages"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_conversation_id"], str(newer_direct.id))
        self.assertEqual(response.context["active_conversation"]["id"], str(newer_direct.id))
        self.assertContains(response, "Messages")
        self.assertNotContains(response, "Leena Al-Sabah")
        self.assertNotContains(response, "Active now")
        self.assertNotContains(response, "conversation-data")

    def test_messages_page_hides_private_conversation_without_recoverable_partner(self):
        valid_conversation = self._create_private_conversation(created_by=self.user)
        invalid_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=self.user,
        )
        invalid_conversation.participants.add(self.user)

        now = timezone.now()
        self._create_message_at(valid_conversation, self.other_user, "Healthy direct thread", now - timedelta(minutes=5))
        invalid_conversation.last_message_at = now
        invalid_conversation.save(update_fields=["last_message_at"])

        response = self.client.get(reverse("Messages"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_conversation_id"], str(valid_conversation.id))
        summary_ids = [item["id"] for item in response.context["conversation_summaries"]]
        self.assertIn(str(valid_conversation.id), summary_ids)
        self.assertNotIn(str(invalid_conversation.id), summary_ids)

    def test_send_message_repairs_private_conversation_missing_partner_when_partner_is_inferable(self):
        invalid_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=self.other_user,
        )
        invalid_conversation.participants.add(self.user)

        response = self.client.post(
            reverse("Send Message", args=[invalid_conversation.id]),
            data=json.dumps({"message": "Recovered thread message"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        invalid_conversation.refresh_from_db()
        participant_ids = set(invalid_conversation.participants.values_list("id", flat=True))
        self.assertEqual(participant_ids, {self.user.id, self.other_user.id})
        self.assertTrue(
            Message.objects.filter(
                conversation=invalid_conversation,
                sender=self.user,
                body="Recovered thread message",
            ).exists()
        )

    def test_private_conversation_integrity_repair_handles_extra_participants(self):
        extra_user = User.objects.create_user(
            email="messages-extra@example.com",
            password="safe-password-123",
            full_name="Messages Extra",
        )
        Profile.objects.create(
            user=extra_user,
            full_name="Messages Extra",
            has_accepted_platform_agreement=True,
        )
        invalid_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=self.other_user,
        )
        invalid_conversation.participants.add(self.user, self.other_user, extra_user)

        repaired = ensure_private_conversation_integrity(invalid_conversation, current_user=self.user)

        self.assertIsNotNone(repaired)
        participant_ids = set(repaired.participants.values_list("id", flat=True))
        self.assertEqual(participant_ids, {self.user.id, self.other_user.id})

    def test_start_private_conversation_redirects_to_canonical_merged_thread(self):
        accepted_request = ConversationRequest.objects.create(
            requester=self.user,
            recipient=self.other_user,
            status=ConversationRequest.Status.ACCEPTED,
            responded_at=timezone.now(),
        )
        first_conversation = self._create_private_conversation(created_by=self.user)
        second_conversation = self._create_private_conversation(created_by=self.other_user)

        first_message = Message.objects.create(
            conversation=first_conversation,
            sender=self.user,
            body="Earlier message",
        )
        second_message = Message.objects.create(
            conversation=second_conversation,
            sender=self.other_user,
            body="Latest message",
        )
        first_conversation.last_message_at = first_message.created_at
        first_conversation.save(update_fields=["last_message_at"])
        second_conversation.last_message_at = second_message.created_at
        second_conversation.save(update_fields=["last_message_at"])
        accepted_request.conversation = first_conversation
        accepted_request.save(update_fields=["conversation"])

        response = self.client.post(reverse("Start Private Conversation", args=[self.other_user.id]))

        merged_conversations = (
            Conversation.objects.filter(
                conversation_type=Conversation.ConversationType.PRIVATE,
                participants=self.user,
            )
            .filter(participants=self.other_user)
            .distinct()
        )
        self.assertEqual(merged_conversations.count(), 1)

        canonical = merged_conversations.first()
        self.assertIsNotNone(canonical)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('Messages')}?conversation={canonical.id}")
        self.assertTrue(
            ConversationRequest.objects.filter(id=accepted_request.id, conversation=canonical).exists()
        )

    @patch("covise_app.views.dispatch_notification")
    def test_start_private_conversation_creates_pending_request_and_redirects_to_requests_page(self, dispatch_mock):
        response = self.client.post(reverse("Start Private Conversation", args=[self.other_user.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Requests"))
        self.assertTrue(
            ConversationRequest.objects.filter(
                requester=self.user,
                recipient=self.other_user,
                status=ConversationRequest.Status.PENDING,
            ).exists()
        )
        dispatch_mock.assert_called_once()
        self.assertFalse(dispatch_mock.call_args.kwargs["send_email"])

    @patch("covise_app.views._merge_private_conversations")
    def test_start_private_conversation_still_creates_request_when_merge_fails_for_non_friend(self, merge_mock):
        merge_mock.side_effect = RuntimeError("merge exploded")

        response = self.client.post(reverse("Start Private Conversation", args=[self.other_user.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Requests"))
        self.assertTrue(
            ConversationRequest.objects.filter(
                requester=self.user,
                recipient=self.other_user,
                status=ConversationRequest.Status.PENDING,
            ).exists()
        )

    @patch("covise_app.views._merge_private_conversations")
    def test_start_private_conversation_cancels_outgoing_pending_request_before_merge(self, merge_mock):
        ConversationRequest.objects.create(
            requester=self.user,
            recipient=self.other_user,
            status=ConversationRequest.Status.PENDING,
        )

        response = self.client.post(
            reverse("Start Private Conversation", args=[self.other_user.id]),
            {"next": reverse("Public Profile", args=[self.other_user.id])},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Public Profile", args=[self.other_user.id]))
        self.assertEqual(
            ConversationRequest.objects.filter(
                requester=self.user,
                recipient=self.other_user,
            ).count(),
            0,
        )
        merge_mock.assert_not_called()

    @patch("covise_app.views._merge_private_conversations")
    def test_start_private_conversation_keeps_incoming_pending_request_redirect_to_requests(self, merge_mock):
        ConversationRequest.objects.create(
            requester=self.other_user,
            recipient=self.user,
            status=ConversationRequest.Status.PENDING,
        )

        response = self.client.post(reverse("Start Private Conversation", args=[self.other_user.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Requests"))
        self.assertEqual(
            ConversationRequest.objects.filter(
                requester=self.other_user,
                recipient=self.user,
                status=ConversationRequest.Status.PENDING,
            ).count(),
            1,
        )
        merge_mock.assert_not_called()

    @patch("covise_app.views._normalize_contact_pair")
    def test_start_private_conversation_redirects_to_messages_error_when_friend_normalization_fails(self, normalize_mock):
        ConversationRequest.objects.create(
            requester=self.user,
            recipient=self.other_user,
            status=ConversationRequest.Status.ACCEPTED,
            responded_at=timezone.now(),
        )
        normalize_mock.side_effect = RuntimeError("normalize exploded")

        response = self.client.post(reverse("Start Private Conversation", args=[self.other_user.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('Messages')}?error=conversation_unavailable")
        self.assertFalse(
            ConversationRequest.objects.filter(
                requester=self.user,
                recipient=self.other_user,
                status=ConversationRequest.Status.PENDING,
            ).exists()
        )

    @patch("covise_app.views.dispatch_notification")
    def test_start_private_conversation_still_redirects_when_notification_dispatch_fails(self, dispatch_mock):
        dispatch_mock.side_effect = RuntimeError("notification failed")

        response = self.client.post(reverse("Start Private Conversation", args=[self.other_user.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("Requests"))
        self.assertTrue(
            ConversationRequest.objects.filter(
                requester=self.user,
                recipient=self.other_user,
                status=ConversationRequest.Status.PENDING,
            ).exists()
        )

    @patch("covise_app.views._normalize_visible_private_conversations")
    def test_messages_page_does_not_run_request_time_normalization(self, normalize_mock):
        conversation = self._create_private_conversation(created_by=self.user)
        self._create_message_at(conversation, self.other_user, "Fresh direct thread", timezone.now())

        response = self.client.get(reverse("Messages"))

        self.assertEqual(response.status_code, 200)
        normalize_mock.assert_not_called()
        self.assertEqual(response.context["active_conversation_id"], str(conversation.id))

    def test_messages_page_shows_truthful_empty_state_when_only_group_conversations_exist(self):
        group_conversation = self._create_group_conversation(created_by=self.user, participant=self.other_user)
        self._create_message_at(group_conversation, self.other_user, "Group hello", timezone.now())

        response = self.client.get(reverse("Messages"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_conversation_id"], "")
        self.assertIsNone(response.context["active_conversation"])
        self.assertContains(response, "No direct conversation selected")
        self.assertNotContains(response, "Leena Al-Sabah")

    def test_messages_page_ignores_requested_group_thread_and_still_prefers_newest_direct_conversation(self):
        direct_conversation = self._create_private_conversation(created_by=self.user)
        group_conversation = self._create_group_conversation(created_by=self.user, participant=self.other_user)
        now = timezone.now()
        self._create_message_at(direct_conversation, self.other_user, "Direct hello", now)
        self._create_message_at(group_conversation, self.other_user, "Group hello", now + timedelta(minutes=1))

        response = self.client.get(
            reverse("Messages"),
            {"conversation": str(group_conversation.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_conversation_id"], str(direct_conversation.id))
        self.assertEqual(response.context["active_conversation"]["id"], str(direct_conversation.id))

    def test_messages_page_maps_conversation_unavailable_error_code_to_friendly_message(self):
        response = self.client.get(f"{reverse('Messages')}?error=conversation_unavailable")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["message_error"],
            "We couldn't open this conversation right now. Please try again.",
        )

    def test_messages_page_sets_csrf_cookie_for_send_actions(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.get(reverse("Messages"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", csrf_client.cookies)

    def test_messages_page_renders_safety_controls_and_locked_composer_shell(self):
        conversation = self._create_private_conversation(created_by=self.user)
        self._create_message_at(conversation, self.other_user, "Fresh direct thread", timezone.now())

        response = self.client.get(reverse("Messages"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="chatSafetyMenuBtn"')
        self.assertContains(response, 'id="blockUserBtn"')
        self.assertContains(response, 'id="reportUserBtn"')
        self.assertContains(response, 'id="composerLockOverlay"')
        self.assertContains(response, 'id="composerReportBtn"')
        self.assertContains(response, 'id="composerBlockToggleBtn"')

    @patch("covise_app.views._normalize_visible_private_conversations")
    def test_messages_state_endpoint_returns_split_payload_without_non_active_histories(self, normalize_mock):
        older_conversation = self._create_private_conversation(created_by=self.user)
        newer_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=self.user,
        )
        newer_conversation.participants.add(self.user, self.other_user)

        now = timezone.now()
        self._create_message_at(older_conversation, self.other_user, "Older conversation", now - timedelta(minutes=10))
        latest_message = self._create_message_at(newer_conversation, self.other_user, "Fresh sync message", now)

        state_response = self.client.get(
            reverse("Messages State"),
            {"conversation": str(newer_conversation.id)},
        )

        self.assertEqual(state_response.status_code, 200)
        payload = state_response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["active_conversation_id"], str(newer_conversation.id))
        self.assertEqual(len(payload["conversation_summaries"]), 2)
        self.assertEqual(payload["active_conversation"]["id"], str(newer_conversation.id))
        self.assertEqual(payload["active_conversation"]["messages"][-1]["text"], latest_message.body)
        self.assertNotIn("messages", payload["conversation_summaries"][0])
        normalize_mock.assert_not_called()

    def test_messages_state_honors_requested_group_conversation_for_in_app_switching(self):
        direct_conversation = self._create_private_conversation(created_by=self.user)
        group_conversation = self._create_group_conversation(created_by=self.user, participant=self.other_user)
        now = timezone.now()
        self._create_message_at(direct_conversation, self.other_user, "Direct hello", now)
        self._create_message_at(group_conversation, self.other_user, "Group hello", now + timedelta(minutes=1))

        state_response = self.client.get(
            reverse("Messages State"),
            {"conversation": str(group_conversation.id)},
        )

        self.assertEqual(state_response.status_code, 200)
        payload = state_response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["active_conversation_id"], str(group_conversation.id))
        self.assertEqual(payload["active_conversation"]["id"], str(group_conversation.id))
        self.assertEqual(payload["active_conversation"]["conversation_type"], Conversation.ConversationType.GROUP)

    def test_messages_history_endpoint_returns_older_messages_in_oldest_to_newest_order(self):
        conversation = self._create_private_conversation(created_by=self.user)
        start = timezone.now() - timedelta(hours=2)
        for index in range(60):
            sender = self.user if index % 2 == 0 else self.other_user
            self._create_message_at(
                conversation,
                sender,
                f"Message {index}",
                start + timedelta(minutes=index),
            )

        state_response = self.client.get(
            reverse("Messages State"),
            {"conversation": str(conversation.id)},
        )

        self.assertEqual(state_response.status_code, 200)
        active_conversation = state_response.json()["active_conversation"]
        self.assertEqual(len(active_conversation["messages"]), 50)
        self.assertTrue(active_conversation["has_older_messages"])

        history_response = self.client.get(
            reverse("Messages History", args=[conversation.id]),
            {"before": active_conversation["oldest_loaded_message_id"]},
        )

        self.assertEqual(history_response.status_code, 200)
        history_payload = history_response.json()
        self.assertTrue(history_payload["ok"])
        self.assertEqual([item["text"] for item in history_payload["messages"]], [f"Message {index}" for index in range(10)])
        self.assertFalse(history_payload["has_older_messages"])

    def test_messages_state_marks_conversation_locked_when_current_user_blocked_partner(self):
        conversation = self._create_private_conversation(created_by=self.user)
        BlockedUser.objects.create(blocker=self.user, blocked=self.other_user)

        state_response = self.client.get(
            reverse("Messages State"),
            {"conversation": str(conversation.id)},
        )

        self.assertEqual(state_response.status_code, 200)
        active_conversation = state_response.json()["active_conversation"]
        self.assertTrue(active_conversation["blocked_by_current_user"])
        self.assertFalse(active_conversation["blocked_by_partner"])
        self.assertTrue(active_conversation["messaging_blocked"])
        self.assertIn("You blocked this user", active_conversation["messaging_lock_reason"])

    def test_messages_state_marks_conversation_locked_when_partner_blocked_current_user(self):
        conversation = self._create_private_conversation(created_by=self.user)
        BlockedUser.objects.create(blocker=self.other_user, blocked=self.user)

        state_response = self.client.get(
            reverse("Messages State"),
            {"conversation": str(conversation.id)},
        )

        self.assertEqual(state_response.status_code, 200)
        active_conversation = state_response.json()["active_conversation"]
        self.assertFalse(active_conversation["blocked_by_current_user"])
        self.assertTrue(active_conversation["blocked_by_partner"])
        self.assertTrue(active_conversation["messaging_blocked"])
        self.assertIn("blocked you", active_conversation["messaging_lock_reason"])

    @patch("covise_app.notifications.send_notification_email")
    def test_send_message_creates_pending_notification_without_inline_email_send(self, send_email_mock):
        conversation = self._create_private_conversation(created_by=self.user)

        response = self.client.post(
            reverse("Send Message", args=[conversation.id]),
            data=json.dumps({"message": "Fresh sync message"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        notification = Notification.objects.get(
            recipient=self.other_user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
        )
        self.assertEqual(notification.target_url, f"/messages/?conversation={conversation.id}")
        self.assertIsNone(notification.emailed_at)
        send_email_mock.assert_not_called()

    def test_send_notification_emails_command_marks_pending_notifications_processed(self):
        notification = Notification.objects.create(
            recipient=self.other_user,
            actor=self.user,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="New message",
            body="You have a new message.",
            target_url="/messages/",
        )

        with patch("covise_app.notifications.RESEND_API_KEY", ""):
            call_command("send_notification_emails")

        notification.refresh_from_db()
        self.assertIsNotNone(notification.emailed_at)

    def test_accept_request_succeeds_with_duplicate_private_threads_present(self):
        incoming_request = ConversationRequest.objects.create(
            requester=self.other_user,
            recipient=self.user,
            status=ConversationRequest.Status.PENDING,
        )
        older_conversation = self._create_private_conversation(created_by=self.user)
        newer_conversation = self._create_private_conversation(created_by=self.other_user)

        older_message = Message.objects.create(
            conversation=older_conversation,
            sender=self.user,
            body="Older thread",
        )
        newer_message = Message.objects.create(
            conversation=newer_conversation,
            sender=self.other_user,
            body="Newer thread",
        )
        older_conversation.last_message_at = older_message.created_at
        older_conversation.save(update_fields=["last_message_at"])
        newer_conversation.last_message_at = newer_message.created_at
        newer_conversation.save(update_fields=["last_message_at"])

        response = self.client.post(
            reverse("Respond To Conversation Request", args=[incoming_request.id, "accept"])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        incoming_request.refresh_from_db()
        self.assertEqual(incoming_request.status, ConversationRequest.Status.ACCEPTED)
        self.assertIsNotNone(incoming_request.conversation_id)
        merged_conversations = (
            Conversation.objects.filter(
                conversation_type=Conversation.ConversationType.PRIVATE,
                participants=self.user,
            )
            .filter(participants=self.other_user)
            .distinct()
        )
        self.assertEqual(merged_conversations.count(), 1)

    @patch("covise_app.views.broadcast_chat_message")
    @patch("covise_app.messaging.dispatch_notification")
    @patch("covise_app.views.dispatch_notification")
    def test_accepting_founders_request_sends_welcome_message(
        self,
        accept_dispatch_mock,
        _message_dispatch_mock,
        broadcast_mock,
    ):
        founders_user = User.objects.create_user(
            email="founders@covise.net",
            password="safe-password-123",
            full_name="CoVise Team",
        )
        Profile.objects.create(
            user=founders_user,
            full_name="CoVise Team",
            has_accepted_platform_agreement=True,
        )
        incoming_request = ConversationRequest.objects.create(
            requester=founders_user,
            recipient=self.user,
            status=ConversationRequest.Status.PENDING,
        )

        response = self.client.post(
            reverse("Respond To Conversation Request", args=[incoming_request.id, "accept"])
        )

        self.assertEqual(response.status_code, 200)
        incoming_request.refresh_from_db()
        self.assertEqual(incoming_request.status, ConversationRequest.Status.ACCEPTED)
        self.assertIsNotNone(incoming_request.conversation_id)
        welcome_message = Message.objects.get(
            conversation=incoming_request.conversation,
            sender=founders_user,
        )
        self.assertEqual(
            welcome_message.body,
            "Welcome to CoVise\n\nthis is your direct chat with the CoVise team.\n\nIf you have any questions, run into any issues, or need help with anything, feel free to message here anytime.",
        )
        self.assertTrue(
            MessageReceipt.objects.filter(
                message=welcome_message,
                user=self.user,
                status=MessageReceipt.Status.DELIVERED,
            ).exists()
        )
        broadcast_mock.assert_called_once()
        accept_dispatch_mock.assert_called_once()
        self.assertFalse(accept_dispatch_mock.call_args.kwargs["send_email"])


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class MessagingMediaEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="media-owner@example.com",
            password="safe-password-123",
            full_name="Media Owner",
        )
        self.other_user = User.objects.create_user(
            email="media-partner@example.com",
            password="safe-password-123",
            full_name="Media Partner",
        )
        self.outsider = User.objects.create_user(
            email="media-outsider@example.com",
            password="safe-password-123",
            full_name="Media Outsider",
        )
        onboarding_answers = {
            "one_liner": "Building faster founder messaging.",
            "looking_for_type": "partner",
        }
        Profile.objects.create(
            user=self.user,
            full_name="Media Owner",
            has_accepted_platform_agreement=True,
            onboarding_answers=onboarding_answers,
        )
        Profile.objects.create(
            user=self.other_user,
            full_name="Media Partner",
            has_accepted_platform_agreement=True,
            onboarding_answers=onboarding_answers,
        )
        Profile.objects.create(
            user=self.outsider,
            full_name="Media Outsider",
            has_accepted_platform_agreement=True,
            onboarding_answers=onboarding_answers,
        )
        UserPreference.objects.create(user=self.user)
        UserPreference.objects.create(user=self.other_user)
        UserPreference.objects.create(user=self.outsider)

        Profile.objects.filter(user=self.user).update(profile_image="profile_images/avatar.png")
        self.user.profile.refresh_from_db()

        self.conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=self.user,
        )
        self.conversation.participants.add(self.user, self.other_user)
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            body="Attachment",
            message_type=Message.MessageType.FILE,
            attachment_file="chat_media/notes.txt",
            attachment_name="notes.txt",
            attachment_content_type="text/plain",
            attachment_size=23,
        )

        self.client.force_login(self.user)
        self.outsider_client = Client()
        self.outsider_client.force_login(self.outsider)

    @patch("covise_app.views._public_media_url", return_value="https://cdn.example/profile_images/avatar.png")
    def test_messaging_avatar_endpoint_redirects_with_public_cache_headers(self, _mock_public_media_url):
        url = reverse("Messaging Avatar", args=[self.user.id])

        first_response = self.client.get(url)
        second_response = self.client.get(url)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(first_response["Location"], second_response["Location"])
        self.assertEqual(first_response["Location"], "https://cdn.example/profile_images/avatar.png")
        self.assertIn("public", first_response["Cache-Control"])

    @patch("covise_app.views._safe_media_url", return_value="https://signed.example/profile_images/avatar.png?sig=abc")
    def test_messaging_avatar_endpoint_uses_private_signed_redirect_when_storage_requires_signed_urls(self, _mock_safe_media_url):
        url = reverse("Messaging Avatar", args=[self.user.id])
        storage = self.user.profile.profile_image.storage

        with patch.object(storage, "_use_s3", return_value=True), patch.object(
            storage,
            "_use_signed_urls",
            return_value=True,
        ), patch.object(storage, "_presigned_url_expiry", return_value=3600):
            response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://signed.example/profile_images/avatar.png?sig=abc")
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("max-age=3540", response["Cache-Control"])

    @patch("covise_app.views._safe_media_url", return_value="https://cdn.example/chat_media/notes.txt")
    def test_messaging_message_media_endpoint_redirects_for_participants_only(self, _mock_safe_media_url):
        url = reverse("Messaging Message Media", args=[self.message.id])

        participant_response = self.client.get(url)
        outsider_response = self.outsider_client.get(url)

        self.assertEqual(participant_response.status_code, 302)
        self.assertEqual(participant_response["Location"], "https://cdn.example/chat_media/notes.txt")
        self.assertIn("private", participant_response["Cache-Control"])
        self.assertEqual(outsider_response.status_code, 404)
