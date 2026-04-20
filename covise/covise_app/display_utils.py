def public_display_name(user, fallback="CoVise Member"):
    if not user:
        return ""

    full_name = str(getattr(user, "full_name", "") or "").strip()
    if full_name:
        return full_name

    profile = getattr(user, "profile", None)
    profile_name = str(getattr(profile, "full_name", "") or "").strip() if profile else ""
    if profile_name:
        return profile_name

    return fallback
