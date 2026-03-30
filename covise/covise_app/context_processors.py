from django.urls import reverse


def _initials_from_name(name, email=""):
    if name:
        parts = [part for part in name.strip().split() if part]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        if len(parts) == 1:
            return parts[0][:2].upper()

    if email:
        return email[:2].upper()

    return "CV"


def user_ui_context(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return {
            "ui_user": {
                "is_authenticated": False,
                "display_name": "",
                "first_name": "",
                "email": "",
                "bio": "",
                "linkedin_url": "",
                "github_url": "",
                "avatar_initials": "CV",
                "avatar_url": "",
                "profile_href": reverse("Login"),
                "has_profile_content": False,
            }
        }
    display_name = user.full_name.strip() if user.full_name else user.email.split("@")[0]
    parts = display_name.split()

    first_name = parts[0] if parts else ""
    avatar_url = ""
    bio = ""
    linkedin_url = ""
    github_url = ""
    has_profile_content = False

    profile = getattr(user, "profile", None)
    if profile:
        bio = profile.bio or ""
        linkedin_url = profile.linkedin or ""
        github_url = profile.github or ""
        has_profile_content = any([
            profile.bio,
            profile.linkedin,
            profile.github,
            profile.country,
            profile.phone_number,
        ])

    return {
        "ui_user": {
            "is_authenticated": True,
            "display_name": display_name,
            "first_name": first_name,
            "email": user.email,
            "bio": bio,
            "linkedin_url": linkedin_url,
            "github_url": github_url,
            "avatar_initials": _initials_from_name(display_name, user.email),
            "avatar_url": avatar_url,
            "profile_href": reverse("Profile"),
            "has_profile_content": has_profile_content,
        }
    }
