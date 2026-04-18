import logging

from django.shortcuts import redirect
from django.urls import reverse

from covise_app.models import Profile

logger = logging.getLogger(__name__)


class AgreementRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            try:
                profile, _ = Profile.objects.get_or_create(user=user)
                exempt_paths = {
                    reverse("Agreement"),
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
                    logger.info(
                        "Agreement redirect for user=%s path=%s",
                        getattr(user, "email", ""),
                        path,
                    )
                    return redirect(f"{reverse('Agreement')}?next={path}")
            except Exception:
                logger.exception(
                    "AgreementRequiredMiddleware failed for user=%s path=%s",
                    getattr(user, "email", ""),
                    request.path_info or "",
                )
                raise

        return self.get_response(request)
