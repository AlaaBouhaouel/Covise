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
            if not profile.has_accepted_platform_agreement and not is_exempt:
                return redirect(f"{reverse('Agreement')}?next={path}")

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
