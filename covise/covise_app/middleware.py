from django.shortcuts import redirect
from django.urls import reverse

from covise_app.models import Profile


class AgreementRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            profile, _ = Profile.objects.get_or_create(user=user)
            exempt_paths = {
                reverse("Agreement"),
                reverse("Onboarding"),
                reverse("Onboarding Submit"),
                reverse("Onboarding Final"),
                reverse("Loading"),
                reverse("Logout"),
                reverse("Terms"),
                reverse("Privacy"),
                reverse("Security"),
            }
            path = request.path_info or ""
            is_exempt = (
                path in exempt_paths
                or path.startswith("/admin/")
                or path.startswith("/static/")
                or path.startswith("/media/")
            )
            if not self._has_profile_completion(profile) and not is_exempt:
                return redirect(f"{reverse('Onboarding')}?next={path}")

            if not profile.has_accepted_platform_agreement and not is_exempt:
                return redirect(f"{reverse('Agreement')}?next={path}")

            if getattr(profile, "requires_intro_post", False) and not self._intro_post_request_allowed(request):
                return redirect(reverse("Create Post"))

            if profile.is_account_paused and not self._paused_request_allowed(request):
                return redirect(f"{reverse('Settings')}?account_pause=blocked")

        return self.get_response(request)

    def _paused_request_allowed(self, request):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return True

        view_name = getattr(getattr(request, "resolver_match", None), "view_name", "") or ""
        path = request.path_info or ""
        allowed_paths = {
            reverse("Agreement"),
            reverse("Settings"),
            reverse("Request Data Export"),
            reverse("Request Account Pause"),
            reverse("Request Data Deletion"),
            reverse("Delete Account"),
            reverse("Logout"),
        }
        if path in allowed_paths:
            if path != reverse("Settings"):
                return True
            return request.POST.get("save_section", "").strip() == "security"
        if view_name in {
            "Agreement",
            "Settings",
            "Request Data Export",
            "Request Account Pause",
            "Request Data Deletion",
            "Delete Account",
            "Logout",
        }:
            if view_name != "Settings":
                return True
            return request.POST.get("save_section", "").strip() == "security"

        return False

    def _intro_post_request_allowed(self, request):
        path = request.path_info or ""
        allowed_paths = {
            reverse("Home"),
            reverse("Create Post"),
            reverse("Agreement"),
            reverse("Onboarding"),
            reverse("Onboarding Submit"),
            reverse("Onboarding Final"),
            reverse("Loading"),
            reverse("Logout"),
            reverse("Terms"),
            reverse("Privacy"),
            reverse("Security"),
        }
        if path in allowed_paths:
            return True
        return False

    def _has_profile_completion(self, profile):
        if not profile:
            return False

        onboarding_answers = self._clean_onboarding_answers(getattr(profile, "onboarding_answers", {}))
        one_liner_value = onboarding_answers.get("one_liner", getattr(profile, "one_liner", None))
        looking_for_value = onboarding_answers.get("looking_for_type", getattr(profile, "looking_for_type", None))
        legacy_onboarding = bool(
            getattr(profile, "source_onboarding_response_id", None)
            or str(getattr(profile, "flow_name", "") or "").strip()
        )
        return (bool(self._flatten_text_values(one_liner_value)) and bool(self._flatten_text_values(looking_for_value))) or legacy_onboarding

    def _clean_onboarding_answers(self, answers):
        if not isinstance(answers, dict):
            return {}
        cleaned = {}
        for key, value in answers.items():
            if value in (None, "", [], {}, ()):
                continue
            cleaned[key] = value
        return cleaned

    def _flatten_text_values(self, value):
        if value in (None, "", [], {}, ()):
            return []
        if isinstance(value, dict):
            items = []
            for item in value.values():
                items.extend(self._flatten_text_values(item))
            return items
        if isinstance(value, (list, tuple, set)):
            items = []
            for item in value:
                items.extend(self._flatten_text_values(item))
            return items
        text = str(value).strip()
        return [text] if text else []
