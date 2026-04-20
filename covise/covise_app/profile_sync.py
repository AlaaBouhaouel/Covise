from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from .models import OnboardingResponse, Profile, User, WaitlistEntry


PROFILE_ONBOARDING_FIELD_IDS = [
    "user_type",
    "industry",
    "stage",
    "target_market",
    "team_size",
    "one_liner",
    "cofounders_needed",
    "looking_for_type",
    "founder_timeline",
    "current_role",
    "years_experience",
    "industries_interested",
    "venture_stage_preference",
    "founder_type_preference",
    "specialist_timeline",
    "investor_type",
    "investment_geography",
    "ticket_size",
    "investment_stage",
    "investment_industries",
    "investor_value_add",
    "investor_looking_for",
    "investor_timeline",
    "home_country",
    "target_gcc_market",
    "foreign_industry",
    "foreign_stage",
    "foreign_one_liner",
    "local_partner_need",
    "foreign_timeline",
    "program_type",
    "program_location",
    "program_stage_focus",
    "program_industries",
    "cohort_size",
    "program_offering",
    "incubator_looking_for",
    "incubator_timeline",
    "skills",
    "availability",
    "capital_contribution",
    "looking_for_skills",
    "cofounder_commitment",
    "compensation",
    "cofounder_location_pref",
    "monthly_revenue",
    "funding_status",
    "customer_count",
    "commitment_level",
    "risk_tolerance",
    "execution_history",
    "leadership_style",
    "how_heard",
    "referral_code",
]

url_validator = URLValidator(schemes=["http", "https"])


def _clean_text(value):
    return str(value or "").strip()


def _flatten_text_values(value):
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, dict):
        items = []
        for item in value.values():
            items.extend(_flatten_text_values(item))
        return items
    if isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            items.extend(_flatten_text_values(item))
        return items
    text = str(value).strip()
    return [text] if text else []


def _normalize_profile_links(value, *, max_items=5):
    links = []
    for raw in _flatten_text_values(value):
        candidate = raw
        if not candidate.startswith(("http://", "https://")):
            candidate = f"https://{candidate}"
        try:
            url_validator(candidate)
        except ValidationError:
            continue
        if candidate not in links:
            links.append(candidate)
        if len(links) >= max_items:
            break
    return links


def _profile_links_from_answers(answers):
    links = []
    for candidate in _normalize_profile_links(answers.get("profile_links", [])):
        if candidate not in links:
            links.append(candidate)
    return links


def _pick_profile_links(links, *, existing_linkedin="", existing_github="", existing_proof=""):
    linkedin = _clean_text(existing_linkedin)
    github = _clean_text(existing_github)
    proof = _clean_text(existing_proof)

    for link in links:
        lowered = link.lower()
        if not linkedin and "linkedin.com" in lowered:
            linkedin = link
            continue
        if not github and "github.com" in lowered:
            github = link
            continue
        if not proof:
            proof = link

    return linkedin, github, proof


def _waitlist_snapshot(waitlist_entry):
    if not waitlist_entry:
        return {}

    return {
        "full_name": waitlist_entry.full_name,
        "phone_number": waitlist_entry.phone_number,
        "email": waitlist_entry.email,
        "country": waitlist_entry.country,
        "non_gcc_business": waitlist_entry.non_gcc_business,
        "custom_country": waitlist_entry.custom_country,
        "description": waitlist_entry.description,
        "custom_description": waitlist_entry.custom_description,
        "venture_summary": waitlist_entry.venture_summary,
        "linkedin": waitlist_entry.linkedin,
        "cv_s3_key": waitlist_entry.cv_s3_key,
        "my_referral_code": waitlist_entry.my_referral_code,
        "referred_by_id": waitlist_entry.referred_by_id,
        "status": waitlist_entry.status,
    }


def build_profile_defaults(
    *,
    user,
    existing_profile=None,
    waitlist_entry=None,
    onboarding_response=None,
    flow_name="",
    answers=None,
):
    answers = answers or {}
    source_waitlist = waitlist_entry or getattr(onboarding_response, "waitlist_entry", None)
    normalized_profile_links = _profile_links_from_answers(answers)
    waitlist_linkedin = _clean_text(getattr(source_waitlist, "linkedin", ""))
    existing_linkedin = _clean_text(getattr(existing_profile, "linkedin", "")) if existing_profile else ""
    existing_github = _clean_text(getattr(existing_profile, "github", "")) if existing_profile else ""
    existing_proof = _clean_text(getattr(existing_profile, "proof_of_work_url", "")) if existing_profile else ""
    resolved_linkedin, resolved_github, resolved_proof = _pick_profile_links(
        normalized_profile_links,
        existing_linkedin=existing_linkedin or waitlist_linkedin,
        existing_github=existing_github,
        existing_proof=existing_proof,
    )

    resolved_location = (
        _clean_text(answers.get("location"))
        or (_clean_text(getattr(existing_profile, "country", "")) if existing_profile else "")
        or _clean_text(getattr(source_waitlist, "custom_country", ""))
        or _clean_text(getattr(source_waitlist, "country", ""))
    )
    resolved_headline = (
        _clean_text(answers.get("headline"))
        or (_clean_text(getattr(existing_profile, "bio", "")) if existing_profile else "")
    )

    profile_defaults = {
        "full_name": _clean_text(user.full_name) or _clean_text(getattr(source_waitlist, "full_name", "")),
        "source_waitlist_entry": source_waitlist,
        "source_onboarding_response": onboarding_response,
        "waitlist_snapshot": _waitlist_snapshot(source_waitlist),
        "onboarding_answers": answers,
        "plan": _clean_text(answers.get("plan")) or getattr(existing_profile, "plan", "") or "Free",
        "country": resolved_location,
        "bio": resolved_headline,
        "linkedin": resolved_linkedin,
        "github": resolved_github,
        "proof_of_work_url": resolved_proof,
    }

    if source_waitlist:
        profile_defaults.update(
            {
                "phone_number": source_waitlist.phone_number,
                "non_gcc_business": source_waitlist.non_gcc_business,
                "custom_country": source_waitlist.custom_country,
                "cv_s3_key": source_waitlist.cv_s3_key,
                "my_referral_code": source_waitlist.my_referral_code,
            }
        )

    if source_waitlist and source_waitlist.referred_by_id:
        referrer_user = User.objects.filter(email=source_waitlist.referred_by.email).first()
        profile_defaults["referred_by"] = getattr(referrer_user, "profile", None) if referrer_user else None

    if onboarding_response:
        profile_defaults["flow_name"] = _clean_text(flow_name) or onboarding_response.flow_name
        profile_defaults.update(
            {
                field_id: answers.get(field_id, getattr(onboarding_response, field_id))
                for field_id in PROFILE_ONBOARDING_FIELD_IDS
            }
        )

    return profile_defaults


def sync_profile_for_user(user, waitlist_entry=None, onboarding_response=None, flow_name="", answers=None):
    if not user:
        return None

    existing_profile = getattr(user, "profile", None)

    if waitlist_entry is None:
        waitlist_entry = WaitlistEntry.objects.filter(email=user.email).first()

    if onboarding_response is None:
        if waitlist_entry:
            onboarding_response = getattr(waitlist_entry, "onboarding_response", None)
        if onboarding_response is None:
            onboarding_response = OnboardingResponse.objects.filter(email=user.email).order_by("-updated_at").first()

    if answers is None and onboarding_response is not None:
        answers = onboarding_response.answers

    profile_defaults = build_profile_defaults(
        user=user,
        existing_profile=existing_profile,
        waitlist_entry=waitlist_entry,
        onboarding_response=onboarding_response,
        flow_name=flow_name,
        answers=answers,
    )

    profile, _ = Profile.objects.update_or_create(user=user, defaults=profile_defaults)
    return profile
