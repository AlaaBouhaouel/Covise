import json
import re
from functools import lru_cache
from pathlib import Path
from django.urls import reverse
from django.utils.timesince import timesince

from covise_app.models import BlockedUser, SavedPost


def _value_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            items.extend(_value_list(item))
        return items
    if isinstance(value, dict):
        items = []
        for item in value.values():
            items.extend(_value_list(item))
        return items

    text = str(value).strip()
    return [text] if text else []


def _value_text(value, separator=", "):
    return separator.join(_value_list(value))


def _score_value(value, default):
    for item in _value_list(value):
        match = re.search(r"\d+", item)
        if match:
            score = int(match.group())
            return max(0, min(score, 100))
    return default


def _tag_dicts(values, palette):
    tags = []
    for index, label in enumerate(_value_list(values)):
        tags.append(
            {
                "label": label,
                "color": palette[index % len(palette)],
            }
        )
    return tags


def _preferences_dict(preferences):
    return {
        "profile_visibility": getattr(preferences, "profile_visibility", "everyone"),
        "read_profile_data": getattr(preferences, "read_profile_data", True),
        "show_conviction_score": getattr(preferences, "show_conviction_score", True),
        "show_cv_to_matches": getattr(preferences, "show_cv_to_matches", True),
        "show_linkedin_to_matches": getattr(preferences, "show_linkedin_to_matches", True),
        "appear_in_search": getattr(preferences, "appear_in_search", True),
        "pause_matching": getattr(preferences, "pause_matching", False),
        "ai_enabled": getattr(preferences, "ai_enabled", True),
        "ai_read_messages": getattr(preferences, "ai_read_messages", True),
        "ai_read_workspace": getattr(preferences, "ai_read_workspace", True),
        "ai_post_updates": getattr(preferences, "ai_post_updates", False),
        "ai_send_messages": getattr(preferences, "ai_send_messages", False),
        "ai_edit_workspace": getattr(preferences, "ai_edit_workspace", False),
        "ai_manage_milestones": getattr(preferences, "ai_manage_milestones", False),
        "two_factor_enabled": getattr(preferences, "two_factor_enabled", False),
        "email_new_match": getattr(preferences, "email_new_match", True),
        "email_new_message": getattr(preferences, "email_new_message", True),
        "email_connection_request": getattr(preferences, "email_connection_request", True),
        "email_request_accepted": getattr(preferences, "email_request_accepted", True),
        "email_milestone_reminder": getattr(preferences, "email_milestone_reminder", True),
        "email_workspace_activity": getattr(preferences, "email_workspace_activity", False),
        "email_platform_updates": getattr(preferences, "email_platform_updates", True),
        "email_marketing": getattr(preferences, "email_marketing", False),
        "in_app_new_match": getattr(preferences, "in_app_new_match", True),
        "in_app_new_message": getattr(preferences, "in_app_new_message", True),
        "in_app_connection_request": getattr(preferences, "in_app_connection_request", True),
        "in_app_request_accepted": getattr(preferences, "in_app_request_accepted", True),
        "in_app_milestone_reminder": getattr(preferences, "in_app_milestone_reminder", True),
        "in_app_workspace_activity": getattr(preferences, "in_app_workspace_activity", False),
        "in_app_platform_updates": getattr(preferences, "in_app_platform_updates", True),
        "in_app_marketing": getattr(preferences, "in_app_marketing", False),
        "email_frequency": getattr(preferences, "email_frequency", "instant"),
        "preferred_cofounder_types": getattr(preferences, "preferred_cofounder_types", []),
        "preferred_industries": getattr(preferences, "preferred_industries", []),
        "preferred_gcc_markets": getattr(preferences, "preferred_gcc_markets", []),
        "minimum_commitment": getattr(preferences, "minimum_commitment", "Either"),
        "open_to_foreign_founders": getattr(preferences, "open_to_foreign_founders", True),
    }


@lru_cache(maxsize=1)
def get_onboarding_skill_config():
    flow_path = Path(__file__).resolve().parent / "boarding.json"
    default_config = {"options": [], "max_selected": 8}
    try:
        with flow_path.open(encoding="utf-8-sig") as handle:
            flow = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default_config

    for step in flow.get("steps", []):
        for field in step.get("fields", []):
            if field.get("id") != "skills":
                continue
            options = [str(option).strip() for option in field.get("options", []) if str(option).strip()]
            return {
                "options": options,
                "max_selected": int(field.get("max_selected") or 8),
            }
    return default_config


def _cofounder_badge_state(profile):
    if not profile:
        return False, False

    onboarding_answers = getattr(profile, "onboarding_answers", {}) or {}

    def normalized_values(value):
        if isinstance(value, dict):
            raw_items = value.values()
        elif isinstance(value, (list, tuple, set)):
            raw_items = value
        elif value in (None, "", [], {}, ()):
            raw_items = []
        else:
            raw_items = [value]
        return [
            " ".join(str(item or "").strip().lower().replace("/", " ").replace("-", " ").split())
            for item in raw_items
            if str(item or "").strip()
        ]

    cofounder_count_values = (
        normalized_values(getattr(profile, "cofounders_needed", None))
        + normalized_values(onboarding_answers.get("cofounders_needed"))
    )
    eligible = any(value not in {"0", "none", "no"} for value in cofounder_count_values)
    if not eligible:
        desired_partner_values = (
            normalized_values(getattr(profile, "looking_for_type", None))
            + normalized_values(onboarding_answers.get("looking_for_type"))
        )
        eligible = any("cofounder" in value or "co founder" in value for value in desired_partner_values)

    explicit_visibility = onboarding_answers.get("show_cofounder_badge")
    if isinstance(explicit_visibility, str):
        explicit_visibility = explicit_visibility.strip().lower() in {"1", "true", "yes", "on"}
    visible = eligible and (True if explicit_visibility is None else bool(explicit_visibility))
    return eligible, visible


def build_saved_post_items(user):
    blocked_user_ids = list(
        BlockedUser.objects.filter(blocker=user).values_list("blocked_id", flat=True)
    )
    saved_posts = list(
        SavedPost.objects.filter(user=user)
        .exclude(post__user_id__in=blocked_user_ids)
        .select_related("post", "post__user")
        .order_by("-created_at")
    )
    return [
        {
            "id": saved_post.post.id,
            "title": getattr(saved_post.post, "title", "") or (getattr(saved_post.post, "content", "")[:80] or "Untitled post"),
            "author": getattr(saved_post.post.user, "full_name", "") or getattr(saved_post.post.user, "email", ""),
            "saved_at": f"{timesince(saved_post.created_at)} ago",
        }
        for saved_post in saved_posts
    ]


def build_ui_user_context(user):
    profile = getattr(user, "profile", None)

    display_name = (getattr(user, "full_name", "") or "").strip()
    if not display_name and profile:
        display_name = (getattr(profile, "full_name", "") or "").strip()
    if not display_name:
        display_name = (getattr(user, "email", "") or "CoVise User").split("@")[0]

    parts = [part for part in display_name.split() if part]
    if len(parts) >= 2:
        avatar_initials = (parts[0][0] + parts[1][0]).upper()
    elif parts:
        avatar_initials = parts[0][:2].upper()
    else:
        avatar_initials = "CV"

    return {
        "display_name": display_name,
        "email": getattr(user, "email", ""),
        "bio": getattr(profile, "bio", "") if profile else "",
        "linkedin_url": getattr(profile, "linkedin", "") if profile else "",
        "github_url": getattr(profile, "github", "") if profile else "",
        "proof_of_work_url": getattr(profile, "proof_of_work_url", "") if profile else "",
        "avatar_initials": avatar_initials,
        "avatar_url": getattr(getattr(profile, "profile_image", None), "url", "") if profile and getattr(profile, "profile_image", None) else "",
    }


def _experience_items(profile):
    items = []

    current_role = _value_text(getattr(profile, "current_role", None))
    years_experience = _value_text(getattr(profile, "years_experience", None))
    skills = _value_text(getattr(profile, "skills", None))
    availability = _value_text(getattr(profile, "availability", None))
    industry = _value_text(getattr(profile, "industry", None))

    if current_role or years_experience:
        items.append(
            {
                "title": current_role or "Current Role",
                "date": years_experience or "Experience not added yet",
                "desc": "Your current role and experience level shape how CoVise positions you to potential matches.",
            }
        )

    if skills:
        items.append(
            {
                "title": "Core Skills",
                "date": "Capabilities",
                "desc": skills,
            }
        )

    if availability or industry:
        items.append(
            {
                "title": "Operating Context",
                "date": availability or "Availability not added yet",
                "desc": industry or "Add your industry focus to help others understand your background faster.",
            }
        )

    if not items:
        items.append(
            {
                "title": "Add your experiences",
                "date": " ",
                "desc": "Add your current role, years of experience, and strengths to make your profile more credible to potential co-founders.",
            }
        )

    return items


def active_projects(user):
    profile = getattr(user, "profile", None)
    defaults = {
                "name": "Add your active projects",
                "description": "Show potential co-founders what you're working on and your progress to date.",
            }
        

    if not profile:
        return defaults
    
    projects = _value_list(getattr(profile, "active_projects", None))
    
    if not projects:
        return defaults
    
    if len(projects) > 3:
        projects = projects[:3]

    return [{"name": p, "description": ""} for p in projects]

def build_profile_context(user):
    profile = getattr(user, "profile", None)
    preferences = getattr(user, "preferences", None)

    defaults = {
        "headline": "Complete your profile",
        "location": "Add your location",
        "what_im_building": "Add your one-liner and market focus to show founders what you're building.",
        "what_im_building_tags": [],
        "looking_for": "Add the skills, commitment, and collaborator type you are looking for.",
        "looking_for_tags": [],
        "experience_items": [
            {
                "title": "Build out your experience",
                "date": "Profile in progress",
                "desc": "Add your current role, years of experience, and strengths to make your profile more credible to potential co-founders.",
            }
        ],
        "conviction_score": 0,
        "conviction_title": "Profile In Progress",
        "conviction_sub": "Complete your onboarding answers to unlock a more accurate founder conviction readout.",
        "conviction_metrics": [
            {"label": "Commitment Level", "value": 0, "color": "green"},
            {"label": "Risk Tolerance", "value": 0, "color": "red"},
            {"label": "Execution History", "value": 0, "color": "blue"},
            {"label": "Leadership Style", "value": 0, "color": "gold"},
        ],
        "preferences": _preferences_dict(preferences),
    }

    if not profile:
        return defaults

    commitment = _score_value(profile.commitment_level, 0)
    risk = _score_value(profile.risk_tolerance, 0)
    execution = _score_value(profile.execution_history, 0)
    leadership = _score_value(profile.leadership_style, 0)
    conviction_score = round((commitment + risk + execution + leadership) / 4)

    if conviction_score >= 80:
        conviction_title = "Highly Committed Founder"
    elif conviction_score >= 60:
        conviction_title = "Promising Founder Profile"
    elif conviction_score >= 35:
        conviction_title = "Early Signal Profile"
    else:
        conviction_title = "Profile In Progress"

    conviction_sub = (
        "This score is built from your onboarding answers around commitment, risk, execution, and leadership."
        if conviction_score
        else defaults["conviction_sub"]
    )

    what_im_building_tags = _tag_dicts(
        [profile.industry, profile.target_market, profile.stage],
        ["blue", "blue", "green", "gold"],
    )
    looking_for_tags = _tag_dicts(
        [profile.cofounder_commitment, profile.looking_for_type, profile.looking_for_skills],
        ["green", "pink", "gold", "blue"],
    )

    return {
        "headline": profile.bio or _value_text(profile.one_liner) or defaults["headline"],
        "location": profile.country or _value_text(profile.home_country) or defaults["location"],
        "what_im_building": _value_text(profile.one_liner) or defaults["what_im_building"],
        "what_im_building_tags": what_im_building_tags,
        "looking_for": _value_text(profile.looking_for_skills) or _value_text(profile.looking_for_type) or defaults["looking_for"],
        "looking_for_tags": looking_for_tags,
        "experience_items": _experience_items(profile),
        "conviction_score": conviction_score,
        "conviction_title": conviction_title,
        "conviction_sub": conviction_sub,
        "conviction_metrics": [
            {"label": "Commitment Level", "value": commitment, "color": "green"},
            {"label": "Risk Tolerance", "value": risk, "color": "red"},
            {"label": "Execution History", "value": execution, "color": "blue"},
            {"label": "Leadership Style", "value": leadership, "color": "gold"},
        ],
        "preferences": _preferences_dict(preferences),
    }


def build_profile_card_context(user):
    profile_page = build_profile_context(user)
    profile = getattr(user, "profile", None)

    display_name = (getattr(user, "full_name", "") or "").strip()
    if not display_name and profile:
        display_name = (getattr(profile, "full_name", "") or "").strip()
    if not display_name:
        display_name = (getattr(user, "email", "") or "CoVise User").split("@")[0]

    parts = [part for part in display_name.split() if part]
    if len(parts) >= 2:
        avatar_initials = (parts[0][0] + parts[1][0]).upper()
    elif parts:
        avatar_initials = parts[0][:2].upper()
    else:
        avatar_initials = "CV"

    current_role = _value_text(getattr(profile, "current_role", None)) if profile else ""
    location = profile_page["location"]
    role_location = " - ".join([value for value in [current_role, location] if value]).upper()
    if not role_location:
        role_location = "PROFILE IN PROGRESS"

    role_label = current_role or "Founder"
    location_label = location if location and location != "Add your location" else "Location not added yet"
    stage = _value_text(getattr(profile, "stage", None)) if profile else ""
    commitment = _value_text(getattr(profile, "cofounder_commitment", None)) if profile else ""
    if not commitment:
        commitment = _value_text(getattr(profile, "commitment_level", None)) if profile else ""
    industry = _value_text(getattr(profile, "industry", None)) if profile else ""
    market = _value_text(getattr(profile, "target_market", None)) if profile else ""

    skills = _value_list(getattr(profile, "skills", None)) if profile else []
    if not skills:
        skills = ["Add your skills"]

    looking_for = []
    if profile:
        looking_for = _value_list(getattr(profile, "looking_for_skills", None))
        if not looking_for:
            looking_for = _value_list(getattr(profile, "looking_for_type", None))
    if not looking_for:
        looking_for = ["Add what you're looking for"]

    about = _value_text(getattr(profile, "one_liner", None)) if profile else ""
    if not about:
        about = profile_page["headline"]
    _cofounder_badge_available, show_cofounder_badge = _cofounder_badge_state(profile)

    return {
        "avatar_initials": avatar_initials,
        "display_name": display_name,
        "role": role_label,
        "location": location_label,
        "role_location": role_location,
        "score": profile_page["conviction_score"],
        "stage": stage or "Profile in progress",
        "commitment": commitment or "Flexible",
        "industry": industry or "Not shared yet",
        "market": market or location_label,
        "skills": skills,
        "looking_for": looking_for,
        "about": about,
        "show_cofounder_badge": show_cofounder_badge,
        "share_url": reverse("Public Profile", args=[user.id]),
    }


def build_settings_context(user):
    profile = getattr(user, "profile", None)
    preferences = getattr(user, "preferences", None)
    email = getattr(user, "email", "") or ""
    display_name = getattr(user, "full_name", "") or ""
    blocked_relationships = list(
        BlockedUser.objects.filter(blocker=user)
        .select_related("blocked", "blocked__profile")
        .order_by("-created_at")
    )

    if not display_name and profile:
        display_name = getattr(profile, "full_name", "") or ""
    if not display_name and email:
        display_name = email.split("@")[0]

    skill_config = get_onboarding_skill_config()
    skill_options = skill_config["options"]
    skill_option_set = set(skill_options)
    selected_skills = [
        skill for skill in _value_list(getattr(profile, "skills", None)) if skill in skill_option_set
    ] if profile else []
    location = ""
    if profile:
        location = getattr(profile, "country", "") or _value_text(getattr(profile, "home_country", None))
    cofounder_badge_available, show_cofounder_badge = _cofounder_badge_state(profile)

    saved_post_items = build_saved_post_items(user)
    blocked_user_items = [
        {
            "id": relationship.blocked.id,
            "display_name": relationship.blocked.full_name or relationship.blocked.email.split("@")[0],
            "email": relationship.blocked.email,
            "avatar_initials": getattr(relationship.blocked, "avatar_initials", "CV"),
            "blocked_at": f"{timesince(relationship.created_at)} ago",
        }
        for relationship in blocked_relationships
    ]

    return {
        "display_name": display_name,
        "email": email,
        "sign_in_count": getattr(user, "sign_in_count", 0),
        "last_login": getattr(user, "last_login", None),
        "has_seen_interactive_demo": getattr(user, "has_seen_interactive_demo", False),
        "phone_number": getattr(profile, "phone_number", "") if profile else "",
        "current_role": _value_text(getattr(profile, "current_role", None)) if profile else "",
        "plan": getattr(profile, "plan", "Free") if profile else "Free",
        "linkedin_url": getattr(profile, "linkedin", "") if profile else "",
        "github_url": getattr(profile, "github", "") if profile else "",
        "proof_of_work_url": getattr(profile, "proof_of_work_url", "") if profile else "",
        "skills_text": _value_text(getattr(profile, "skills", None)) if profile else "",
        "skills_options": skill_options,
        "skills_selected": selected_skills,
        "skills_max_selected": skill_config["max_selected"],
        "location": location,
        "nationality": getattr(profile, "nationality", "") if profile else "",
        "bio": getattr(profile, "bio", "") if profile else "",
        "cofounder_badge_available": cofounder_badge_available,
        "show_cofounder_badge": show_cofounder_badge,
        "saved_posts": saved_post_items,
        "saved_posts_preview": saved_post_items[:2],
        "saved_posts_has_more": len(saved_post_items) > 2,
        "blocked_users": blocked_user_items,
        "platform_agreement_accepted": getattr(profile, "has_accepted_platform_agreement", False) if profile else False,
        "platform_agreement_accepted_at": getattr(profile, "platform_agreement_accepted_at", None) if profile else None,
        "platform_agreement_version": getattr(profile, "platform_agreement_version", "2026.04") if profile else "2026.04",
        "receive_email_notifications": getattr(profile, "receive_email_notifications", True) if profile else True,
        "preferences": _preferences_dict(preferences),
    }


def build_ai_user_context(user):
    profile = getattr(user, "profile", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}

    return {
        "user": {
            "email": user.email,
            "full_name": getattr(user, "full_name", "") or "",
        },
        "profile": {
            "bio": getattr(profile, "bio", "") or "",
            "country": getattr(profile, "country", "") or "",
            "linkedin": getattr(profile, "linkedin", "") or "",
            "user_type": getattr(profile, "user_type", None),
            "industry": getattr(profile, "industry", None),
            "stage": getattr(profile, "stage", None),
            "target_market": getattr(profile, "target_market", None),
            "one_liner": getattr(profile, "one_liner", None),
            "skills": getattr(profile, "skills", None),
            "availability": getattr(profile, "availability", None),
            "looking_for_skills": getattr(profile, "looking_for_skills", None),
            "looking_for_type": getattr(profile, "looking_for_type", None),
            "cofounder_commitment": getattr(profile, "cofounder_commitment", None),
            "commitment_level": getattr(profile, "commitment_level", None),
            "risk_tolerance": getattr(profile, "risk_tolerance", None),
            "execution_history": getattr(profile, "execution_history", None),
            "leadership_style": getattr(profile, "leadership_style", None),
        },
    }
