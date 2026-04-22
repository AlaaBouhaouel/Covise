import io
import json
import logging
import random
import re
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.http import Http404, HttpResponsePermanentRedirect, JsonResponse
from django.db import models, IntegrityError, OperationalError, close_old_connections, transaction
from django.db.models import Case, Count, IntegerField, Q, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.utils.html import escape
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timesince import timesince
from .models import OnboardingResponse, Profile, User, UserPreference, WaitlistEmailVerification, WaitlistEntry, Post, PostImage, PostMention, PostReaction, Comment, CommentReaction, SavedPost, BlockedUser, Notification, ConversationUserState, Experiences, Active_projects, Project, Conversation, Message, MessageReceipt, MessageReaction, ConversationRequest, AccountDeletionRequest, AccountPauseRequest, DataDeletionRequest, DataExportRequest, SignInEvent, TwoFactorChallenge
from covise_app.utils import delete_s3_object, generate_referral_code, upload_cv_to_s3
from covise_app.user_context import build_profile_card_context, build_profile_context, build_saved_post_items, build_settings_context, build_ui_user_context, get_onboarding_skill_config
from covise_app.profile_sync import PROFILE_ONBOARDING_FIELD_IDS, sync_profile_for_user
from covise_app.display_utils import public_display_name
from covise_app.messaging import (
    MessagingError,
    RealtimeDeliveryError,
    broadcast_chat_message,
    broadcast_conversation_deleted,
    broadcast_message_receipts_seen,
    deliver_media_message,
    deliver_text_message,
    mark_conversation_seen,
    message_receipt_state_for_viewer,
    send_messaging_failure_alert,
)
from covise_app.notifications import create_notification, dispatch_notification, enabled_in_app_notification_types, in_app_notification_enabled, serialize_notification
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import identify_hasher
from django.contrib.sessions.models import Session

try:
    import resend
except ImportError:
    resend = None


logger = logging.getLogger(__name__)
RESEND_API_KEY = getattr(settings, "RESEND_API", "")
WAITLIST_FAILURE_ALERT_EMAIL = getattr(settings, "WAITLIST_FAILURE_ALERT_EMAIL", "ellabouhawel@gmail.com")
REPORT_ALERT_EMAIL = getattr(settings, "REPORT_ALERT_EMAIL", WAITLIST_FAILURE_ALERT_EMAIL)
url_validator = URLValidator(schemes=["http", "https"])
PENDING_2FA_CHALLENGE_SESSION_KEY = "pending_2fa_challenge_id"
PENDING_2FA_USER_SESSION_KEY = "pending_2fa_user_id"
PENDING_2FA_NEXT_SESSION_KEY = "pending_2fa_next"
PROFILE_PHOTO_MAX_SIZE_BYTES = int(getattr(settings, "PROFILE_PHOTO_MAX_SIZE_BYTES", 5 * 1024 * 1024))
PROFILE_PHOTO_MAX_SIZE_MB = max(1, PROFILE_PHOTO_MAX_SIZE_BYTES // (1024 * 1024))
HOME_PINNED_POST_EMAIL = "founders@covise.net"
FOUNDERS_TEAM_WELCOME_MESSAGE = (
    "Welcome to CoVise\n\n"
    "this is your direct chat with the CoVise team.\n\n"
    "If you have any questions, run into any issues, or need help with anything, feel free to message here anytime."
)


def _normalize_email(value):
    return str(value or "").strip().lower()


def _is_founders_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and _normalize_email(getattr(user, "email", "")) == HOME_PINNED_POST_EMAIL)


def _normalize_email_list(value):
    if not value:
        return ()

    if isinstance(value, str):
        candidates = re.split(r"[,;\s]+", value)
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        candidates = [value]

    normalized = []
    for candidate in candidates:
        email = _normalize_email(candidate)
        if not email:
            continue
        try:
            validate_email(email)
        except ValidationError:
            logger.warning("Ignoring invalid email recipient configured for post alerts: %s", candidate)
            continue
        if email not in normalized:
            normalized.append(email)
    return tuple(normalized)


def _post_alert_recipients():
    emails = (
        User.objects.filter(is_active=True)
        .exclude(email__icontains="small365")
        .values_list("email", flat=True)
    )
    return tuple(_normalize_email(e) for e in emails if _normalize_email(e))


def _new_account_alert_recipients():
    return _normalize_email_list(
        getattr(
            settings,
            "NEW_ACCOUNT_ALERT_EMAILS",
            ("ellabouhawel@gmail.com", "small345az@gmail.com"),
        )
    )


def _site_url():
    return str(getattr(settings, "SITE_URL", "https://covise.net") or "https://covise.net").rstrip("/")


def _absolute_site_url(value):
    if not value:
        return f"{_site_url()}/"

    value = str(value)
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if not value.startswith("/"):
        value = f"/{value}"
    return f"{_site_url()}{value}"


def _safe_media_url(field_file):
    if not field_file:
        return ""
    try:
        url = field_file.url
    except Exception:
        return ""
    return url


def _display_name(user):
    if not user:
        return ""
    return public_display_name(user)


def _public_profile_url(user):
    if not user:
        return ""
    return _absolute_site_url(reverse("Public Profile", args=[user.id]))


def _country_display_label(value):
    text = str(value or "").strip()
    if not text:
        return ""

    country_map = {
        "saudi_arabia": "Saudi Arabia",
        "united_arab_emirates": "United Arab Emirates",
        "uae": "UAE",
        "gcc_wide": "GCC-wide",
        "mena_wide": "MENA-wide",
    }
    normalized = text.casefold()
    if normalized in country_map:
        return country_map[normalized]

    if "_" in text:
        return " ".join(part.capitalize() for part in text.split("_") if part)

    if text == text.lower():
        return " ".join(part.capitalize() for part in text.split() if part)

    return text


def _serialize_model_fields(instance, *, exclude=None):
    if not instance:
        return {}
    excluded = set(exclude or ())
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in excluded:
            continue
        value = field.value_from_object(instance)
        if isinstance(field, models.FileField):
            data[field.name] = getattr(value, "name", "") if value else ""
            data[f"{field.name}_url"] = _safe_media_url(value)
        elif isinstance(value, uuid.UUID):
            data[field.name] = str(value)
        else:
            data[field.name] = value
    return data


def _build_data_export_payload(user):
    profile = getattr(user, "profile", None)
    preferences = getattr(user, "preferences", None)

    posts = list(
        Post.objects.filter(user=user)
        .prefetch_related("gallery_images", "mentions__mentioned_user")
        .order_by("-created_at")
    )
    comments = list(
        Comment.objects.filter(user=user)
        .select_related("post", "post__user", "parent")
        .order_by("-created_at")
    )
    saved_posts = list(
        SavedPost.objects.filter(user=user)
        .select_related("post__user")
        .order_by("-created_at")
    )
    blocked_users = list(
        BlockedUser.objects.filter(blocker=user)
        .select_related("blocked")
        .order_by("-created_at")
    )
    notifications = list(
        Notification.objects.filter(recipient=user)
        .select_related("actor")
        .order_by("-created_at")
    )
    conversation_requests = list(
        ConversationRequest.objects.filter(Q(requester=user) | Q(recipient=user))
        .select_related("requester", "recipient", "conversation")
        .order_by("-created_at")
    )
    conversations = list(
        Conversation.objects.filter(participants=user)
        .prefetch_related("participants__profile", "messages__sender", "messages__receipts", "messages__reactions")
        .order_by("-updated_at")
        .distinct()
    )
    experiences = list(Experiences.objects.filter(user=user).order_by("-id"))
    active_projects = list(Active_projects.objects.filter(user=user).order_by("-id"))
    projects = list(Project.objects.filter(user=user).order_by("-updated_at"))

    payload = {
        "generated_at": timezone.now(),
        "site_url": _site_url(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "date_joined": user.date_joined,
            "sign_in_count": user.sign_in_count,
            "has_seen_interactive_demo": user.has_seen_interactive_demo,
            "public_profile_url": _public_profile_url(user),
        },
        "profile": _serialize_model_fields(profile, exclude={"id", "user"}),
        "preferences": _serialize_model_fields(preferences, exclude={"id", "user"}),
        "experiences": [
            {
                "id": item.id,
                "title": item.title,
                "date": item.date,
                "description": item.desc,
            }
            for item in experiences
        ],
        "active_projects": [
            {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "description": item.desc,
            }
            for item in active_projects
        ],
        "projects": [
            {
                **_serialize_model_fields(item, exclude={"user"}),
                "url": _absolute_site_url(reverse("Project Detail", args=[item.slug])),
            }
            for item in projects
        ],
        "posts": [
            {
                "id": item.id,
                "title": item.title,
                "post_type": item.post_type,
                "theme_color": item.theme_color,
                "content": item.content,
                "likes_number": item.likes_number,
                "comments_number": item.comments_number,
                "created_at": item.created_at,
                "url": _absolute_site_url(reverse("Post Detail", args=[item.id])),
                "image_url": _safe_media_url(item.image),
                "gallery_images": [
                    {
                        "id": image.id,
                        "sort_order": image.sort_order,
                        "image_url": _safe_media_url(image.image),
                    }
                    for image in item.gallery_images.all()
                ],
                "mentions": [
                    {
                        "user_id": str(mention.mentioned_user_id),
                        "display_name": _display_name(mention.mentioned_user),
                        "handle_text": mention.handle_text,
                        "profile_url": _public_profile_url(mention.mentioned_user),
                    }
                    for mention in item.mentions.all()
                ],
            }
            for item in posts
        ],
        "comments": [
            {
                "id": item.id,
                "post_id": item.post_id,
                "post_title": item.post.title if item.post_id else "",
                "post_url": _absolute_site_url(reverse("Post Detail", args=[item.post_id])) if item.post_id else "",
                "post_owner_profile_url": _public_profile_url(item.post.user) if item.post_id else "",
                "parent_comment_id": item.parent_id,
                "content": item.content,
                "up": item.up,
                "down": item.down,
                "is_pinned": item.is_pinned,
                "edited_at": item.edited_at,
                "created_at": item.created_at,
            }
            for item in comments
        ],
        "saved_posts": [
            {
                "saved_at": item.created_at,
                "post_id": item.post_id,
                "post_title": item.post.title,
                "post_type": item.post.post_type,
                "post_url": _absolute_site_url(reverse("Post Detail", args=[item.post_id])),
                "post_owner_id": str(item.post.user_id),
                "post_owner_name": _display_name(item.post.user),
                "post_owner_profile_url": _public_profile_url(item.post.user),
            }
            for item in saved_posts
        ],
        "blocked_users": [
            {
                "blocked_user_id": str(item.blocked_id),
                "blocked_user_name": _display_name(item.blocked),
                "blocked_user_email": item.blocked.email if item.blocked_id else "",
                "blocked_user_profile_url": _public_profile_url(item.blocked),
                "blocked_at": item.created_at,
            }
            for item in blocked_users
        ],
        "notifications": [
            {
                "id": item.id,
                "notification_type": item.notification_type,
                "title": item.title,
                "body": item.body,
                "target_url": _absolute_site_url(item.target_url) if item.target_url else "",
                "is_read": item.is_read,
                "emailed_at": item.emailed_at,
                "created_at": item.created_at,
                "actor_id": str(item.actor_id) if item.actor_id else "",
                "actor_name": _display_name(item.actor) if item.actor_id else "",
                "actor_profile_url": _public_profile_url(item.actor) if item.actor_id else "",
            }
            for item in notifications
        ],
        "conversation_requests": [
            {
                "id": str(item.id),
                "status": item.status,
                "created_at": item.created_at,
                "responded_at": item.responded_at,
                "conversation_id": str(item.conversation_id) if item.conversation_id else "",
                "requester": {
                    "id": str(item.requester_id),
                    "name": _display_name(item.requester),
                    "profile_url": _public_profile_url(item.requester),
                },
                "recipient": {
                    "id": str(item.recipient_id),
                    "name": _display_name(item.recipient),
                    "profile_url": _public_profile_url(item.recipient),
                },
            }
            for item in conversation_requests
        ],
        "conversations": [
            {
                "id": str(conversation.id),
                "conversation_type": conversation.conversation_type,
                "group_name": conversation.group_name,
                "recording_mode": conversation.recording_mode,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
                "last_message_at": conversation.last_message_at,
                "participants": [
                    {
                        "id": str(participant.id),
                        "name": _display_name(participant),
                        "profile_url": _public_profile_url(participant),
                    }
                    for participant in conversation.participants.all()
                ],
                "messages": [
                    {
                        "id": str(message.id),
                        "sender_id": str(message.sender_id),
                        "sender_name": _display_name(message.sender),
                        "sender_profile_url": _public_profile_url(message.sender),
                        "message_type": message.message_type,
                        "body": message.body,
                        "attachment_name": message.attachment_name,
                        "attachment_content_type": message.attachment_content_type,
                        "attachment_size": message.attachment_size,
                        "attachment_url": _safe_media_url(message.attachment_file),
                        "created_at": message.created_at,
                        "receipts": [
                            {
                                "user_id": str(receipt.user_id),
                                "status": receipt.status,
                                "delivered_at": receipt.delivered_at,
                                "seen_at": receipt.seen_at,
                            }
                            for receipt in message.receipts.all()
                        ],
                        "reactions": [
                            {
                                "user_id": str(reaction.user_id),
                                "reaction": reaction.reaction,
                                "created_at": reaction.created_at,
                            }
                            for reaction in message.reactions.all()
                        ],
                    }
                    for message in conversation.messages.all()
                ],
            }
            for conversation in conversations
        ],
    }
    return payload


def _build_data_export_archive(user):
    export_payload = _build_data_export_payload(user)
    export_json = json.dumps(export_payload, cls=DjangoJSONEncoder, indent=2)
    now = timezone.now()
    json_filename = f"covise-data-export-{now.strftime('%Y%m%d-%H%M%S')}.json"
    archive_filename = f"covise-data-export-{now.strftime('%Y%m%d-%H%M%S')}.zip"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(json_filename, export_json)
    return archive_filename, buffer.getvalue()


def _send_data_export_email(user):
    filename, archive_bytes = _build_data_export_archive(user)
    subject = "Your CoVise data export"
    body = (
        "Your CoVise data export is attached as a ZIP file.\n\n"
        f"Account email: {user.email}\n"
        f"Public profile: {_public_profile_url(user)}\n"
        "The attachment includes your account, profile, preferences, posts, comments, saved posts, "
        "notifications, conversation history, related profile links, and other user-owned records.\n"
    )
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "support@covise.net"),
        to=[user.email],
    )
    email.attach(filename, archive_bytes, "application/zip")
    email.send(fail_silently=False)


def _send_data_deletion_request_emails(user):
    requested_at = timezone.now()
    profile_url = _public_profile_url(user)
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "support@covise.net")
    support_recipient = _normalize_email(REPORT_ALERT_EMAIL)

    user_body = (
        "We processed your CoVise data deletion request.\n\n"
        f"Processed at: {requested_at.isoformat()}\n"
        f"Account email: {user.email}\n"
        f"Public profile: {profile_url}\n\n"
        "Your member login remains active, but your user-owned CoVise data was cleared. If this request was not made by you, please reply to this email immediately.\n"
    )
    EmailMessage(
        subject="We processed your CoVise data deletion request",
        body=user_body,
        from_email=from_email,
        to=[user.email],
    ).send(fail_silently=False)

    if support_recipient:
        support_body = (
            "A CoVise user data wipe was completed.\n\n"
            f"Processed at: {requested_at.isoformat()}\n"
            f"User ID: {user.id}\n"
            f"User email: {user.email}\n"
            f"User name: {_display_name(user)}\n"
            f"Public profile: {profile_url}\n"
        )
        EmailMessage(
            subject=f"Data wipe completed: {user.email}",
            body=support_body,
            from_email=from_email,
            to=[support_recipient],
        ).send(fail_silently=False)


def _send_account_deletion_request_emails(user):
    requested_at = timezone.now()
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "support@covise.net")
    support_recipient = _normalize_email(REPORT_ALERT_EMAIL)

    user_body = (
        "We received and processed your CoVise account deletion request.\n\n"
        f"Processed at: {requested_at.isoformat()}\n"
        f"Account email: {user.email}\n\n"
        "If this request was not made by you, please contact support immediately.\n"
    )
    EmailMessage(
        subject="Your CoVise account deletion was processed",
        body=user_body,
        from_email=from_email,
        to=[user.email],
    ).send(fail_silently=False)

    if support_recipient:
        support_body = (
            "A CoVise user account was deleted.\n\n"
            f"Processed at: {requested_at.isoformat()}\n"
            f"User ID: {user.id}\n"
            f"User email: {user.email}\n"
            f"User name: {_display_name(user)}\n"
        )
        EmailMessage(
            subject=f"Account deleted: {user.email}",
            body=support_body,
            from_email=from_email,
            to=[support_recipient],
        ).send(fail_silently=False)


def _generate_verification_code():
    return f"{random.randint(0, 999999):06d}"


def _blocked_user_ids(user):
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    return set(
        BlockedUser.objects.filter(blocker=user).values_list("blocked_id", flat=True)
    )


def _has_user_blocked(blocker, blocked):
    if not blocker or not blocked:
        return False
    return BlockedUser.objects.filter(blocker=blocker, blocked=blocked).exists()


def _is_blocked_pair(user_a, user_b):
    if not user_a or not user_b or user_a == user_b:
        return False
    return (
        BlockedUser.objects.filter(blocker=user_a, blocked=user_b).exists()
        or BlockedUser.objects.filter(blocker=user_b, blocked=user_a).exists()
    )


def _blocked_user_items(user):
    relationships = (
        BlockedUser.objects.filter(blocker=user)
        .select_related("blocked", "blocked__profile")
        .order_by("-created_at")
    )
    items = []
    for relationship in relationships:
        blocked_user = relationship.blocked
        items.append(
            {
                "id": blocked_user.id,
                "display_name": _display_name(blocked_user),
                "avatar_initials": blocked_user.avatar_initials,
                "avatar_url": _user_avatar_url(blocked_user),
            }
        )
    return items


EXTENDED_ONBOARDING_SIGNAL_KEYS = (
    "current_goal",
    "discovery_people",
    "discovery_region",
    "industry",
    "stage",
    "target_market",
    "team_size",
    "cofounders_needed",
    "founder_timeline",
    "current_role",
    "years_experience",
    "industries_interested",
    "specialist_timeline",
    "investor_type",
    "investment_geography",
    "investment_stage",
    "investment_industries",
    "investor_looking_for",
    "home_country",
    "target_gcc_market",
    "foreign_industry",
    "foreign_stage",
    "local_partner_need",
    "program_type",
    "program_location",
    "program_stage_focus",
    "program_industries",
    "incubator_looking_for",
    "skills",
    "availability",
    "how_heard",
    "referral_code",
)


def _has_profile_completion(profile):
    if not profile:
        return False

    onboarding_answers = _clean_onboarding_answers(getattr(profile, "onboarding_answers", {}))
    one_liner_value = onboarding_answers.get("one_liner", getattr(profile, "one_liner", None))
    looking_for_value = onboarding_answers.get("looking_for_type", getattr(profile, "looking_for_type", None))

    has_building = bool(_flatten_text_values(one_liner_value))
    has_looking_for = bool(_flatten_text_values(looking_for_value))
    legacy_onboarding = bool(getattr(profile, "source_onboarding_response_id", None) or str(getattr(profile, "flow_name", "") or "").strip())

    return (has_building and has_looking_for) or legacy_onboarding


def _has_completed_extended_onboarding(profile):
    if not profile:
        return False

    onboarding_answers = _clean_onboarding_answers(getattr(profile, "onboarding_answers", {}))
    if onboarding_answers.get("extended_onboarding_completed"):
        return True

    if any(key in onboarding_answers for key in EXTENDED_ONBOARDING_SIGNAL_KEYS):
        return True

    return False


def _is_profile_onboarded(profile):
    return _has_profile_completion(profile)


def _post_auth_redirect_url(user, next_url=""):
    profile = getattr(user, "profile", None)
    sanitized_next = str(next_url or "").strip()

    if not _is_profile_onboarded(profile):
        onboarding_url = reverse("Onboarding")
        if sanitized_next:
            return f"{onboarding_url}?next={sanitized_next}"
        return onboarding_url

    if not getattr(profile, "has_accepted_platform_agreement", False):
        agreement_url = reverse("Agreement")
        target = sanitized_next or reverse("Home")
        return f"{agreement_url}?next={target}"

    return sanitized_next or reverse("Home")


def _requires_intro_post(profile):
    return bool(profile and getattr(profile, "requires_intro_post", False))


def _clean_onboarding_answers(answers):
    if not isinstance(answers, dict):
        return {}
    cleaned = {}
    for key, value in answers.items():
        if value in (None, "", [], {}, ()):
            continue
        cleaned[key] = value
    return cleaned


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
    invalid_links = []
    for raw in _flatten_text_values(value):
        candidate = raw
        if not candidate.startswith(("http://", "https://")):
            candidate = f"https://{candidate}"
        try:
            url_validator(candidate)
        except ValidationError:
            invalid_links.append(raw)
            continue
        if candidate not in links:
            links.append(candidate)
        if len(links) >= max_items:
            break
    return links, invalid_links


def _waitlist_description_to_user_type(description_value, *, non_gcc_business=False):
    normalized = str(description_value or "").strip().lower()
    if normalized == "founder_idea":
        return "foreign_founder" if non_gcc_business else "founder"
    if normalized == "developer":
        return "developer"
    if normalized == "operator":
        return "operator"
    if normalized == "other":
        return "other"
    return ""


def _waitlist_to_onboarding_initial_answers(waitlist_source):
    if not waitlist_source:
        return {}

    source = waitlist_source
    if not isinstance(source, dict):
        source = {
            "email": getattr(waitlist_source, "email", ""),
            "country": getattr(waitlist_source, "country", ""),
            "custom_country": getattr(waitlist_source, "custom_country", ""),
            "non_gcc_business": getattr(waitlist_source, "non_gcc_business", False),
            "description": getattr(waitlist_source, "description", ""),
            "custom_description": getattr(waitlist_source, "custom_description", ""),
            "venture_summary": getattr(waitlist_source, "venture_summary", ""),
            "linkedin": getattr(waitlist_source, "linkedin", ""),
        }

    non_gcc_business = bool(source.get("non_gcc_business"))
    mapped_user_type = _waitlist_description_to_user_type(
        source.get("description"),
        non_gcc_business=non_gcc_business,
    )

    initial_answers = {}
    if source.get("email"):
        initial_answers["email"] = source.get("email")
    if mapped_user_type:
        initial_answers["user_type"] = mapped_user_type
    if source.get("venture_summary"):
        initial_answers["one_liner"] = source.get("venture_summary")
    if non_gcc_business and source.get("custom_country"):
        initial_answers["home_country"] = source.get("custom_country")
        initial_answers.setdefault("looking_for_type", "Local GCC partner")

    return _clean_onboarding_answers(initial_answers)


def _onboarding_show_if_matches(show_if, answers):
    if not show_if:
        return True
    if isinstance(show_if, dict):
        any_of = show_if.get("any_of")
        if isinstance(any_of, list):
            return any(_onboarding_show_if_matches(rule, answers) for rule in any_of)
        field = str(show_if.get("field", "")).strip()
        expected = show_if.get("equals")
        if field:
            return answers.get(field) == expected
    return True


def _first_extended_onboarding_step_id(flow, answers):
    steps = (flow or {}).get("steps", [])
    for step in steps:
        step_id = str((step or {}).get("step_id", "")).strip()
        if not step_id or step_id == "S1_PROFILE_COMPLETION":
            continue
        if _onboarding_show_if_matches((step or {}).get("show_if"), answers):
            return step_id
    return "S1_PROFILE_COMPLETION"


def _send_onboarding_failure_alert(user_email, reason, details):
    alert_email = WAITLIST_FAILURE_ALERT_EMAIL
    if resend is None or not RESEND_API_KEY or not alert_email:
        logger.warning(
            "Skipped onboarding failure alert for %s because email alerts are not configured.",
            user_email,
        )
        return

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [alert_email],
        "subject": f"ERROR: onboarding submission failed for {user_email or 'unknown user'}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">Onboarding submission failed</h1>'
            f"<p style=\"margin: 0 0 10px;\"><strong>User email:</strong> {user_email or 'unknown'}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Date:</strong> {timestamp}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Reason:</strong> {reason}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Details:</strong> {json.dumps(details, default=str)}</p>"
            "</div>"
        ),
    }

    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception("Failed to send onboarding failure alert email for %s", user_email)


def _integrity_error_text(exc):
    parts = [str(exc)]
    if getattr(exc, "__cause__", None):
        parts.append(str(exc.__cause__))
    if getattr(exc, "__context__", None):
        parts.append(str(exc.__context__))
    return " ".join(part for part in parts if part).lower()


def _send_waitlist_failure_alert(user_email, reason, details):
    if resend is None or not RESEND_API_KEY or not WAITLIST_FAILURE_ALERT_EMAIL:
        logger.warning(
            "Skipped waitlist failure alert for %s because email alerts are not configured.",
            user_email,
        )
        return

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [WAITLIST_FAILURE_ALERT_EMAIL],
        "subject": f"ERROR: waitlist submission failed after email verification for {user_email}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">Error after email verification</h1>'
            f"<p style=\"margin: 0 0 10px;\"><strong>User email:</strong> {user_email}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Date:</strong> {timestamp}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Reason:</strong> {reason}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Details:</strong> {json.dumps(details, default=str)}</p>"
            "</div>"
        ),
    }

    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception("Failed to send waitlist failure alert email for %s", user_email)


def _log_waitlist_submission_failure(email, reason, *, verified_already, cv_uploaded, cv_s3_key="", extra=None):
    details = {
        "email": email,
        "reason": reason,
        "verified_already": verified_already,
        "cv_uploaded": cv_uploaded,
    }
    if cv_s3_key:
        details["cv_s3_key"] = cv_s3_key
    if extra:
        details.update(extra)
    logger.warning("Waitlist submission incomplete: %s", details)
    if reason in {"referral_code_collision", "unexpected_integrity_error", "operational_error"}:
        _send_waitlist_failure_alert(email, reason, details)


def _send_waitlist_abandonment_alert(user_email):
    if resend is None or not RESEND_API_KEY or not WAITLIST_FAILURE_ALERT_EMAIL:
        logger.warning(
            "Skipped waitlist abandonment alert for %s because email alerts are not configured.",
            user_email,
        )
        return

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [WAITLIST_FAILURE_ALERT_EMAIL],
        "subject": f"WITHDRAWN: user verified email but left before full waitlist submission for {user_email}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">User withdrew after email verification</h1>'
            f"<p style=\"margin: 0 0 10px;\"><strong>User email:</strong> {user_email}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Date:</strong> {timestamp}</p>"
            '<p style="margin: 0;">The user completed email verification but left the waitlist flow before submitting the full form.</p>'
            "</div>"
        ),
    }

    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception("Failed to send waitlist abandonment alert email for %s", user_email)


def _send_waitlist_verification_email(email_verification):
    if resend is None:
        raise RuntimeError("resend is not installed.")
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API is not configured.")

    resend.api_key = RESEND_API_KEY
    payload = {
        "from": "CoVise <founders@covise.net>",
        "to": [email_verification.email],
        "subject": "Verify your email for the CoVise waitlist",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 24px; color: #e2e8f0; background: #0f1117; border-radius: 12px;">'
            '<div style="text-align: center; margin-bottom: 32px;">'
            '<img src="https://logo-im-g.s3.eu-central-1.amazonaws.com/covise_logo.png" alt="CoVise" style="height: 40px; margin-bottom: 8px;">'
            '<h1 style="font-size: 28px; font-weight: 700; color: #ffffff; margin: 0;">CoVise</h1>'
            '<p style="font-size: 13px; color: #64748b; margin: 4px 0 0; letter-spacing: 0.05em;">THE FOUNDERS COMMUNITY</p>'
            "</div>"
            '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 0 0 28px;">'
            '<p style="font-size: 15px; color: #cbd5e1; margin: 0 0 8px;">Hey, this is the CoVise Team,</p>'
            '<p style="font-size: 15px; color: #cbd5e1; margin: 0 0 20px;">We are excited to have you on board.</p>'
            '<p style="font-size: 15px; color: #94a3b8; margin: 0 0 8px;">You are one step away from reserving your spot in the CoVise community.</p>'
            '<p style="font-size: 15px; color: #94a3b8; margin: 0 0 24px;">Enter this 6-digit verification code in the waitlist form to complete your application:</p>'
            '<div style="text-align: center; background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.15); border-radius: 10px; padding: 24px; margin: 0 0 28px;">'
            '<p style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 10px;">Verification Code</p>'
            f'<p style="font-size: 32px; font-weight: 700; letter-spacing: 0.3em; color: #ffffff; margin: 0;">{email_verification.verification_code}</p>'
            "</div>"
            '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 0 0 20px;">'
            '<p style="font-size: 13px; color: #cbd5e1; margin: 0;">- The CoVise Team</p>'
            '<p style="font-size: 12px; color: #cbd5e1; margin: 12px 0 0;">If you did not request this, you can safely ignore this email.</p>'
            "</div>"
        ),
    }
    resend.Emails.send(payload)


def _send_platform_welcome_email(user):
    display_name = _display_name(user).split("@")[0] if "@" in _display_name(user) else _display_name(user)
    first_name = (display_name or "Founder").split()[0]
    home_url = _absolute_site_url(reverse("Home"))
    profile_url = _public_profile_url(user)
    subject = "Welcome to CoVise"

    if resend is not None and RESEND_API_KEY:
        resend.api_key = RESEND_API_KEY
        payload = {
            "from": "CoVise <founders@covise.net>",
            "to": [user.email],
            "subject": subject,
            "html": (
                '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 24px; color: #e2e8f0; background: #0f1117; border-radius: 12px;">'
                '<div style="text-align: center; margin-bottom: 32px;">'
                '<img src="https://logo-im-g.s3.eu-central-1.amazonaws.com/covise_logo.png" alt="CoVise" style="height: 40px; margin-bottom: 8px;">'
                '<h1 style="font-size: 28px; font-weight: 700; color: #ffffff; margin: 0;">CoVise</h1>'
                '<p style="font-size: 13px; color: #64748b; margin: 4px 0 0; letter-spacing: 0.05em;">THE FOUNDERS COMMUNITY</p>'
                "</div>"
                '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 0 0 28px;">'
                f'<p style="font-size: 15px; color: #cbd5e1; margin: 0 0 8px;">Hey {escape(first_name)}, this is the CoVise Team,</p>'
                '<p style="font-size: 15px; color: #cbd5e1; margin: 0 0 20px;">Welcome in. Your community access is now active.</p>'
                '<p style="font-size: 15px; color: #94a3b8; margin: 0 0 8px;">You can now explore founders, post updates, send requests, and start building inside CoVise.</p>'
                '<p style="font-size: 15px; color: #94a3b8; margin: 0 0 24px;">We recommend starting by opening your home feed, completing your profile, and making your first post.</p>'
                '<div style="text-align: center; margin: 0 0 28px;">'
                f'<a href="{home_url}" style="display: inline-block; padding: 14px 24px; border-radius: 10px; background: rgba(59,130,246,0.14); border: 1px solid rgba(59,130,246,0.24); color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 700;">Open CoVise</a>'
                "</div>"
                '<div style="background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.15); border-radius: 10px; padding: 18px 20px; margin: 0 0 28px;">'
                f'<p style="font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 8px;">Your Profile</p>'
                f'<p style="font-size: 14px; color: #ffffff; margin: 0;">{escape(profile_url)}</p>'
                "</div>"
                '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 0 0 20px;">'
                '<p style="font-size: 13px; color: #cbd5e1; margin: 0;">- The CoVise Team</p>'
                '<p style="font-size: 12px; color: #cbd5e1; margin: 12px 0 0;">You are receiving this because you agreed to the CoVise community guidelines and your access is now enabled.</p>'
                "</div>"
            ),
        }
        resend.Emails.send(payload)
        return

    body = (
        f"Welcome to CoVise, {first_name}.\n\n"
        "Your community access is now active.\n\n"
        f"Open CoVise: {home_url}\n"
        f"Your profile: {profile_url}\n\n"
        "You can now explore founders, post updates, send requests, and start building inside CoVise.\n"
    )
    EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "support@covise.net"),
        to=[user.email],
    ).send(fail_silently=False)


def _founders_team_user():
    founders_user = User.objects.filter(email__iexact=HOME_PINNED_POST_EMAIL).first()
    if founders_user is None:
        try:
            founders_user = User.objects.create_user(
                email=HOME_PINNED_POST_EMAIL,
                full_name="CoVise Team",
            )
        except IntegrityError:
            founders_user = User.objects.filter(email__iexact=HOME_PINNED_POST_EMAIL).first()

    if founders_user is None:
        return None

    profile_defaults = {
        "full_name": founders_user.full_name or "CoVise Team",
        "has_accepted_platform_agreement": True,
        "platform_agreement_accepted_at": timezone.now(),
    }
    profile, _ = Profile.objects.get_or_create(user=founders_user, defaults=profile_defaults)

    update_fields = []
    if not profile.full_name:
        profile.full_name = founders_user.full_name or "CoVise Team"
        update_fields.append("full_name")
    if not profile.has_accepted_platform_agreement:
        profile.has_accepted_platform_agreement = True
        update_fields.append("has_accepted_platform_agreement")
    if not profile.platform_agreement_accepted_at:
        profile.platform_agreement_accepted_at = timezone.now()
        update_fields.append("platform_agreement_accepted_at")
    if update_fields:
        profile.save(update_fields=update_fields)

    return founders_user


def _send_new_account_alert(user, waitlist_entry=None):
    recipients = _new_account_alert_recipients()
    if resend is None or not RESEND_API_KEY or not recipients:
        logger.warning(
            "Skipped new account alert for %s because email alerts are not configured.",
            getattr(user, "email", ""),
        )
        return False

    resend.api_key = RESEND_API_KEY
    profile = getattr(user, "profile", None)
    onboarding_answers = getattr(profile, "onboarding_answers", {}) or {}
    waitlist_snapshot = getattr(profile, "waitlist_snapshot", {}) or {}

    full_name = (getattr(profile, "full_name", "") or getattr(user, "full_name", "") or "CoVise Member").strip()
    country = (
        str(getattr(profile, "custom_country", "") or "").strip()
        or str(getattr(profile, "country", "") or "").strip()
        or str(getattr(waitlist_entry, "custom_country", "") or "").strip()
        or str(getattr(waitlist_entry, "country", "") or "").strip()
        or str(waitlist_snapshot.get("custom_country") or "").strip()
        or str(waitlist_snapshot.get("country") or "").strip()
        or "Not provided"
    )
    linkedin_url = (
        str(getattr(profile, "linkedin", "") or "").strip()
        or str(getattr(waitlist_entry, "linkedin", "") or "").strip()
        or str(waitlist_snapshot.get("linkedin") or "").strip()
        or "Not provided"
    )
    one_liner = (
        _display_value(getattr(profile, "one_liner", None))
        or _display_value(onboarding_answers.get("one_liner"))
        or str(getattr(waitlist_entry, "venture_summary", "") or "").strip()
        or str(waitlist_snapshot.get("venture_summary") or "").strip()
        or "Not provided"
    )
    user_type = (
        _display_value(getattr(profile, "user_type", None))
        or _display_value(onboarding_answers.get("user_type"))
        or str(getattr(waitlist_entry, "description", "") or "").strip()
        or str(waitlist_snapshot.get("description") or "").strip()
        or "Not provided"
    )
    timestamp = timezone.now().isoformat()
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": list(recipients),
        "subject": f"New CoVise account created: {full_name}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">New account created</h1>'
            f"<p style=\"margin: 0 0 10px;\"><strong>Name:</strong> {escape(full_name)}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Email:</strong> {escape(user.email)}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Date:</strong> {escape(timestamp)}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>User type:</strong> {escape(user_type)}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Country:</strong> {escape(country)}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>LinkedIn:</strong> {escape(linkedin_url)}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>One-liner:</strong> {escape(one_liner)}</p>"
            "</div>"
        ),
    }

    try:
        resend.Emails.send(payload)
        return True
    except Exception:
        logger.exception("Failed to send new account alert email for %s", user.email)
        return False


def _ensure_founders_team_request(user):
    if not user or not getattr(user, "id", None):
        return None

    founders_user = _founders_team_user()
    if founders_user is None or founders_user.id == user.id:
        return None
    if _is_blocked_pair(founders_user, user):
        return None

    pair_filter = Q(requester=founders_user, recipient=user) | Q(requester=user, recipient=founders_user)
    existing_request = (
        ConversationRequest.objects.filter(
            pair_filter,
            status__in=[ConversationRequest.Status.PENDING, ConversationRequest.Status.ACCEPTED],
        )
        .order_by("-created_at")
        .first()
    )
    if existing_request:
        return existing_request

    request_item = ConversationRequest.objects.create(
        requester=founders_user,
        recipient=user,
    )
    dispatch_notification(
        recipient=user,
        actor=founders_user,
        notification_type=Notification.NotificationType.CONVERSATION_REQUEST,
        title=f"{_display_name(founders_user)} wants to start a private chat",
        body="Open Messages to review the request and decide whether to accept it.",
        target_url=reverse("Messages"),
    )
    return request_item


def _send_founders_team_welcome_message(*, request_item, conversation):
    if not request_item or not conversation:
        return None
    if _normalize_email(getattr(request_item.requester, "email", "")) != HOME_PINNED_POST_EMAIL:
        return None

    send_result = deliver_text_message(
        conversation_id=conversation.id,
        sender=request_item.requester,
        message_text=FOUNDERS_TEAM_WELCOME_MESSAGE,
    )
    message = send_result["message"]
    try:
        broadcast_chat_message(
            conversation=conversation,
            message=message,
            sender=request_item.requester,
        )
    except RealtimeDeliveryError as exc:
        send_messaging_failure_alert(
            action="founders_welcome_message",
            reason=exc.code,
            actor=request_item.requester,
            conversation=conversation,
            target_user=request_item.recipient,
            details={"message_id": str(message.id), **exc.details},
        )
    except Exception as exc:
        send_messaging_failure_alert(
            action="founders_welcome_message",
            reason="broadcast_failed",
            actor=request_item.requester,
            conversation=conversation,
            target_user=request_item.recipient,
            details={"message_id": str(message.id), "exception": str(exc)},
        )
    return message


def _as_bool(value):
    return str(value).strip().lower() == "true"


def _split_pipe_list(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split("|") if item.strip()]


def _record_successful_sign_in(user):
    user.sign_in_count = (user.sign_in_count or 0) + 1
    user.save(update_fields=["sign_in_count"])


def _request_ip_address(request):
    forwarded_for = str(request.META.get("HTTP_X_FORWARDED_FOR", "") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    for key in ("HTTP_CF_CONNECTING_IP", "REMOTE_ADDR"):
        value = str(request.META.get(key, "") or "").strip()
        if value:
            return value
    return None


def _request_location_label(request):
    city = str(request.META.get("HTTP_CF_IPCITY", "") or request.META.get("HTTP_X_CITY", "") or "").strip()
    country = str(
        request.META.get("HTTP_CF_IPCOUNTRY", "")
        or request.META.get("HTTP_X_COUNTRY_CODE", "")
        or request.META.get("GEOIP_COUNTRY_CODE", "")
        or ""
    ).strip()
    if city and country:
        return f"{city}, {country}"
    if country:
        return country
    return "Unknown location"


def _device_metadata_from_request(request):
    user_agent = str(request.META.get("HTTP_USER_AGENT", "") or "")
    lowered = user_agent.lower()

    if "edg/" in lowered:
        browser = "Edge"
    elif "opr/" in lowered or "opera" in lowered:
        browser = "Opera"
    elif "chrome/" in lowered and "edg/" not in lowered:
        browser = "Chrome"
    elif "firefox/" in lowered:
        browser = "Firefox"
    elif "safari/" in lowered and "chrome/" not in lowered:
        browser = "Safari"
    else:
        browser = "Browser"

    if "windows" in lowered:
        operating_system = "Windows"
    elif "iphone" in lowered or "ipad" in lowered or "ios" in lowered:
        operating_system = "iOS"
    elif "android" in lowered:
        operating_system = "Android"
    elif "mac os x" in lowered or "macintosh" in lowered:
        operating_system = "macOS"
    elif "linux" in lowered:
        operating_system = "Linux"
    else:
        operating_system = "Unknown OS"

    if "ipad" in lowered or "tablet" in lowered:
        device_type = SignInEvent.DeviceType.TABLET
    elif "iphone" in lowered or "android" in lowered or "mobile" in lowered:
        device_type = SignInEvent.DeviceType.MOBILE
    elif user_agent:
        device_type = SignInEvent.DeviceType.DESKTOP
    else:
        device_type = SignInEvent.DeviceType.OTHER

    return {
        "user_agent": user_agent,
        "browser": browser,
        "operating_system": operating_system,
        "device_type": device_type,
    }


def _device_display_name(event):
    if not event:
        return "Unknown device"
    browser = (event.browser or "").strip() or "Browser"
    operating_system = (event.operating_system or "").strip() or "Unknown OS"
    return f"{browser} - {operating_system}"


def _record_sign_in_event(user, request, *, status, session_key=""):
    metadata = _device_metadata_from_request(request)
    return SignInEvent.objects.create(
        user=user,
        email=user.email,
        status=status,
        session_key=session_key or "",
        ip_address=_request_ip_address(request),
        location=_request_location_label(request),
        user_agent=metadata["user_agent"],
        browser=metadata["browser"],
        operating_system=metadata["operating_system"],
        device_type=metadata["device_type"],
    )


def _send_two_factor_code_email(user, challenge):
    code = getattr(challenge, "code", "")
    if not code:
        raise ValueError("Two-factor challenge code is required.")

    EmailMessage(
        subject="Your CoVise security code",
        body=(
            f"Hi {_display_name(user) or user.email},\n\n"
            f"Your CoVise security code is: {code}\n\n"
            "It expires in 10 minutes. If you did not try to sign in, you can ignore this email."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "support@covise.net"),
        to=[challenge.email or user.email],
    ).send(fail_silently=False)


def _issue_two_factor_challenge(user):
    TwoFactorChallenge.objects.filter(user=user, consumed_at__isnull=True).delete()
    expires_at = timezone.now() + timedelta(minutes=10)
    challenge = TwoFactorChallenge.objects.create(
        user=user,
        email=user.email,
        code=_generate_verification_code(),
        expires_at=expires_at,
    )
    _send_two_factor_code_email(user, challenge)
    return challenge


def _is_valid_two_factor_challenge(challenge):
    if not challenge:
        return False
    if challenge.consumed_at is not None:
        return False
    return challenge.expires_at > timezone.now()


def _store_pending_two_factor(request, challenge, *, next_url=""):
    request.session[PENDING_2FA_CHALLENGE_SESSION_KEY] = str(challenge.id)
    request.session[PENDING_2FA_USER_SESSION_KEY] = str(challenge.user_id)
    request.session[PENDING_2FA_NEXT_SESSION_KEY] = next_url or ""
    request.session.modified = True


def _clear_pending_two_factor(request):
    request.session.pop(PENDING_2FA_CHALLENGE_SESSION_KEY, None)
    request.session.pop(PENDING_2FA_USER_SESSION_KEY, None)
    request.session.pop(PENDING_2FA_NEXT_SESSION_KEY, None)
    request.session.modified = True


def _pending_two_factor_matches(request, challenge):
    if not challenge:
        return False
    return (
        str(request.session.get(PENDING_2FA_CHALLENGE_SESSION_KEY, "")) == str(challenge.id)
        and str(request.session.get(PENDING_2FA_USER_SESSION_KEY, "")) == str(challenge.user_id)
    )


def _active_user_sessions(user):
    active_sessions = []
    for session in Session.objects.filter(expire_date__gte=timezone.now()).order_by("-expire_date"):
        try:
            decoded = session.get_decoded()
        except Exception:
            continue
        if str(decoded.get("_auth_user_id")) != str(user.pk):
            continue
        active_sessions.append(session)
    return active_sessions


def _build_security_context(user, request):
    current_session_key = request.session.session_key or ""
    active_sessions = _active_user_sessions(user)
    session_keys = [session.session_key for session in active_sessions if session.session_key]
    sign_in_events = list(
        SignInEvent.objects.filter(user=user).order_by("-created_at")[:12]
    )

    latest_event_by_session = {}
    for event in SignInEvent.objects.filter(user=user, session_key__in=session_keys).order_by("-created_at"):
        latest_event_by_session.setdefault(event.session_key, event)

    session_rows = []
    for session in active_sessions:
        event = latest_event_by_session.get(session.session_key)
        is_current = session.session_key == current_session_key
        session_rows.append(
            {
                "session_key": session.session_key,
                "device_label": _device_display_name(event),
                "device_type": getattr(event, "device_type", SignInEvent.DeviceType.OTHER),
                "location": getattr(event, "location", "") or "Unknown location",
                "activity_label": "Active now" if is_current else f"Last seen {timesince(getattr(event, 'created_at', session.expire_date))} ago",
                "is_current": is_current,
            }
        )

    session_rows.sort(key=lambda row: (not row["is_current"], row["device_label"]))

    history_rows = [
        {
            "created_at": event.created_at,
            "device_label": _device_display_name(event),
            "location": event.location or "Unknown location",
            "status_label": event.get_status_display(),
            "status_class": "success" if event.status == SignInEvent.Status.SUCCESS else "danger",
        }
        for event in sign_in_events
    ]

    return {
        "two_factor_enabled": getattr(getattr(user, "preferences", None), "two_factor_enabled", False),
        "active_sessions": session_rows,
        "login_history": history_rows,
    }


def _reset_model_to_defaults(instance, *, preserve_fields=None):
    preserve = set(preserve_fields or ())
    update_fields = []

    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name in preserve:
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        if field.is_relation and field.name == "user":
            continue

        if field.has_default():
            value = field.get_default()
        elif getattr(field, "null", False):
            value = None
        elif isinstance(field, (models.CharField, models.TextField)):
            value = ""
        else:
            continue

        setattr(instance, field.name, value)
        update_fields.append(field.name)

    if update_fields:
        instance.save(update_fields=update_fields)


def _prune_conversations_after_member_data_wipe(conversations):
    for conversation in conversations:
        participant_count = conversation.participants.count()
        latest_message = conversation.messages.order_by("-created_at").first()
        if participant_count < 2 or latest_message is None:
            conversation.delete()
            continue
        conversation.last_message_at = latest_message.created_at
        conversation.save(update_fields=["last_message_at"])


def _delete_file_field_for_queryset(queryset, field_name):
    for item in queryset:
        field_file = getattr(item, field_name, None)
        if field_file:
            field_file.delete(save=False)


def _execute_member_data_wipe(user, *, current_deletion_request):
    profile, _ = Profile.objects.get_or_create(user=user)
    preferences, _ = UserPreference.objects.get_or_create(user=user)

    preserved_profile_fields = {
        "user",
        "has_accepted_platform_agreement",
        "platform_agreement_accepted_at",
        "platform_agreement_version",
        "is_account_paused",
        "account_paused_at",
    }
    preserved_preference_fields = {
        "user",
        "two_factor_enabled",
    }
    preserved_user_fields = {
        "email",
        "password",
        "is_active",
        "is_staff",
        "is_superuser",
        "last_login",
        "date_joined",
    }

    conversations = list(
        Conversation.objects.filter(participants=user)
        .prefetch_related("participants", "messages")
        .distinct()
    )
    owned_posts = list(
        Post.objects.filter(user=user).prefetch_related("gallery_images")
    )
    sent_messages = list(
        Message.objects.filter(sender=user)
    )

    waitlist_entry_ids = [item for item in {profile.source_waitlist_entry_id} if item]
    onboarding_response_ids = [item for item in {profile.source_onboarding_response_id} if item]
    user_email = user.email
    waitlist_entries = list(
        WaitlistEntry.objects.filter(Q(id__in=waitlist_entry_ids) | Q(email__iexact=user_email))
    )

    if profile.profile_image:
        profile.profile_image.delete(save=False)
    if profile.cv_s3_key:
        delete_s3_object(profile.cv_s3_key)
    for entry in waitlist_entries:
        if entry.cv_s3_key:
            delete_s3_object(entry.cv_s3_key)
    for post in owned_posts:
        if post.image:
            post.image.delete(save=False)
        _delete_file_field_for_queryset(post.gallery_images.all(), "image")
    _delete_file_field_for_queryset(sent_messages, "attachment_file")

    WaitlistEmailVerification.objects.filter(email__iexact=user_email).delete()
    WaitlistEntry.objects.filter(id__in=[entry.id for entry in waitlist_entries]).delete()
    OnboardingResponse.objects.filter(Q(id__in=onboarding_response_ids) | Q(email__iexact=user_email)).delete()

    Notification.objects.filter(actor=user).update(actor=None)
    BlockedUser.objects.filter(Q(blocker=user) | Q(blocked=user)).delete()
    ConversationRequest.objects.filter(Q(requester=user) | Q(recipient=user)).delete()
    ConversationUserState.objects.filter(user=user).delete()
    MessageReceipt.objects.filter(user=user).delete()
    MessageReaction.objects.filter(user=user).delete()
    CommentReaction.objects.filter(user=user).delete()
    Comment.objects.filter(user=user).delete()
    SavedPost.objects.filter(user=user).delete()
    Notification.objects.filter(recipient=user).delete()
    Experiences.objects.filter(user=user).delete()
    Active_projects.objects.filter(user=user).delete()
    Project.objects.filter(user=user).delete()
    PostMention.objects.filter(mentioned_user=user).delete()
    Post.objects.filter(user=user).delete()
    SignInEvent.objects.filter(user=user).delete()
    TwoFactorChallenge.objects.filter(user=user).delete()
    DataExportRequest.objects.filter(user=user).delete()
    AccountPauseRequest.objects.filter(user=user).delete()
    DataDeletionRequest.objects.filter(user=user).exclude(id=current_deletion_request.id).delete()

    Message.objects.filter(sender=user).delete()
    user.conversations.clear()
    _prune_conversations_after_member_data_wipe(conversations)

    _reset_model_to_defaults(user, preserve_fields=preserved_user_fields)
    _reset_model_to_defaults(profile, preserve_fields=preserved_profile_fields)
    _reset_model_to_defaults(preferences, preserve_fields=preserved_preference_fields)


def _build_data_export_context(user):
    latest_request = (
        DataExportRequest.objects.filter(user=user)
        .order_by("-requested_at")
        .first()
    )
    return {
        "latest_request": latest_request,
    }


def _build_account_pause_context(user):
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile = None
    latest_request = (
        AccountPauseRequest.objects.filter(user=user)
        .order_by("-requested_at")
        .first()
    )
    return {
        "is_paused": getattr(profile, "is_account_paused", False),
        "paused_at": getattr(profile, "account_paused_at", None),
        "latest_request": latest_request,
    }


def _build_data_deletion_context(user):
    latest_request = (
        DataDeletionRequest.objects.filter(user=user)
        .order_by("-requested_at")
        .first()
    )
    if not latest_request:
        return {
            "has_request": False,
            "requested_at": None,
            "status_label": "Not requested",
        }
    return {
        "has_request": True,
        "requested_at": latest_request.requested_at,
        "processed_at": latest_request.processed_at,
        "status_label": latest_request.get_status_display(),
    }


def _build_settings_page_context(request):
    settings_page = build_settings_context(request.user)
    settings_page["security"] = _build_security_context(request.user, request)
    settings_page["data_export_request"] = _build_data_export_context(request.user)
    settings_page["account_pause"] = _build_account_pause_context(request.user)
    settings_page["data_deletion_request"] = _build_data_deletion_context(request.user)
    return settings_page


SETTINGS_SECTION_ORDER = (
    "account",
    "profile-details",
    "saved-posts",
    "blocked-users",
    "experience-projects",
    "profile-preferences",
    "ai-preferences",
    "notifications",
    "matching-preferences",
    "legal-compliance",
    "danger-zone",
)


SETTINGS_SECTION_CONFIG = {
    "account": {
        "title": "Account",
        "summary": "Email, phone, photo, security, and platform guidelines.",
        "icon": "fa-solid fa-circle-user",
    },
    "profile-details": {
        "title": "Profile Details",
        "summary": "Links, location, bio, and top skills used across your profile.",
        "icon": "fa-solid fa-id-card",
    },
    "saved-posts": {
        "title": "Saved Posts",
        "summary": "Your bookmarked posts, ready to reopen anytime.",
        "icon": "fa-solid fa-bookmark",
    },
    "blocked-users": {
        "title": "Blocked Users",
        "summary": "People you have blocked from messaging and feed visibility.",
        "icon": "fa-solid fa-ban",
    },
    "experience-projects": {
        "title": "Experience & Projects",
        "summary": "Add work history and active ventures without leaving settings.",
        "icon": "fa-solid fa-briefcase",
    },
    "profile-preferences": {
        "title": "Profile Preferences",
        "summary": "Visibility, search, badge, and matching presence controls.",
        "icon": "fa-solid fa-eye",
    },
    "ai-preferences": {
        "title": "CoVise AI Agent",
        "summary": "Preview the upcoming AI permissions and activity controls.",
        "icon": "fa-solid fa-robot",
    },
    "notifications": {
        "title": "Notifications",
        "summary": "Email and in-app notification preferences in one place.",
        "icon": "fa-solid fa-bell",
    },
    "matching-preferences": {
        "title": "Matching Preferences",
        "summary": "Who you want to match with and where you are open to build.",
        "icon": "fa-solid fa-sliders",
    },
    "legal-compliance": {
        "title": "Legal & Compliance",
        "summary": "Agreements, policies, exports, and data deletion requests.",
        "icon": "fa-solid fa-scale-balanced",
    },
    "danger-zone": {
        "title": "Danger Zone",
        "summary": "Pause or permanently delete your account.",
        "icon": "fa-solid fa-triangle-exclamation",
    },
}


def _append_query_params(url, **params):
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _safe_redirect_url(request, fallback_url):
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def _get_settings_section_config(section_slug):
    config = SETTINGS_SECTION_CONFIG.get(section_slug)
    if not config:
        raise Http404("Settings section not found")
    return {
        "slug": section_slug,
        "url": reverse("Settings Section", args=[section_slug]),
        **config,
    }


def _build_settings_sections():
    return [_get_settings_section_config(section_slug) for section_slug in SETTINGS_SECTION_ORDER]


def _build_settings_view_context(request, section_slug=None):
    context = {
        "profile_photo_max_size_bytes": PROFILE_PHOTO_MAX_SIZE_BYTES,
        "profile_photo_max_size_mb": PROFILE_PHOTO_MAX_SIZE_MB,
        "settings_page": _build_settings_page_context(request),
        "settings_sections": _build_settings_sections(),
        "settings_return_url": reverse("Settings"),
        "settings_form_action": reverse("Settings"),
    }
    if section_slug:
        section = _get_settings_section_config(section_slug)
        context.update(
            {
                "settings_active_section": section_slug,
                "settings_section": section,
                "settings_section_title": section["title"],
                "settings_section_summary": section["summary"],
                "settings_return_url": section["url"],
                "settings_form_action": section["url"],
            }
        )
    if request.GET.get("saved") == "1":
        context["success_message"] = "Saved successfully."
        context["save_success"] = True
    if request.GET.get("saved") == "2":
        context["error_message"] = "An error occurred while saving. Please try again."
        context["save_success"] = False
    if request.GET.get("blocked") == "1":
        context["success_message"] = "User blocked successfully."
        context["save_success"] = True
    if request.GET.get("unblocked") == "1":
        context["success_message"] = "User unblocked successfully."
        context["save_success"] = True
    if request.GET.get("delete_account") == "todo":
        context["error_message"] = "Delete account is wired to a backend view but not implemented yet."
        context["save_success"] = False
    if request.GET.get("delete_account") == "error":
        context["error_message"] = "We could not delete your account right now. Please try again."
        context["save_success"] = False
    if request.GET.get("data_export") == "completed":
        context["success_message"] = "Your data export was emailed successfully."
        context["save_success"] = True
    if request.GET.get("data_export") == "error":
        context["error_message"] = "We could not prepare your data export right now. Please try again."
        context["save_success"] = False
    if request.GET.get("account_pause") == "paused":
        context["success_message"] = "Your account is now paused. You can still browse and reactivate anytime."
        context["save_success"] = True
    if request.GET.get("account_pause") == "reactivated":
        context["success_message"] = "Your account has been reactivated."
        context["save_success"] = True
    if request.GET.get("account_pause") == "blocked":
        context["error_message"] = "Your account is paused. Reactivate it to resume posting, messaging, and other activity."
        context["save_success"] = False
    if request.GET.get("account_pause") == "error":
        context["error_message"] = "We could not update your pause status right now. Please try again."
        context["save_success"] = False
    if request.GET.get("data_deletion") == "completed":
        context["success_message"] = "Your user data was deleted while keeping your login account active."
        context["save_success"] = True
    if request.GET.get("data_deletion") == "error":
        context["error_message"] = "We could not complete your data deletion right now. Please try again."
        context["save_success"] = False
    security_action = request.GET.get("security", "").strip()
    if security_action == "2fa-enabled":
        context["success_message"] = "Two-factor authentication is now enabled."
        context["save_success"] = True
    if security_action == "2fa-disabled":
        context["success_message"] = "Two-factor authentication has been disabled."
        context["save_success"] = True
    if security_action == "session-ended":
        context["success_message"] = "That session has been logged out."
        context["save_success"] = True
    if security_action == "other-sessions-ended":
        context["success_message"] = "All other active sessions have been logged out."
        context["save_success"] = True
    return context


def _handle_settings_post(request, *, template_name, redirect_url, section_slug=None):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    preferences, _ = UserPreference.objects.get_or_create(user=request.user)
    user = request.user
    save_section = request.POST.get("save_section")

    try:
        if save_section == "personal_data":
            full_name = request.POST.get("full_name", "").strip()
            email = request.POST.get("email", "").strip()
            phone_number = request.POST.get("phone_number", "").strip()
            profile_photo_action = request.POST.get("profile_photo_action", "").strip()
            uploaded_profile_image = request.FILES.get("profile_image")
            if full_name != (user.full_name or "").strip():
                user.full_name = full_name
                user.save(update_fields=["full_name"])
            if email and email != user.email:
                if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                    context = _build_settings_view_context(request, section_slug=section_slug)
                    context["error_message"] = "This email is already registered on CoVise. Please sign in instead."
                    context["save_success"] = False
                    return render(request, template_name, context)
                user.email = email
                user.save(update_fields=["email"])

            profile.full_name = full_name
            profile.phone_number = phone_number
            profile_update_fields = ["full_name", "phone_number"]

            if profile_photo_action == "remove":
                if profile.profile_image:
                    profile.profile_image.delete(save=False)
                profile.profile_image = None
                profile_update_fields.append("profile_image")
            elif uploaded_profile_image:
                if uploaded_profile_image.size > PROFILE_PHOTO_MAX_SIZE_BYTES:
                    context = _build_settings_view_context(request, section_slug=section_slug)
                    context["error_message"] = f"Profile photo must be {PROFILE_PHOTO_MAX_SIZE_MB} MB or smaller."
                    context["save_success"] = False
                    return render(request, template_name, context)
                profile.profile_image = uploaded_profile_image
                profile_update_fields.append("profile_image")

            profile.save(update_fields=profile_update_fields)

        if save_section == "professional_data":
            linkedin = request.POST.get("linkedin", "").strip()
            github = request.POST.get("github", "").strip()
            proof_of_work_url = request.POST.get("proof_of_work_url", "").strip()
            location = request.POST.get("location", "").strip()
            nationality = request.POST.get("nationality", "").strip()
            bio = request.POST.get("bio", "").strip()

            profile.linkedin = linkedin
            profile.github = github
            profile.proof_of_work_url = proof_of_work_url
            profile.country = location
            profile.nationality = nationality
            profile.bio = bio
            skill_config = get_onboarding_skill_config()
            allowed_skills = set(skill_config["options"])
            submitted_skills = [item.strip() for item in request.POST.get("skills", "").split("|") if item.strip()]
            deduped_skills = []
            for item in submitted_skills:
                if item in allowed_skills and item not in deduped_skills:
                    deduped_skills.append(item)
            deduped_skills = deduped_skills[:skill_config["max_selected"]]
            profile.skills = deduped_skills
            profile.save(update_fields=["linkedin", "github", "proof_of_work_url", "country", "nationality", "bio", "skills"])

        if save_section == "experiences":
            title = request.POST.get("title", "").strip()
            date = request.POST.get("date", "").strip()
            desc = request.POST.get("desc", "").strip()
            Experiences.objects.create(
                user=request.user,
                title=title,
                date=date,
                desc=desc,
            )

        if save_section == "projects":
            name = request.POST.get("name", "").strip()
            status = request.POST.get("status", "").strip()
            desc = request.POST.get("desc", "").strip()
            Active_projects.objects.create(
                user=request.user,
                name=name,
                status=status,
                desc=desc,
            )

        if save_section == "profile_preferences":
            profile_visibility = request.POST.get("profile_visibility")
            show_conviction_score = request.POST.get("show_conviction_score")
            show_cv_to_matches = request.POST.get("show_cv_to_matches")
            show_linkedin_to_matches = request.POST.get("show_linkedin_to_matches")
            appear_in_search = request.POST.get("appear_in_search")
            pause_matching = request.POST.get("pause_matching")
            show_cofounder_badge = request.POST.get("show_cofounder_badge")
            if profile_visibility:
                preferences.profile_visibility = profile_visibility
            preferences.show_conviction_score = _as_bool(show_conviction_score)
            preferences.show_cv_to_matches = _as_bool(show_cv_to_matches)
            preferences.show_linkedin_to_matches = _as_bool(show_linkedin_to_matches)
            preferences.appear_in_search = _as_bool(appear_in_search)
            preferences.pause_matching = _as_bool(pause_matching)
            if show_cofounder_badge is not None:
                onboarding_answers = dict(getattr(profile, "onboarding_answers", {}) or {})
                onboarding_answers["show_cofounder_badge"] = _as_bool(show_cofounder_badge)
                profile.onboarding_answers = onboarding_answers
                profile.save(update_fields=["onboarding_answers"])
            preferences.save(update_fields=["profile_visibility", "show_conviction_score", "show_cv_to_matches", "show_linkedin_to_matches", "appear_in_search", "pause_matching"])

        if save_section == "ai_preferences":
            ai_enabled = request.POST.get("ai_enabled")
            read_profile_data = request.POST.get("read_profile_data")
            ai_read_messages = request.POST.get("ai_read_messages")
            ai_read_workspace = request.POST.get("ai_read_workspace")
            ai_post_updates = request.POST.get("ai_post_updates")
            ai_send_messages = request.POST.get("ai_send_messages")
            ai_edit_workspace = request.POST.get("ai_edit_workspace")
            ai_manage_milestones = request.POST.get("ai_manage_milestones")

            preferences.ai_enabled = _as_bool(ai_enabled)
            preferences.read_profile_data = _as_bool(read_profile_data)
            preferences.ai_read_messages = _as_bool(ai_read_messages)
            preferences.ai_read_workspace = _as_bool(ai_read_workspace)
            preferences.ai_post_updates = _as_bool(ai_post_updates)
            preferences.ai_send_messages = _as_bool(ai_send_messages)
            preferences.ai_edit_workspace = _as_bool(ai_edit_workspace)
            preferences.ai_manage_milestones = _as_bool(ai_manage_milestones)
            preferences.save(update_fields=["ai_enabled", "read_profile_data", "ai_read_messages", "ai_read_workspace", "ai_post_updates", "ai_send_messages", "ai_edit_workspace", "ai_manage_milestones"])

        if save_section == "notifications":
            profile, _created = Profile.objects.get_or_create(user=request.user)
            email_frequency = request.POST.get("email_frequency")
            receive_email_notifications = request.POST.get("receive_email_notifications")
            email_new_match = request.POST.get("email_new_match")
            email_new_message = request.POST.get("email_new_message")
            email_connection_request = request.POST.get("email_connection_request")
            email_request_accepted = request.POST.get("email_request_accepted")
            email_milestone_reminder = request.POST.get("email_milestone_reminder")
            email_workspace_activity = request.POST.get("email_workspace_activity")
            email_platform_updates = request.POST.get("email_platform_updates")
            email_marketing = request.POST.get("email_marketing")
            in_app_new_match = request.POST.get("in_app_new_match")
            in_app_new_message = request.POST.get("in_app_new_message")
            in_app_connection_request = request.POST.get("in_app_connection_request")
            in_app_request_accepted = request.POST.get("in_app_request_accepted")
            in_app_milestone_reminder = request.POST.get("in_app_milestone_reminder")
            in_app_workspace_activity = request.POST.get("in_app_workspace_activity")
            in_app_platform_updates = request.POST.get("in_app_platform_updates")
            in_app_marketing = request.POST.get("in_app_marketing")

            if email_frequency:
                preferences.email_frequency = email_frequency
            profile.receive_email_notifications = _as_bool(receive_email_notifications)
            preferences.email_new_match = _as_bool(email_new_match)
            preferences.email_new_message = _as_bool(email_new_message)
            preferences.email_connection_request = _as_bool(email_connection_request)
            preferences.email_request_accepted = _as_bool(email_request_accepted)
            preferences.email_milestone_reminder = _as_bool(email_milestone_reminder)
            preferences.email_workspace_activity = _as_bool(email_workspace_activity)
            preferences.email_platform_updates = _as_bool(email_platform_updates)
            preferences.email_marketing = _as_bool(email_marketing)
            preferences.in_app_new_match = _as_bool(in_app_new_match)
            preferences.in_app_new_message = _as_bool(in_app_new_message)
            preferences.in_app_connection_request = _as_bool(in_app_connection_request)
            preferences.in_app_request_accepted = _as_bool(in_app_request_accepted)
            preferences.in_app_milestone_reminder = _as_bool(in_app_milestone_reminder)
            preferences.in_app_workspace_activity = _as_bool(in_app_workspace_activity)
            preferences.in_app_platform_updates = _as_bool(in_app_platform_updates)
            preferences.in_app_marketing = _as_bool(in_app_marketing)
            profile.save(update_fields=["receive_email_notifications"])
            preferences.save(update_fields=["email_frequency", "email_new_match", "email_new_message", "email_connection_request", "email_request_accepted", "email_milestone_reminder", "email_workspace_activity", "email_platform_updates", "email_marketing", "in_app_new_match", "in_app_new_message", "in_app_connection_request", "in_app_request_accepted", "in_app_milestone_reminder", "in_app_workspace_activity", "in_app_platform_updates", "in_app_marketing"])

        if save_section == "matching_preferences":
            preferred_cofounder_types = request.POST.get("preferred_cofounder_types")
            preferred_industries = request.POST.get("preferred_industries")
            preferred_gcc_markets = request.POST.get("preferred_gcc_markets")
            minimum_commitment = request.POST.get("minimum_commitment")
            open_to_foreign_founders = request.POST.get("open_to_foreign_founders")
            pause_matching = request.POST.get("pause_matching")
            preferences.preferred_cofounder_types = _split_pipe_list(preferred_cofounder_types)
            preferences.preferred_industries = _split_pipe_list(preferred_industries)
            preferences.preferred_gcc_markets = _split_pipe_list(preferred_gcc_markets)
            if minimum_commitment:
                preferences.minimum_commitment = minimum_commitment
            preferences.open_to_foreign_founders = _as_bool(open_to_foreign_founders)
            preferences.pause_matching = _as_bool(pause_matching)
            preferences.save(update_fields=["preferred_cofounder_types", "pause_matching", "preferred_industries", "preferred_gcc_markets", "minimum_commitment", "open_to_foreign_founders"])

        if save_section == "security":
            security_action = request.POST.get("security_action", "").strip()

            if security_action == "enable_2fa":
                preferences.two_factor_enabled = True
                preferences.save(update_fields=["two_factor_enabled"])
                return redirect(_append_query_params(redirect_url, security="2fa-enabled"))

            if security_action == "disable_2fa":
                preferences.two_factor_enabled = False
                preferences.save(update_fields=["two_factor_enabled"])
                return redirect(_append_query_params(redirect_url, security="2fa-disabled"))

            if security_action == "logout_session":
                session_key = request.POST.get("session_key", "").strip()
                if session_key:
                    Session.objects.filter(session_key=session_key).delete()
                    if session_key == request.session.session_key:
                        logout(request)
                        return redirect(f"{reverse('Login')}?logged_out=1")
                return redirect(_append_query_params(redirect_url, security="session-ended"))

            if security_action == "logout_other_sessions":
                current_session_key = request.session.session_key or ""
                for session in _active_user_sessions(request.user):
                    if session.session_key and session.session_key != current_session_key:
                        session.delete()
                return redirect(_append_query_params(redirect_url, security="other-sessions-ended"))

        return redirect(_append_query_params(redirect_url, saved="1"))
    except Exception:
        return redirect(_append_query_params(redirect_url, saved="2"))


def _agreement_next_url(request):
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if not next_url or next_url.startswith("/agreement"):
        return reverse("Home")
    return next_url


def _display_value(value, fallback=""):
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts)
    if isinstance(value, dict):
        parts = [str(item).strip() for item in value.values() if str(item).strip()]
        return ", ".join(parts)
    return str(value).strip() if value else fallback


def _top_skill_labels(value, limit=3):
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, dict):
        items = [str(item).strip() for item in value.values() if str(item).strip()]
    elif value:
        items = [str(value).strip()]
    else:
        items = []

    deduped = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:limit]


def _normalized_choice_values(value):
    if isinstance(value, dict):
        raw_items = value.values()
    elif isinstance(value, (list, tuple, set)):
        raw_items = value
    elif value in (None, "", [], {}, ()):
        raw_items = []
    else:
        raw_items = [value]

    normalized = []
    for item in raw_items:
        text = " ".join(str(item or "").strip().lower().replace("/", " ").replace("-", " ").split())
        if text:
            normalized.append(text)
    return normalized


def _normalized_skill_label(label):
    return re.sub(r"[^a-z0-9]+", " ", str(label or "").strip().lower()).strip()


def _profile_is_looking_for_cofounder(profile):
    if not profile:
        return False

    onboarding_answers = getattr(profile, "onboarding_answers", {}) or {}
    cofounder_count_values = (
        _normalized_choice_values(getattr(profile, "cofounders_needed", None))
        + _normalized_choice_values(onboarding_answers.get("cofounders_needed"))
    )
    if any(value not in {"0", "none", "no"} for value in cofounder_count_values):
        return True

    desired_partner_values = (
        _normalized_choice_values(getattr(profile, "looking_for_type", None))
        + _normalized_choice_values(onboarding_answers.get("looking_for_type"))
    )
    return any("cofounder" in value or "co founder" in value for value in desired_partner_values)


def _profile_show_cofounder_badge(profile):
    if not profile:
        return False

    onboarding_answers = getattr(profile, "onboarding_answers", {}) or {}
    explicit_preference = onboarding_answers.get("show_cofounder_badge")
    if explicit_preference is None:
        return True
    if isinstance(explicit_preference, str):
        return explicit_preference.strip().lower() in {"1", "true", "yes", "on"}
    return bool(explicit_preference)


def _profile_has_visible_cofounder_badge(profile):
    return _profile_is_looking_for_cofounder(profile) and _profile_show_cofounder_badge(profile)


def _skill_tone(label):
    normalized = _normalized_skill_label(label)
    tone_map = {
        "software engineering": "blue",
        "full stack development": "blue",
        "frontend react next js": "blue",
        "backend node python java": "blue",
        "mobile ios android flutter": "blue",
        "devops cloud": "blue",
        "data engineering": "blue",
        "ai ml engineering": "blue",
        "llms prompting": "blue",
        "data science": "blue",
        "cybersecurity": "blue",
        "software engineer": "blue",
        "data scientist ai engineer": "blue",
        "developer": "blue",
        "engineer": "blue",
        "technical": "blue",
        "product management": "violet",
        "product": "violet",
        "product manager": "violet",
        "ux ui design": "amber",
        "branding": "amber",
        "content copywriting": "amber",
        "software designer": "amber",
        "designer": "amber",
        "ui ux designer": "amber",
        "ux designer": "amber",
        "brand designer": "amber",
        "growth marketing": "green",
        "performance marketing": "green",
        "sales": "green",
        "business development": "green",
        "partnerships": "green",
        "customer success": "green",
        "community building": "green",
        "marketing": "green",
        "growth": "green",
        "operations": "red",
        "strategy": "red",
        "finance": "red",
        "fundraising": "red",
        "legal compliance": "red",
        "hr hiring": "red",
        "supply chain": "red",
        "industry expertise": "red",
        "operations": "red",
        "legal": "red",
    }
    return tone_map.get(normalized, "default")


def _profile_skill_labels(profile, limit=2):
    if not profile:
        return []
    profile_skills = getattr(profile, "skills", None)
    if profile_skills is not None:
        labels = _top_skill_labels(profile_skills, limit=limit)
        return [{"label": label, "tone": _skill_tone(label)} for label in labels]
    onboarding_answers = getattr(profile, "onboarding_answers", {}) or {}
    labels = _top_skill_labels(onboarding_answers.get("skills"), limit=limit)
    return [{"label": label, "tone": _skill_tone(label)} for label in labels]


def _normalized_overlap_tokens(value):
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, dict):
        raw_items = value.values()
    elif value:
        raw_items = [value]
    else:
        raw_items = []

    tokens = set()
    for item in raw_items:
        cleaned = " ".join(str(item or "").strip().lower().replace("/", " ").replace("-", " ").split())
        if cleaned:
            tokens.add(cleaned)
    return tokens


def _experience_datetime_from_input(raw_value):
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _profile_domain_tokens(profile):
    if not profile:
        return set()

    token_fields = (
        getattr(profile, "skills", None),
        getattr(profile, "industry", None),
        getattr(profile, "industries_interested", None),
        getattr(profile, "investment_industries", None),
    )
    tokens = set()
    for field_value in token_fields:
        tokens.update(_normalized_overlap_tokens(field_value))
    return tokens


MENTION_PATTERN = re.compile(r"@([A-Za-z0-9._-]{2,50})")
COMMENT_REACTION_ACTION_MAP = {
    "upvote": CommentReaction.ReactionType.THUMBS_UP,
    "thumbs_up": CommentReaction.ReactionType.THUMBS_UP,
    "downvote": CommentReaction.ReactionType.THUMBS_DOWN,
    "thumbs_down": CommentReaction.ReactionType.THUMBS_DOWN,
    "fire": CommentReaction.ReactionType.FIRE,
    "rocket": CommentReaction.ReactionType.ROCKET,
    "crazy": CommentReaction.ReactionType.CRAZY,
}
MESSAGE_REACTION_ACTION_MAP = {
    "thumbs_up": MessageReaction.ReactionType.THUMBS_UP,
    "fire": MessageReaction.ReactionType.FIRE,
}
POST_REACTION_ACTION_MAP = {
    "thumbs_up": PostReaction.ReactionType.THUMBS_UP,
    "thumbs_down": PostReaction.ReactionType.THUMBS_DOWN,
}


def _normalize_handle_token(value):
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def _mention_candidates_for_user(user):
    candidates = set()
    email_local = (getattr(user, "email", "") or "").split("@")[0]
    normalized_email = _normalize_handle_token(email_local)
    if len(normalized_email) >= 2:
        candidates.add(normalized_email)

    full_name = getattr(user, "full_name", "") or ""
    normalized_name = _normalize_handle_token(full_name)
    if len(normalized_name) >= 2:
        candidates.add(normalized_name)

    for part in full_name.split():
        normalized_part = _normalize_handle_token(part)
        if len(normalized_part) >= 3:
            candidates.add(normalized_part)
    return candidates


def _resolve_post_mentions(content, *, exclude_user_id=None):
    requested_tokens = []
    token_label_map = {}
    for raw_handle in MENTION_PATTERN.findall(content or ""):
        normalized = _normalize_handle_token(raw_handle)
        if normalized and normalized not in requested_tokens:
            requested_tokens.append(normalized)
            token_label_map[normalized] = raw_handle
    if not requested_tokens:
        return []

    users = list(User.objects.select_related("profile").all())
    matches = []
    for token in requested_tokens:
        matching_users = [
            user for user in users
            if user.id != exclude_user_id and token in _mention_candidates_for_user(user)
        ]
        if len(matching_users) == 1:
            matches.append((token_label_map.get(token, token), matching_users[0]))
    return matches


def _render_post_content_html(post):
    content = getattr(post, "content", "") or ""
    mention_map = {}
    mentions = getattr(post, "mentions_cache", None)
    if mentions is None and hasattr(post, "mentions"):
        mention_source = getattr(post, "mentions")
        mentions = list(mention_source.all()) if hasattr(mention_source, "all") else list(mention_source)
    for mention in mentions or []:
        mentioned_user = getattr(mention, "mentioned_user", None)
        if not mentioned_user:
            continue
        mention_map[_normalize_handle_token(getattr(mention, "handle_text", ""))] = {
            "url": reverse("Public Profile", args=[mentioned_user.id]),
            "label": getattr(mention, "handle_text", ""),
        }

    pieces = []
    last_index = 0
    for match in MENTION_PATTERN.finditer(content):
        start, end = match.span()
        pieces.append(_render_post_content_segment_html(content[last_index:start]))
        raw_handle = match.group(1)
        normalized = _normalize_handle_token(raw_handle)
        mention_data = mention_map.get(normalized)
        if mention_data:
            pieces.append(
                f'<a class="post-mention-link" href="{escape(mention_data["url"])}">@{escape(mention_data["label"] or raw_handle)}</a>'
            )
        else:
            pieces.append(escape(match.group(0)))
        last_index = end
    pieces.append(_render_post_content_segment_html(content[last_index:]))
    return "".join(pieces).replace("\n", "<br>")


def _render_post_content_segment_html(text):
    escaped = escape(text or "")
    escaped = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", escaped, flags=re.DOTALL)
    escaped = re.sub(r"(?<!\*)\*(?=\S)(.+?)(?<=\S)\*(?!\*)", r"<em>\1</em>", escaped, flags=re.DOTALL)
    return escaped


def _profile_country_label(profile):
    if not profile:
        return ""
    return (
        _country_display_label(getattr(profile, "country", ""))
        or _country_display_label(_display_value(getattr(profile, "home_country", None), ""))
        or _country_display_label(getattr(profile, "custom_country", ""))
    )


def _blocked_profile_search_ids(user):
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    hidden_ids = set()
    relationships = BlockedUser.objects.filter(
        Q(blocker=user) | Q(blocked=user)
    ).values_list("blocker_id", "blocked_id")
    for blocker_id, blocked_id in relationships:
        if blocker_id == user.id:
            hidden_ids.add(blocked_id)
        else:
            hidden_ids.add(blocker_id)
    return hidden_ids


def _searchable_users_for_home(user):
    hidden_ids = _blocked_profile_search_ids(user)
    candidates = (
        User.objects.select_related("profile", "preferences")
        .exclude(id__in=hidden_ids)
        .exclude(profile__is_account_paused=True)
        .filter(Q(preferences__appear_in_search=True) | Q(preferences__isnull=True))
        .distinct()
        .order_by("full_name", "email")
    )

    items = []
    for candidate in candidates:
        try:
            profile = candidate.profile
        except Profile.DoesNotExist:
            profile = None

        display_name = _display_name(candidate)
        location = _profile_country_label(profile)
        headline = (
            str(getattr(profile, "bio", "") or "").strip()
            or _display_value(getattr(profile, "one_liner", None))
            or _display_value((getattr(profile, "onboarding_answers", {}) or {}).get("one_liner"))
        )
        role = _display_value(getattr(profile, "current_role", None))
        skills = ", ".join(_top_skill_labels(getattr(profile, "skills", None), limit=4))
        searchable_text = " ".join(
            part for part in [
                display_name,
                location,
                headline,
                role,
                skills,
            ] if part
        )
        items.append(
                {
                    "id": str(candidate.id),
                    "display_name": display_name,
                    "avatar_initials": candidate.avatar_initials,
                    "avatar_url": _profile_avatar_url(profile),
                    "profile_url": reverse("Profile") if candidate.id == user.id else reverse("Public Profile", args=[candidate.id]),
                "location": location,
                "headline": headline,
                "search_text": searchable_text,
            }
        )
    return items


def _comment_reaction_payload(comment, *, viewer=None):
    reactions = list(comment.reactions.all()) if hasattr(comment, "reactions") else list(CommentReaction.objects.filter(comment=comment))
    thumbs_up = sum(1 for item in reactions if item.reaction in {CommentReaction.ReactionType.THUMBS_UP, "up"})
    thumbs_down = sum(1 for item in reactions if item.reaction in {CommentReaction.ReactionType.THUMBS_DOWN, "down"})
    fire = sum(1 for item in reactions if item.reaction == CommentReaction.ReactionType.FIRE)
    rocket = sum(1 for item in reactions if item.reaction == CommentReaction.ReactionType.ROCKET)
    crazy = sum(1 for item in reactions if item.reaction == CommentReaction.ReactionType.CRAZY)
    viewer_reactions = []
    if viewer and getattr(viewer, "is_authenticated", False):
        for item in reactions:
            if item.user_id != viewer.id:
                continue
            if item.reaction in {CommentReaction.ReactionType.THUMBS_UP, "up"}:
                viewer_reactions.append(CommentReaction.ReactionType.THUMBS_UP)
            elif item.reaction in {CommentReaction.ReactionType.THUMBS_DOWN, "down"}:
                viewer_reactions.append(CommentReaction.ReactionType.THUMBS_DOWN)
            elif item.reaction == CommentReaction.ReactionType.FIRE:
                viewer_reactions.append(CommentReaction.ReactionType.FIRE)
            elif item.reaction == CommentReaction.ReactionType.ROCKET:
                viewer_reactions.append(CommentReaction.ReactionType.ROCKET)
            elif item.reaction == CommentReaction.ReactionType.CRAZY:
                viewer_reactions.append(CommentReaction.ReactionType.CRAZY)
    comment.up = thumbs_up
    comment.down = thumbs_down
    comment.viewer_reactions = viewer_reactions
    comment.fire_count = fire
    comment.rocket_count = rocket
    comment.crazy_count = crazy
    return {
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "fire": fire,
        "rocket": rocket,
        "crazy": crazy,
        "viewer_reactions": viewer_reactions,
    }


def _message_reaction_payload(message, *, viewer=None):
    reactions = list(message.reactions.all()) if hasattr(message, "reactions") else list(MessageReaction.objects.filter(message=message))
    counts = {
        "thumbs_up": sum(1 for item in reactions if item.reaction == MessageReaction.ReactionType.THUMBS_UP),
        "fire": sum(1 for item in reactions if item.reaction == MessageReaction.ReactionType.FIRE),
    }
    viewer_reactions = []
    if viewer and getattr(viewer, "is_authenticated", False):
        viewer_reactions = [item.reaction for item in reactions if item.user_id == viewer.id]
    return counts, viewer_reactions


def _is_complete_onboarding_response(response):
    if not response:
        return False
    answers = getattr(response, "answers", None) or {}
    flow_name = str(getattr(response, "flow_name", "") or "").strip()
    return bool(answers) and bool(flow_name)


def _home_sidebar_metrics(user):
    now = timezone.now()
    week_ago = now - timezone.timedelta(days=7)

    verified_founders_count = WaitlistEntry.objects.count()
    open_opportunities_count = (
        OnboardingResponse.objects.exclude(flow_name="")
        .exclude(answers={})
        .values("email")
        .distinct()
        .count()
    )

    request_items = list(
        ConversationRequest.objects.filter(
            Q(requester=user) | Q(recipient=user),
        ).select_related("requester", "recipient")
    )
    visible_request_items = [
        item for item in request_items if not _is_blocked_pair(item.requester, item.recipient)
    ]
    accepted_this_week_count = sum(
        1
        for item in visible_request_items
        if item.status == ConversationRequest.Status.ACCEPTED
        and item.responded_at
        and item.responded_at >= week_ago
    )
    pending_requests_count = sum(
        1 for item in visible_request_items if item.status == ConversationRequest.Status.PENDING
    )

    current_profile = getattr(user, "profile", None)
    current_tokens = _profile_domain_tokens(current_profile)
    blocked_ids = _blocked_user_ids(user)
    same_domain_count = 0
    if current_tokens:
        candidate_profiles = (
            Profile.objects.select_related("user")
            .exclude(user=user)
            .exclude(user_id__in=blocked_ids)
        )
        for profile in candidate_profiles:
            if current_tokens.intersection(_profile_domain_tokens(profile)):
                same_domain_count += 1

    return {
        "verified_founders_count": verified_founders_count,
        "verified_founders_delta": "Waitlist profiles",
        "open_opportunities_count": open_opportunities_count,
        "open_opportunities_delta": "Completed onboarding",
        "new_matches_count": accepted_this_week_count + pending_requests_count,
        "new_matches_delta_clean": f"{accepted_this_week_count} accepted this week - {pending_requests_count} pending",
        "new_matches_delta": f"{accepted_this_week_count} accepted this week · {pending_requests_count} pending",
        "same_domain_count": same_domain_count,
        "same_domain_delta": "Shared skills or interests",
        "pending_requests_count": pending_requests_count,
        "accepted_this_week_count": accepted_this_week_count,
    }


def _home_sidebar_metrics(user):
    start_of_day = timezone.make_aware(
        timezone.datetime.combine(timezone.localdate(), timezone.datetime.min.time()),
        timezone.get_current_timezone(),
    )
    start_of_week_date = timezone.localdate() - timezone.timedelta(days=timezone.localdate().weekday())
    start_of_week = timezone.make_aware(
        timezone.datetime.combine(start_of_week_date, timezone.datetime.min.time()),
        timezone.get_current_timezone(),
    )
    verified_waitlist_entries = WaitlistEntry.objects.filter(
        status__in=[
            WaitlistEntry.Status.APPROVED,
            WaitlistEntry.Status.ACTIVATED,
        ]
    )
    verified_founders_count = verified_waitlist_entries.count()
    activated_accounts_this_week = User.objects.filter(
        date_joined__gte=start_of_week,
        profile__source_waitlist_entry__status=WaitlistEntry.Status.ACTIVATED,
    ).distinct().count()
    waitlist_count = WaitlistEmailVerification.objects.count()
    posts_count = Post.objects.filter(user=user).count()
    waitlist_today = WaitlistEmailVerification.objects.filter(created_at__gte=start_of_day).count()
    posts_today = Post.objects.filter(user=user, created_at__gte=start_of_day).count()

    approved_country_keys = set()
    for country, custom_country in verified_waitlist_entries.values_list("country", "custom_country"):
        normalized_country = (custom_country or country or "").strip()
        if normalized_country:
            approved_country_keys.add(normalized_country.casefold())

    return {
        "verified_founders_count": verified_founders_count,
        "verified_founders_delta": f"{activated_accounts_this_week}+ Joined this week",
        "waitlist_count": waitlist_count,
        "waitlist_delta": f"{waitlist_today}+ today",
        "countries_involved_count": len(approved_country_keys),
        "countries_involved_delta": "UAE, Saudi Arabia, ...",
        "posts_count": posts_count,
        "posts_delta": f"{posts_today}+ today",
    }


def _home_quick_requests(user, limit=2):
    requests = list(
        ConversationRequest.objects.filter(
            Q(requester=user) | Q(recipient=user)
        )
        .select_related(
            "requester",
            "requester__profile",
            "recipient",
            "recipient__profile",
        )
        .order_by(
            Case(
                When(recipient=user, status=ConversationRequest.Status.PENDING, then=0),
                When(requester=user, status=ConversationRequest.Status.PENDING, then=1),
                default=2,
                output_field=IntegerField(),
            ),
            "-created_at",
        )[:limit]
    )

    items = []
    for request_item in requests:
        other_user = request_item.recipient if request_item.requester_id == user.id else request_item.requester
        if not other_user or _is_blocked_pair(user, other_user):
            continue

        is_incoming = request_item.recipient_id == user.id
        if request_item.status == ConversationRequest.Status.PENDING:
            status_line = "Received - Pending" if is_incoming else "Sent - Awaiting response"
        elif request_item.status == ConversationRequest.Status.ACCEPTED:
            status_line = "Received - Accepted" if is_incoming else "Sent - Accepted"
        else:
            status_line = "Received - Declined" if is_incoming else "Sent - Declined"

        items.append({
            "id": str(request_item.id),
            "display_name": _display_name(other_user),
            "avatar_initials": other_user.avatar_initials,
            "avatar_url": _user_avatar_url(other_user),
            "status": request_item.status,
            "status_line": status_line,
            "is_incoming": is_incoming,
            "show_actions": is_incoming and request_item.status == ConversationRequest.Status.PENDING,
        })
    return items


def _home_welcome_subtitle(metrics):
    return "Your network is active."


def _post_gallery_items(post, limit=6):
    items = []
    seen_urls = set()

    gallery_relation = getattr(post, "gallery_images", None)
    gallery_images = list(gallery_relation.all()) if gallery_relation is not None else []
    for gallery_image in gallery_images:
        image_file = getattr(gallery_image, "image", None)
        image_url = _safe_media_url(image_file)
        if image_url and image_url not in seen_urls:
            seen_urls.add(image_url)
            items.append({
                "url": image_url,
                "alt": getattr(post, "title", "") or "Post image",
            })

    legacy_image = getattr(post, "image", None)
    legacy_url = _safe_media_url(legacy_image)
    if legacy_url and legacy_url not in seen_urls:
        items.insert(0, {
            "url": legacy_url,
            "alt": getattr(post, "title", "") or "Post image",
        })

    return items[:limit]


def _attach_post_feed_metadata(posts, current_user=None):
    for post in posts:
        profile = getattr(post.user, "profile", None)
        post.avatar_url = _profile_avatar_url(profile)
        post.mentions_cache = list(post.mentions.select_related("mentioned_user")) if hasattr(post, "mentions") else []
        post.feed_title = _build_post_feed_title(post)
        post.feed_title_html = _render_post_title_html(post.feed_title)
        post.feed_skills = _profile_skill_labels(profile, limit=2)
        post.show_cofounder_badge = _profile_has_visible_cofounder_badge(profile)
        post.theme_class = _post_theme_class(post)
        post.relative_time = _relative_time_label(post.created_at)
        post.feed_images = _post_gallery_items(post, limit=6)
        post.feed_image_count = len(post.feed_images)
        post.feed_country = _profile_country_label(profile)
        post.feed_country_display = _country_display_label(post.feed_country)
        post.content_html = _render_post_content_html(post)
        post.owner_display_name = _display_name(post.user)
        post.feed_post_type_label = _post_type_display_label(post)
        post.is_founders_spotlight = _normalize_email(getattr(post.user, "email", "")) == HOME_PINNED_POST_EMAIL
        post.viewer_can_delete = bool(current_user and (current_user.id == post.user_id or _is_founders_admin(current_user)))
        post.viewer_can_edit = bool(current_user and current_user.id == post.user_id)
    _attach_post_reaction_metadata(posts, current_user=current_user)
    return posts


def _attach_post_reaction_metadata(posts, current_user=None):
    post_list = list(posts)
    if not post_list:
        return post_list

    reactions = list(PostReaction.objects.filter(post__in=post_list))
    counts_by_post_id = {}
    viewer_reactions_by_post_id = {}

    for reaction in reactions:
        counts = counts_by_post_id.setdefault(
            reaction.post_id,
            {
                PostReaction.ReactionType.THUMBS_UP: 0,
                PostReaction.ReactionType.THUMBS_DOWN: 0,
            },
        )
        counts[reaction.reaction] = counts.get(reaction.reaction, 0) + 1
        if current_user and reaction.user_id == current_user.id:
            viewer_reactions_by_post_id[reaction.post_id] = reaction.reaction

    for post in post_list:
        counts = counts_by_post_id.get(
            post.id,
            {
                PostReaction.ReactionType.THUMBS_UP: 0,
                PostReaction.ReactionType.THUMBS_DOWN: 0,
            },
        )
        viewer_reaction = viewer_reactions_by_post_id.get(post.id, "")
        post.likes_number = counts.get(PostReaction.ReactionType.THUMBS_UP, 0)
        post.dislikes_number = counts.get(PostReaction.ReactionType.THUMBS_DOWN, 0)
        post.viewer_post_reaction = viewer_reaction
        post.viewer_liked = viewer_reaction == PostReaction.ReactionType.THUMBS_UP
        post.viewer_disliked = viewer_reaction == PostReaction.ReactionType.THUMBS_DOWN

    return post_list


def _relative_time_label(value):
    if not value:
        return "New"

    delta = timesince(value)
    if not delta:
        return "Right Now"

    first_part = delta.split(",")[0].strip().lower()
    if first_part.startswith("0 "):
        return "Right Now"

    return f"{first_part} ago"


def _build_post_feed_title(post):
    explicit_title = " ".join((getattr(post, "title", "") or "").split())
    if explicit_title:
        return explicit_title

    raw_text = " ".join((post.content or "").split())
    if not raw_text:
        return post.get_post_type_display()
    sentence_break = raw_text.find(". ")
    title_source = raw_text if sentence_break == -1 else raw_text[:sentence_break + 1]
    return (title_source[:110].rstrip() + "…") if len(title_source) > 110 else title_source


def _render_post_title_html(title):
    return _render_post_content_segment_html(title or "")


def _post_type_display_label(post):
    if not post:
        return ""

    post_type = (getattr(post, "post_type", "") or "").strip()
    if post_type == Post.PostType.UPDATE and not Post.objects.filter(
        user=post.user,
    ).exclude(
        id=post.id,
    ).filter(
        Q(created_at__lt=post.created_at) | Q(created_at=post.created_at, id__lt=post.id),
    ).exists():
        return "Introduction"

    return post.get_post_type_display()


def _post_theme_class(post):
    theme_color = (getattr(post, "theme_color", "") or Post.ThemeColor.DEFAULT).strip()
    valid_theme_colors = {choice for choice, _label in Post.ThemeColor.choices}
    if theme_color not in valid_theme_colors:
        theme_color = Post.ThemeColor.DEFAULT
    return f"post-tone-{theme_color}"


def _profile_avatar_url(profile):
    if not profile:
        return ""
    image = getattr(profile, "profile_image", None)
    if not image:
        return ""
    return _safe_media_url(image)


def _user_avatar_url(user):
    if not user:
        return ""
    try:
        profile = getattr(user, "profile", None)
    except Profile.DoesNotExist:
        return ""
    return _profile_avatar_url(profile)


def _comment_avatar_url(comment):
    return _user_avatar_url(getattr(comment, "user", None))


def _build_comment_tree(comments, current_user=None, max_visual_depth=3):
    ordered_comments = sorted(
        comments,
        key=lambda item: (
            0 if getattr(item, "is_pinned", False) else 1,
            item.created_at,
        ),
    )
    comment_map = {}
    root_comments = []

    for comment in ordered_comments:
        comment.child_comments = []
        comment.author_name = _display_name(comment.user)
        comment.avatar_url = _comment_avatar_url(comment)
        comment.relative_created_at = _relative_time_label(comment.created_at)
        comment.can_edit = bool(current_user and current_user.id == comment.user_id)
        comment.can_delete = bool(current_user and (current_user.id == comment.user_id or current_user.id == comment.post.user_id))
        comment.can_pin = bool(current_user and current_user.id == comment.post.user_id)
        comment.is_edited = bool(getattr(comment, "edited_at", None))
        _comment_reaction_payload(comment, viewer=current_user)
        comment_map[comment.id] = comment

    for comment in ordered_comments:
        parent = comment_map.get(comment.parent_id)
        if parent and parent.post_id == comment.post_id:
            parent.child_comments.append(comment)
        else:
            root_comments.append(comment)

    def assign_depth(nodes, depth=0):
        for node in nodes:
            node.child_comments.sort(
                key=lambda item: (
                    0 if getattr(item, "is_pinned", False) else 1,
                    -item.created_at.timestamp(),
                ),
            )
            node.thread_depth = depth
            node.thread_indent_depth = min(depth, max_visual_depth)
            assign_depth(node.child_comments, depth + 1)

    assign_depth(root_comments)
    return root_comments


def _attach_post_comment_threads(posts, current_user=None):
    post_list = list(posts)
    if not post_list:
        return post_list

    all_comments = list(
        Comment.objects.filter(post__in=post_list)
        .select_related("user", "user__profile", "parent", "post")
        .prefetch_related("reactions")
        .order_by("created_at")
    )
    comments_by_post_id = {}
    for comment in all_comments:
        comments_by_post_id.setdefault(comment.post_id, []).append(comment)

    for post in post_list:
        post.comment_threads = _build_comment_tree(comments_by_post_id.get(post.id, []), current_user=current_user)

    return post_list


def _onboarded_user_queryset(*, exclude_user_id=None):
    users = User.objects.select_related("profile")
    if exclude_user_id:
        users = users.exclude(id=exclude_user_id)
    onboarded = []
    for user in users:
        if _is_profile_onboarded(getattr(user, "profile", None)):
            onboarded.append(user)
    return onboarded


def _create_post_notifications(post):
    author = post.user
    actor_name = _display_name(author)
    title = f"{actor_name} published a new post"
    body = (post.feed_title or post.title or post.get_post_type_display())[:180]
    target_url = reverse("Post Detail", args=[post.id])

    for recipient in _onboarded_user_queryset(exclude_user_id=author.id):
        if in_app_notification_enabled(recipient, Notification.NotificationType.NEW_POST):
            create_notification(
                recipient=recipient,
                actor=author,
                notification_type=Notification.NotificationType.NEW_POST,
                title=title,
                body=body,
                target_url=target_url,
            )


def _create_post_mention_notifications(post):
    author = post.user
    target_url = reverse("Post Detail", args=[post.id])
    for mention in post.mentions.select_related("mentioned_user"):
        recipient = mention.mentioned_user
        if recipient.id == author.id:
            continue
        if not in_app_notification_enabled(recipient, Notification.NotificationType.POST_MENTION):
            continue
        create_notification(
            recipient=recipient,
            actor=author,
            notification_type=Notification.NotificationType.POST_MENTION,
            title=f"{_display_name(author)} mentioned you in a post",
            body=(post.feed_title or post.title or "Open the post to see the mention.")[:180],
            target_url=target_url,
        )


def _send_post_alert_email(post):
    recipients = _post_alert_recipients()
    if resend is None or not RESEND_API_KEY or not recipients:
        logger.warning(
            "Skipped post alert email for post=%s because email alerts are not configured.",
            getattr(post, "id", ""),
        )
        return False

    resend.api_key = RESEND_API_KEY
    author = post.user
    author_name = _display_name(author)
    post_url = _absolute_site_url(reverse("Post Detail", args=[post.id]))
    created_at_label = timezone.localtime(post.created_at).strftime("%B %d, %Y at %I:%M %p")
    mentions = [f"@{mention.handle_text}" for mention in post.mentions.select_related("mentioned_user")]
    image_urls = []
    for image in post.gallery_images.all():
        image_url = _safe_media_url(getattr(image, "image", None))
        if image_url:
            image_urls.append(image_url)
    safe_content_html = escape(post.content or "").replace("\n", "<br>")
    mention_markup = (
        "".join(f"<li>{escape(handle)}</li>" for handle in mentions)
        if mentions
        else "<li>None</li>"
    )
    image_markup = (
        "".join(
            f'<li><a href="{escape(url)}" style="color: #2563eb; text-decoration: none;">{escape(url)}</a></li>'
            for url in image_urls
        )
        if image_urls
        else "<li>None</li>"
    )
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": list(recipients),
        "subject": f"New CoVise post: {post.title}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 640px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 24px; margin: 0 0 18px;">A new post was published</h1>'
            f"<p style=\"margin: 0 0 8px;\"><strong>Author:</strong> {escape(author_name)} ({escape(author.email)})</p>"
            f"<p style=\"margin: 0 0 8px;\"><strong>Post ID:</strong> {post.id}</p>"
            f"<p style=\"margin: 0 0 8px;\"><strong>Post type:</strong> {escape(post.get_post_type_display())}</p>"
            f"<p style=\"margin: 0 0 8px;\"><strong>Title:</strong> {escape(post.title)}</p>"
            f"<p style=\"margin: 0 0 8px;\"><strong>Created:</strong> {escape(created_at_label)}</p>"
            f"<p style=\"margin: 0 0 16px;\"><strong>Link:</strong> <a href=\"{escape(post_url)}\" style=\"color: #2563eb; text-decoration: none;\">{escape(post_url)}</a></p>"
            '<div style="margin: 0 0 16px; padding: 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;">'
            '<p style="margin: 0 0 8px;"><strong>Post content</strong></p>'
            f'<div style="white-space: normal; line-height: 1.6; color: #334155;">{safe_content_html}</div>'
            "</div>"
            '<p style="margin: 0 0 6px;"><strong>Mentions</strong></p>'
            f'<ul style="margin: 0 0 16px 20px; padding: 0; line-height: 1.6;">{mention_markup}</ul>'
            '<p style="margin: 0 0 6px;"><strong>Images</strong></p>'
            f'<p style="margin: 0 0 6px;">Count: {len(image_urls)}</p>'
            f'<ul style="margin: 0 0 8px 20px; padding: 0; line-height: 1.6;">{image_markup}</ul>'
            "</div>"
        ),
    }

    try:
        resend.Emails.send(payload)
        return True
    except Exception:
        logger.exception("Failed to send post alert email for post=%s", post.id)
        return False


def _mark_saved_posts(posts, user):
    post_list = list(posts)
    if not post_list:
        return post_list

    saved_post_ids = set(
        SavedPost.objects.filter(user=user, post__in=post_list).values_list("post_id", flat=True)
    )
    for post in post_list:
        post.is_saved = post.id in saved_post_ids
    return post_list


def _conversation_partner(conversation, current_user):
    for participant in conversation.participants.all():
        if participant.pk != current_user.pk:
            return participant
    return current_user


def _friend_queryset(user):
    accepted_requests = ConversationRequest.objects.filter(
        Q(requester=user) | Q(recipient=user),
        status=ConversationRequest.Status.ACCEPTED,
    )
    friend_ids = set()
    for request_item in accepted_requests:
        if request_item.requester_id == user.id:
            friend_ids.add(request_item.recipient_id)
        else:
            friend_ids.add(request_item.requester_id)
    return User.objects.filter(id__in=friend_ids).select_related("profile")


def _are_friends(user_a, user_b):
    if not user_a or not user_b or user_a == user_b:
        return False
    return ConversationRequest.objects.filter(
        Q(requester=user_a, recipient=user_b) | Q(requester=user_b, recipient=user_a),
        status=ConversationRequest.Status.ACCEPTED,
    ).exists()


def _normalize_contact_pair(user_a, user_b):
    if not user_a or not user_b or user_a == user_b:
        return None

    conversation = _get_or_create_private_conversation(user_a, user_b)
    pair_filter = Q(requester=user_a, recipient=user_b) | Q(requester=user_b, recipient=user_a)
    ConversationRequest.objects.filter(
        pair_filter,
        status=ConversationRequest.Status.ACCEPTED,
    ).update(conversation=conversation)
    ConversationRequest.objects.filter(
        pair_filter,
        status=ConversationRequest.Status.PENDING,
    ).update(
        status=ConversationRequest.Status.DECLINED,
        responded_at=timezone.now(),
    )
    return conversation


def _normalize_friend_contacts(user):
    if not user or not getattr(user, "is_authenticated", False):
        return

    accepted_requests = (
        ConversationRequest.objects.filter(
            Q(requester=user) | Q(recipient=user),
            status=ConversationRequest.Status.ACCEPTED,
        )
        .select_related("requester", "recipient", "conversation")
    )
    seen_pairs = set()
    for request_item in accepted_requests:
        other_user = request_item.recipient if request_item.requester_id == user.id else request_item.requester
        if not other_user or _is_blocked_pair(user, other_user):
            continue
        pair_key = tuple(sorted((str(user.id), str(other_user.id))))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        _normalize_contact_pair(user, other_user)


def _group_avatar_initials(group_name):
    parts = [part for part in str(group_name or "").split() if part]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    return "GR"


def _private_conversation_queryset(user_a, user_b):
    matched_users = [user.id for user in (user_a, user_b) if getattr(user, "id", None)]
    if len(matched_users) != 2 or matched_users[0] == matched_users[1]:
        return Conversation.objects.none()

    return (
        Conversation.objects.filter(
            conversation_type=Conversation.ConversationType.PRIVATE,
        )
        .annotate(
            participant_count=Count("participants", distinct=True),
            matched_participant_count=Count(
                "participants",
                filter=Q(participants__id__in=matched_users),
                distinct=True,
            ),
        )
        .filter(participant_count=2, matched_participant_count=2)
        .distinct()
    )


def _merge_private_conversations(user_a, user_b):
    if not user_a or not user_b or user_a == user_b:
        return None

    with transaction.atomic():
        ordered_conversation_ids = list(
            _private_conversation_queryset(user_a, user_b)
            .order_by("-last_message_at", "-updated_at", "-created_at")
            .values_list("id", flat=True)
        )
        if not ordered_conversation_ids:
            return None

        locked_conversations = {
            conversation.id: conversation
            for conversation in Conversation.objects.filter(id__in=ordered_conversation_ids).select_for_update()
        }
        conversations = [
            locked_conversations[conversation_id]
            for conversation_id in ordered_conversation_ids
            if conversation_id in locked_conversations
        ]
        if not conversations:
            return None

        canonical = conversations[0]
        duplicates = conversations[1:]
        if not duplicates:
            return canonical

        duplicate_ids = [conversation.id for conversation in duplicates]
        Message.objects.filter(conversation_id__in=duplicate_ids).update(conversation=canonical)
        ConversationRequest.objects.filter(conversation_id__in=duplicate_ids).update(conversation=canonical)

        duplicate_states = list(
            ConversationUserState.objects.filter(conversation_id__in=duplicate_ids).select_related("user")
        )
        for state in duplicate_states:
            canonical_state, created = ConversationUserState.objects.get_or_create(
                conversation=canonical,
                user=state.user,
                defaults={"mute_notifications": state.mute_notifications},
            )
            if not created and state.mute_notifications and not canonical_state.mute_notifications:
                canonical_state.mute_notifications = True
                canonical_state.save(update_fields=["mute_notifications", "updated_at"])
        ConversationUserState.objects.filter(conversation_id__in=duplicate_ids).delete()

        latest_message_at = (
            Message.objects.filter(conversation=canonical)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        if canonical.last_message_at != latest_message_at:
            canonical.last_message_at = latest_message_at
            canonical.save(update_fields=["last_message_at"])

        Conversation.objects.filter(id__in=duplicate_ids).delete()
        return canonical


def _normalize_visible_private_conversations(user):
    if not user or not getattr(user, "is_authenticated", False):
        return

    private_conversations = (
        Conversation.objects.filter(
            conversation_type=Conversation.ConversationType.PRIVATE,
        )
        .annotate(
            participant_count=Count("participants", distinct=True),
            includes_viewer=Count(
                "participants",
                filter=Q(participants=user),
                distinct=True,
            ),
        )
        .filter(participant_count=2, includes_viewer=1)
        .prefetch_related("participants")
        .distinct()
    )
    seen_pairs = set()
    for conversation in private_conversations:
        participants = list(conversation.participants.all())
        if len(participants) != 2:
            continue
        pair_key = tuple(sorted(str(participant.id) for participant in participants))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        _merge_private_conversations(participants[0], participants[1])


def _find_existing_private_conversation(user_a, user_b):
    return (
        _private_conversation_queryset(user_a, user_b)
        .order_by("-last_message_at", "-updated_at")
        .first()
    )


def _get_or_create_private_conversation(user_a, user_b):
    conversation = _merge_private_conversations(user_a, user_b)
    if conversation:
        return conversation

    with transaction.atomic():
        conversation = _find_existing_private_conversation(user_a, user_b)
        if conversation:
            return conversation

        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE,
            created_by=user_a,
        )
        conversation.participants.add(user_a, user_b)

    return _merge_private_conversations(user_a, user_b) or conversation


def _serialize_message(message, *, viewer=None, is_ephemeral=False):
    sender_name = _display_name(message.sender)
    attachment_url = _safe_media_url(getattr(message, "attachment_file", None))
    reaction_counts, viewer_reactions = _message_reaction_payload(message, viewer=viewer)
    return {
        "id": (
            str(message.id)
            if getattr(message, "id", None)
            else f"ephemeral-{int(message.created_at.timestamp() * 1000)}-{message.sender_id}"
        ),
        "sender_id": str(message.sender_id),
        "sender_name": sender_name,
        "text": message.body,
        "created_at": message.created_at.isoformat(),
        "message_type": getattr(message, "message_type", Message.MessageType.TEXT),
        "attachment_url": attachment_url,
        "attachment_name": getattr(message, "attachment_name", "") or "",
        "attachment_content_type": getattr(message, "attachment_content_type", "") or "",
        "attachment_size": getattr(message, "attachment_size", None),
        "receipt": message_receipt_state_for_viewer(message, viewer=viewer) if viewer else "sent",
        "is_ephemeral": is_ephemeral,
        "reaction_counts": reaction_counts,
        "viewer_reactions": viewer_reactions,
    }


def _messaging_error_response(message, *, code, status):
    return JsonResponse({"ok": False, "error": message, "code": code}, status=status)


def _serialize_conversation(conversation, current_user):
    is_group = conversation.conversation_type == Conversation.ConversationType.GROUP
    partner = _conversation_partner(conversation, current_user)
    partner_profile = getattr(partner, "profile", None) if not is_group else None
    messages = list(
        conversation.messages.select_related("sender").prefetch_related("receipts", "reactions").order_by("created_at")
    )
    last_message = messages[-1] if messages else None
    muted_state = next(
        (state for state in conversation.user_states.all() if state.user_id == current_user.id),
        None,
    ) if hasattr(conversation, "user_states") else None
    group_participants = []
    if is_group:
        for participant in conversation.participants.all():
            group_participants.append(
                    {
                        "id": str(participant.id),
                        "display_name": _display_name(participant),
                        "avatar_initials": participant.avatar_initials,
                        "avatar_url": _user_avatar_url(participant),
                    }
            )
    status = (
        f"{len(group_participants)} members"
        if is_group
        else _display_value(getattr(partner_profile, "current_role", None), "Private conversation")
    )
    skills_text = ""
    country_text = ""
    if not is_group and partner_profile:
        skills_text = _display_value(getattr(partner_profile, "skills", None), "")
        if skills_text:
            skills_text = ", ".join([part.strip() for part in skills_text.split(",") if part.strip()][:2])
        country_text = (
            _display_value(getattr(partner_profile, "country", None), "")
            or _display_value(getattr(partner_profile, "home_country", None), "")
            or _display_value(getattr(partner_profile, "custom_country", None), "")
        )
    preview = "Start the conversation"
    if last_message:
        if last_message.message_type == Message.MessageType.IMAGE:
            preview = last_message.body or "Sent an image"
        elif last_message.message_type == Message.MessageType.VOICE:
            preview = last_message.body or "Sent a voice message"
        elif last_message.message_type == Message.MessageType.FILE:
            preview = last_message.body or f"Shared {last_message.attachment_name or 'a file'}"
        else:
            preview = last_message.body
    shared_files = [
        {
            "id": str(message.id),
            "message_type": message.message_type,
            "name": message.attachment_name or "Attachment",
            "url": _serialize_message(message, viewer=current_user).get("attachment_url", ""),
            "created_at": message.created_at.isoformat(),
            "sender_name": _display_name(message.sender),
            "attachment_size": message.attachment_size,
        }
        for message in messages
        if getattr(message, "attachment_file", None)
    ]
    unread_count = sum(
        1
        for message in messages
        for receipt in message.receipts.all()
        if receipt.user_id == current_user.id and receipt.status == "delivered"
    )
    return {
        "id": str(conversation.id),
        "conversation_type": conversation.conversation_type,
        "partner_id": str(partner.id) if not is_group else "",
        "blocked_by_current_user": _has_user_blocked(current_user, partner) if not is_group else False,
        "name": conversation.group_name if is_group else _display_name(partner),
        "avatar": _group_avatar_initials(conversation.group_name) if is_group else partner.avatar_initials,
        "avatar_url": "" if is_group else _user_avatar_url(partner),
        "preview": preview,
        "time": _relative_time_label(last_message.created_at) if last_message else "New",
        "unread": unread_count,
        "online": False,
        "match": "Group conversation" if is_group else "Private conversation",
        "status": status,
        "skills": skills_text,
        "country": country_text,
        "matchedOn": conversation.created_at.strftime("%B %d, %Y"),
        "userType": "" if is_group else _display_value(getattr(partner_profile, "user_type", None), "CoVise member"),
        "industry": "" if is_group else _display_value(getattr(partner_profile, "industry", None), "Not added yet"),
        "stage": "" if is_group else _display_value(getattr(partner_profile, "stage", None), "Not added yet"),
        "mutual": 0,
        "group_members": group_participants,
        "pinned": (
            "Messages in this conversation are currently ephemeral and will not be saved."
            if conversation.recording_mode == Conversation.RecordingMode.EPHEMERAL
            else ""
        ),
        "recording_mode": conversation.recording_mode,
        "mute_notifications": bool(muted_state and muted_state.mute_notifications),
        "shared_files": shared_files,
        "messages": [_serialize_message(message, viewer=current_user) for message in messages],
    }


def _serialize_conversation_request(request_item, current_user):
    is_incoming = request_item.recipient_id == current_user.id
    other_user = request_item.requester if is_incoming else request_item.recipient
    other_profile = getattr(other_user, "profile", None)
    description = _display_value(getattr(other_profile, "one_liner", None), "Wants to start a private conversation.")
    country = _display_value(
        getattr(other_profile, "custom_country", None) or getattr(other_profile, "country", None),
        "",
    )
    if not description:
        description = "Wants to start a private conversation."
    return {
        "id": str(request_item.id),
        "name": _display_name(other_user),
        "country": country,
        "avatar": other_user.avatar_initials,
        "avatar_url": _user_avatar_url(other_user),
        "profile_url": reverse("Public Profile", args=[other_user.id]) if other_user else "",
        "description": description,
        "is_incoming": is_incoming,
        "status": request_item.status,
    }



def _load_boarding_flow():
    flow_path = Path(__file__).resolve().parent / "boarding.json"
    try:
        # Use utf-8-sig so a BOM in boarding.json does not break JSON parsing.
        with flow_path.open(encoding="utf-8-sig") as f:
            flow = json.load(f)
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.exception("Failed to load boarding.json: %s", exc)
        return None, "We are having trouble loading onboarding right now. Please try another time."

    if not isinstance(flow, dict) or not isinstance(flow.get("steps"), list):
        logger.error("Invalid boarding.json structure")
        return None, "We are having trouble loading onboarding right now. Please try another time."

    return flow, None


def _project_card_context(project):
    owner_name = project.founder_name or "CoVise Founder"
    if project.user and project.user.full_name:
        owner_name = project.user.full_name

    owner_initials = project.founder_initials or "CV"
    if project.user and getattr(project.user, "avatar_initials", ""):
        owner_initials = project.user.avatar_initials
    owner_avatar_url = _user_avatar_url(project.user) if project.user else ""

    filter_tokens = list(project.filter_tokens or [])
    if project.stage:
        filter_tokens.append(str(project.stage).strip().lower().replace(" ", "-"))

    positions_text = " ".join(project.positions_needed or []).lower()
    if "co-founder" in positions_text or "cofounder" in positions_text:
        filter_tokens.append("seeking-co-founder")
    if "investor" in positions_text:
        filter_tokens.append("seeking-investor")
    if "operator" in positions_text or "operations" in positions_text:
        filter_tokens.append("seeking-operator")

    deduped_filters = []
    for token in filter_tokens:
        normalized = str(token).strip().lower()
        if normalized and normalized not in deduped_filters:
            deduped_filters.append(normalized)

    return {
        "slug": project.slug,
        "owner_user_id": project.user_id,
        "code": project.code,
        "title": project.title,
        "founder_name": owner_name,
        "founder_initials": owner_initials,
        "founder_avatar_url": owner_avatar_url,
        "city": project.city,
        "country": project.country,
        "relative_time": f"{timesince(project.published_at)} ago" if project.published_at else "Recently added",
        "description": project.card_description or project.overview,
        "stage": project.stage,
        "sector": project.sector,
        "founder_commitment": project.founder_commitment,
        "capital_status": project.capital_status,
        "positions_needed": project.positions_needed[:3],
        "skills_needed": project.skills_needed[:3],
        "team_members_filled": project.team_members_filled,
        "team_size_target": project.team_size_target,
        "team_progress_percent": project.team_progress_percent,
        "alignment_score": project.alignment_score,
        "data_filters": " ".join(deduped_filters),
        "data_search": project.search_text or " ".join(
            bit for bit in [
                project.title,
                project.code,
                project.founder_name,
                project.city,
                project.country,
                project.sector,
                project.stage,
                project.founder_commitment,
                project.capital_status,
                " ".join(project.positions_needed or []),
                " ".join(project.skills_needed or []),
                " ".join(project.filter_tokens or []),
                project.slug,
            ] if bit
        ),
        "alignment_json": json.dumps(project.alignment_details or {"aspects": [], "summary": ""}),
    }

# Create your views here.
def landing(request):
    return render(request, 'landing.html')

@login_required
def home(request):
    if not request.user.is_authenticated:
        return HttpResponsePermanentRedirect(reverse('Landing Page'))
    profile = getattr(request.user, "profile", None)
    if not _is_profile_onboarded(profile):
        return redirect(f"{reverse('Onboarding')}?next={reverse('Home')}")
    if profile and not getattr(profile, "has_accepted_platform_agreement", False):
        return redirect(f"{reverse('Agreement')}?next={quote(reverse('Home'))}")

    blocked_ids = _blocked_user_ids(request.user)
    posts = _mark_saved_posts(
        Post.objects.select_related("user", "user__profile").prefetch_related("gallery_images", "mentions__mentioned_user").exclude(user_id__in=blocked_ids).order_by(
            Case(
                When(user__email__iexact=HOME_PINNED_POST_EMAIL, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            "-created_at",
        ),
        request.user,
    )
    _attach_post_feed_metadata(posts, current_user=request.user)

    full_name = (request.user.full_name or "").strip()
    first_name = full_name.split()[0] if full_name else "User"
    raw_skills = getattr(profile, "skills", None) if profile else []
    tags = set(raw_skills or [])
    sidebar_metrics = _home_sidebar_metrics(request.user)
    quick_requests = _home_quick_requests(request.user)
    response = render(request, 'home.html', {
        "posts": posts,
        "first_name": first_name,
        "tags": tags,
        "home_sidebar_metrics": sidebar_metrics,
        "home_quick_requests": quick_requests,
        "home_welcome_subtitle": _home_welcome_subtitle(sidebar_metrics),
        "home_filter_countries": sorted({post.feed_country for post in posts if getattr(post, "feed_country", "")}),
        "searchable_users": _searchable_users_for_home(request.user),
        "show_intro_post_notice": _requires_intro_post(profile),
    })
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@login_required
def post_detail(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("user", "user__profile").prefetch_related("gallery_images", "mentions__mentioned_user"),
        id=post_id,
    )
    if post.user_id in _blocked_user_ids(request.user):
        raise Http404("Post not available")
    _attach_post_feed_metadata([post], current_user=request.user)
    post.comment_threads = _build_comment_tree(
        Comment.objects.filter(post=post).select_related("user", "user__profile", "parent", "post").prefetch_related("reactions").order_by("created_at"),
        current_user=request.user,
    )
    post.is_saved = SavedPost.objects.filter(user=request.user, post=post).exists()
    response = render(request, "post_detail.html", {"post": post})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@login_required
def add_comment(request, post_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    post = Post.objects.filter(id=post_id).first()
    if not post:
        return JsonResponse({"error": "Post not found"}, status=404)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request payload"}, status=400)
    content = str(payload.get("content", "")).strip()
    if not content:
        return JsonResponse({"error": "Comment cannot be empty"}, status=400)

    parent_id = payload.get("parent_id")
    parent_comment = None
    if parent_id not in (None, "", "null"):
        parent_comment = Comment.objects.filter(id=parent_id, post=post).select_related("user").first()
        if not parent_comment:
            return JsonResponse({"error": "Reply target not found"}, status=400)

    comment = Comment.objects.create(
        user=request.user,
        post=post,
        parent=parent_comment,
        content=content,
    )
    _comment_reaction_payload(comment, viewer=request.user)
    post.comments_number = post.comments.count()
    post.save(update_fields=["comments_number"])

    return JsonResponse({
        "comment": {
            "id": comment.id,
            "post_id": post.id,
            "user_id": request.user.id,
            "author": _display_name(request.user),
            "avatar_initials": request.user.avatar_initials,
            "content": comment.content,
            "created_at": "just now",
            "parent_id": parent_comment.id if parent_comment else None,
            "is_pinned": False,
            "can_edit": True,
            "can_delete": True,
            "can_pin": request.user.id == post.user_id,
            "thumbs_up": 0,
            "fire": 0,
            "viewer_reactions": [],
        },
        "comments_count": post.comments_number,
    })


@login_required
@require_POST
def toggle_saved_post(request, post_id):
    post = Post.objects.filter(id=post_id).first()
    if not post:
        return JsonResponse({"error": "Post not found"}, status=404)

    saved_post = SavedPost.objects.filter(user=request.user, post=post).first()
    if saved_post:
        saved_post.delete()
        return JsonResponse({"ok": True, "saved": False})

    SavedPost.objects.create(user=request.user, post=post)
    return JsonResponse({"ok": True, "saved": True})


@login_required
@require_POST
def toggle_post_reaction(request, post_id, reaction):
    reaction_type = POST_REACTION_ACTION_MAP.get(reaction)
    if not reaction_type:
        return JsonResponse({"ok": False, "error": "Invalid reaction."}, status=400)

    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if post.user_id in _blocked_user_ids(request.user):
        return JsonResponse({"ok": False, "error": "Post not available."}, status=404)

    existing_reaction = PostReaction.objects.filter(user=request.user, post=post).first()
    if existing_reaction and existing_reaction.reaction == reaction_type:
        existing_reaction.delete()
        viewer_reaction = ""
    else:
        PostReaction.objects.update_or_create(
            user=request.user,
            post=post,
            defaults={"reaction": reaction_type},
        )
        viewer_reaction = reaction_type

    reaction_totals = PostReaction.objects.filter(post=post).aggregate(
        thumbs_up=Count("id", filter=Q(reaction=PostReaction.ReactionType.THUMBS_UP)),
        thumbs_down=Count("id", filter=Q(reaction=PostReaction.ReactionType.THUMBS_DOWN)),
    )
    likes_number = reaction_totals["thumbs_up"] or 0
    dislikes_number = reaction_totals["thumbs_down"] or 0
    if post.likes_number != likes_number:
        post.likes_number = likes_number
        post.save(update_fields=["likes_number"])

    return JsonResponse(
        {
            "ok": True,
            "reaction_counts": {
                "thumbs_up": likes_number,
                "thumbs_down": dislikes_number,
            },
            "user_reaction": viewer_reaction,
        }
    )


@login_required
@require_POST
def delete_post(request, post_id):
    post = get_object_or_404(Post.objects.prefetch_related("gallery_images"), id=post_id)
    if request.user.id != post.user_id and not _is_founders_admin(request.user):
        return JsonResponse({"ok": False, "error": "You cannot delete this post."}, status=403)

    if post.image:
        post.image.delete(save=False)
    _delete_file_field_for_queryset(post.gallery_images.all(), "image")
    post.delete()

    redirect_url = _safe_redirect_url(request, reverse("Home"))
    return redirect(redirect_url)


def notify(user_email, who, reason):
    if resend is None or not RESEND_API_KEY:
        logger.warning(
            "Skipped waitlist failure alert for %s because email alerts are not configured.",
            user_email,
        )
        return
    timestamp=timezone.now().isoformat()
    if reason=="MESSAGE": details = "You have a new message from {}".format(who)
    elif reason=="CONNECTION_REQUEST": details = "You have a new connection request from {}".format(who)
    else: details = "You have a new notification from {}".format(who)

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [user_email],
        "subject": f"NOTIFICATION: You have a new notification from {who}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">Notification</h1>'
            f"<p style=\"margin: 0 0 10px;\"><strong>User email:</strong> {user_email}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Date:</strong> {timestamp}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Reason:</strong> {reason}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Details:</strong> {details}</p>"
            f"<p style=\"margin: 0 0 10px;\">Log in to your CoVise account to view this notification.</p>"
            "</div>"
        ),
    }

    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception("Failed to send notification email to %s", user_email)


def _send_user_report_email(reporter, reported_user, reason):
    if resend is None or not RESEND_API_KEY or not REPORT_ALERT_EMAIL:
        logger.warning(
            "Skipped user report email for reporter=%s reported=%s because email alerts are not configured.",
            getattr(reporter, "email", ""),
            getattr(reported_user, "email", ""),
        )
        return False

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    reporter_name = _display_name(reporter)
    reported_name = _display_name(reported_user)
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [REPORT_ALERT_EMAIL],
        "subject": f"User {reporter_name} reports user {reported_name}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">User report received</h1>'
            f"<p style=\"margin: 0 0 10px;\"><strong>Reporter:</strong> {reporter_name} ({reporter.email})</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Reported user:</strong> {reported_name} ({reported_user.email})</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Date:</strong> {timestamp}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Reason:</strong> {reason}</p>"
            "</div>"
        ),
    }

    try:
        resend.Emails.send(payload)
        return True
    except Exception:
        logger.exception(
            "Failed to send user report email for reporter=%s reported=%s",
            reporter.email,
            reported_user.email,
        )
        return False


def _message_preview_text(message):
    if message.message_type == Message.MessageType.IMAGE:
        return message.body or "Sent an image"
    if message.message_type == Message.MessageType.VOICE:
        return message.body or "Sent a voice message"
    if message.message_type == Message.MessageType.FILE:
        return message.body or f"Shared {message.attachment_name or 'a file'}"
    return message.body or ""


def _send_message_report_email(reporter, reported_user, message, reason):
    if resend is None or not RESEND_API_KEY or not REPORT_ALERT_EMAIL:
        logger.warning(
            "Skipped message report email for reporter=%s reported=%s because email alerts are not configured.",
            getattr(reporter, "email", ""),
            getattr(reported_user, "email", ""),
        )
        return False

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    reporter_name = _display_name(reporter)
    reported_name = _display_name(reported_user)
    message_preview = _message_preview_text(message)
    payload = {
        "from": "CoVise Alerts <founders@covise.net>",
        "to": [REPORT_ALERT_EMAIL],
        "subject": f"User {reporter_name} reports a message from {reported_name}",
        "html": (
            '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #111827;">'
            '<h1 style="font-size: 22px; margin: 0 0 16px;">Message report received</h1>'
            f"<p style=\"margin: 0 0 10px;\"><strong>Reporter:</strong> {reporter_name} ({reporter.email})</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Reported user:</strong> {reported_name} ({reported_user.email})</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Conversation:</strong> {message.conversation_id}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Message ID:</strong> {message.id}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Date:</strong> {timestamp}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Reason:</strong> {reason}</p>"
            f"<p style=\"margin: 0 0 10px;\"><strong>Message preview:</strong> {message_preview or 'Empty message'}</p>"
            "</div>"
        ),
    }

    try:
        resend.Emails.send(payload)
        return True
    except Exception:
        logger.exception(
            "Failed to send message report email for reporter=%s reported=%s message=%s",
            reporter.email,
            reported_user.email,
            message.id,
        )
        return False


def _build_post_editor_context(user, *, form_data=None, error_message="", edit_post=None):
    full_name = (user.full_name or "").strip()
    first_name = full_name.split()[0] if full_name else "..."
    profile = getattr(user, "profile", None)
    onboarding_answers = getattr(profile, "onboarding_answers", {}) or {}
    waitlist_snapshot = getattr(profile, "waitlist_snapshot", {}) or {}

    def _line_value(value, placeholder):
        text = str(value or "").strip()
        return text if text else placeholder

    def _first_nonempty(*values):
        for value in values:
            text = _display_value(value, "").strip()
            if text:
                return text
        return ""

    def _first_skill_text(*values, limit=3):
        for value in values:
            labels = _top_skill_labels(value, limit=limit)
            if labels:
                return ", ".join(labels)
        return ""

    def _placeholder(label):
        return f"[{label}]"

    def _seed_value(*values, placeholder="[..]"):
        return _first_nonempty(*values) or placeholder

    def _join_nonempty(*values, separator=" / "):
        parts = []
        for value in values:
            text = str(value or "").strip()
            if text and not (text.startswith("[") and text.endswith("]")):
                parts.append(text)
        return separator.join(parts)

    def _lower_lead(value):
        text = str(value or "").strip()
        if not text:
            return "[..]"
        if text.startswith("[") and text.endswith("]"):
            inner = text[1:-1].strip()
            if not inner:
                return text
            return f"[{inner[:1].lower() + inner[1:]}]"
        return text[:1].lower() + text[1:]

    def _build_intro_template():
        based_in_parts = [
            str(getattr(profile, "city", "") or "").strip(),
            str(getattr(profile, "country", "") or "").strip(),
        ]
        based_in = ", ".join(part for part in based_in_parts if part)
        if not based_in:
            based_in = (
                _profile_country_label(profile)
                or _display_value(onboarding_answers.get("home_country"), "")
                or _display_value(onboarding_answers.get("target_gcc_market"), "")
            )
        background = str(getattr(profile, "bio", "") or "").strip()
        looking_for = _display_value(getattr(profile, "looking_for_type", None))
        top_skills = _top_skill_labels(getattr(profile, "skills", None), limit=2)
        intro_title_name = full_name or first_name or "me"
        return {
            "key": "introduction",
            "label": "Introduction",
            "description": "Introduce yourself before joining the conversation.",
            "post_type": Post.PostType.UPDATE,
            "title": f"Hey this is {intro_title_name}",
            "content": "\n".join(
                [
                    "Based in:",
                    _line_value(based_in, "[City, Country]"),
                    "",
                    "Background:",
                    _line_value(background, "[2 sentences — what you've done, what you know]"),
                    "",
                    "What I'm building or looking to build:",
                    "[Your venture or area of interest]",
                    "",
                    "What I'm looking for:",
                    _line_value(looking_for, "[Co-founder / Partners / Advice / Connections]"),
                    "",
                    "One thing I can help others with:",
                    _line_value(", ".join(top_skills), "[Your strongest skill or area of expertise]"),
                    "",
                    "Happy to connect with the network.",
                ]
            ),
        }

    location_value = _seed_value(
        ", ".join(
            part for part in [
                str(getattr(profile, "city", "") or "").strip(),
                str(getattr(profile, "country", "") or "").strip(),
            ] if part
        ),
        _profile_country_label(profile),
        onboarding_answers.get("home_country"),
        onboarding_answers.get("target_gcc_market"),
        placeholder=_placeholder("Location"),
    )
    venture_value = _seed_value(
        getattr(profile, "one_liner", None),
        onboarding_answers.get("one_liner"),
        waitlist_snapshot.get("venture_summary"),
        getattr(profile, "foreign_one_liner", None),
        placeholder=_placeholder("What I'm building"),
    )
    stage_value = _seed_value(
        getattr(profile, "stage", None),
        onboarding_answers.get("stage"),
        getattr(profile, "foreign_stage", None),
        getattr(profile, "program_stage_focus", None),
        getattr(profile, "investment_stage", None),
        placeholder=_placeholder("Stage"),
    )
    industry_value = _seed_value(
        getattr(profile, "industry", None),
        onboarding_answers.get("industry"),
        getattr(profile, "foreign_industry", None),
        getattr(profile, "target_market", None),
        placeholder=_placeholder("Industry"),
    )
    partner_value = _seed_value(
        getattr(profile, "looking_for_skills", None),
        onboarding_answers.get("looking_for_skills"),
        getattr(profile, "looking_for_type", None),
        onboarding_answers.get("looking_for_type"),
        getattr(profile, "cofounders_needed", None),
        onboarding_answers.get("cofounders_needed"),
        placeholder=_placeholder("Who I'm looking for"),
    )
    skills_value = _first_skill_text(
        getattr(profile, "skills", None),
        onboarding_answers.get("skills"),
        getattr(profile, "looking_for_skills", None),
        onboarding_answers.get("looking_for_skills"),
        limit=3,
    )
    bring_value = _seed_value(
        getattr(profile, "bio", ""),
        _join_nonempty(
            _first_nonempty(getattr(profile, "current_role", None), onboarding_answers.get("current_role")),
            skills_value,
            separator=" | ",
        ),
        placeholder=_placeholder("What I bring"),
    )
    commitment_value = _seed_value(
        getattr(profile, "cofounder_commitment", None),
        onboarding_answers.get("cofounder_commitment"),
        getattr(profile, "availability", None),
        onboarding_answers.get("availability"),
        getattr(profile, "commitment_level", None),
        onboarding_answers.get("commitment_level"),
        placeholder=_placeholder("Commitment expected"),
    )
    advice_context_value = _seed_value(
        getattr(profile, "bio", ""),
        _join_nonempty(venture_value, industry_value, stage_value, location_value),
        placeholder=_placeholder("Context"),
    )
    advice_challenge_value = _seed_value(
        getattr(profile, "local_partner_need", None),
        onboarding_answers.get("local_partner_need"),
        placeholder=_placeholder("The challenge I'm facing"),
    )
    advice_tried_value = _seed_value(
        getattr(profile, "execution_history", None),
        onboarding_answers.get("execution_history"),
        getattr(profile, "founder_timeline", None),
        onboarding_answers.get("founder_timeline"),
        getattr(profile, "specialist_timeline", None),
        onboarding_answers.get("specialist_timeline"),
        getattr(profile, "foreign_timeline", None),
        onboarding_answers.get("foreign_timeline"),
        getattr(profile, "investor_timeline", None),
        onboarding_answers.get("investor_timeline"),
        placeholder=_placeholder("What I've already tried"),
    )
    guidance_value = _seed_value(
        getattr(profile, "looking_for_type", None),
        onboarding_answers.get("looking_for_type"),
        getattr(profile, "investor_looking_for", None),
        onboarding_answers.get("investor_looking_for"),
        getattr(profile, "incubator_looking_for", None),
        onboarding_answers.get("incubator_looking_for"),
        placeholder=_placeholder("What I'm looking for"),
    )
    update_next_value = _seed_value(
        getattr(profile, "founder_timeline", None),
        onboarding_answers.get("founder_timeline"),
        getattr(profile, "specialist_timeline", None),
        onboarding_answers.get("specialist_timeline"),
        getattr(profile, "foreign_timeline", None),
        onboarding_answers.get("foreign_timeline"),
        getattr(profile, "investor_timeline", None),
        onboarding_answers.get("investor_timeline"),
        placeholder=_placeholder("What's next"),
    )
    update_building_line = _seed_value(
        _join_nonempty(industry_value, stage_value, location_value),
        placeholder=_placeholder("Industry / Stage / Location"),
    )

    template_payloads = {
        "introduction": _build_intro_template(),
        "find_cofounder": {
            "key": "find_cofounder",
            "label": "Find a Co-Founder",
            "description": "Pitch your venture and the partner you need.",
            "post_type": Post.PostType.IDEA,
            "title": f"Looking for {_lower_lead(partner_value)} to build {_lower_lead(venture_value)}",
            "content": "\n".join(
                [
                    "What I'm building:",
                    venture_value,
                    "",
                    "The problem I'm solving:",
                    advice_challenge_value,
                    "",
                    "Stage:",
                    stage_value,
                    "",
                    "Who I'm looking for:",
                    "[Technical / Business / Industry expert — be specific]",
                    "",
                    "What I bring:",
                    bring_value,
                    "",
                    "Commitment expected:",
                    commitment_value,
                    "",
                    "Location:",
                    location_value,
                    "",
                    "If this resonates, reply below or request to connect.",
                ]
            ),
        },
        "ask_advice": {
            "key": "ask_advice",
            "label": "Ask for Advice",
            "description": "Ask a sharp question and show your context.",
            "post_type": Post.PostType.ASK,
            "title": "Seeking Advice",
            "content": "\n".join(
                [
                    "Context:",
                    "[Brief background on your venture or situation]",
                    "",
                    "The challenge I'm facing:",
                    "[Be specific — vague questions get vague answers]",
                    "",
                    "What I've already tried:",
                    "[Shows you've done the work before asking]",
                    "",
                    "What I'm looking for:",
                    "[Specific guidance / Introductions / Lived experience]",
                    "",
                    "Any input appreciated.",
                ]
            ),
        },
        "share_update": {
            "key": "share_update",
            "label": "Share an Update",
            "description": "Share progress, traction, or a milestone.",
            "post_type": Post.PostType.UPDATE,
            "title": "Venture Update",
            "content": "\n".join(
                [
                    "Company:",
                    "[Name]",
                    "",
                    "What we shipped / achieved:",
                    "[Specific milestone — keep it real]",
                    "",
                    "What's next:",
                    "[Your immediate focus]",
                    "",
                    "Where we need help:",
                    "[Optional — be specific if you want input]",
                    "",
                    "Building in [industry] · [Stage] · [Location]",
                ]
            ),
        },
        "write_freely": {
            "key": "write_freely",
            "label": "Write Freely",
            "description": "Start with a blank draft and make it your own.",
            "post_type": Post.PostType.UPDATE,
            "title": "",
            "content": "",
        },
    }
    template_payloads["find_cofounder"]["title"] = (
        f"Looking for {_lower_lead(partner_value)} to build {_lower_lead(venture_value)}"
    )
    template_payloads["find_cofounder"]["content"] = "\n".join(
        [
            "What I'm building:",
            venture_value,
            "",
            "The problem I'm solving:",
            advice_challenge_value,
            "",
            "Stage:",
            stage_value,
            "",
            "Who I'm looking for:",
            partner_value,
            "",
            "What I bring:",
            bring_value,
            "",
            "Commitment expected:",
            commitment_value,
            "",
            "Location:",
            location_value,
            "",
            "If this resonates, reply below or request to connect.",
        ]
    )
    template_payloads["ask_advice"]["title"] = (
        f"Need advice on {_lower_lead(_seed_value(advice_challenge_value, venture_value, industry_value, placeholder=_placeholder('The challenge I need advice on')))}"
    )
    template_payloads["ask_advice"]["content"] = "\n".join(
        [
            "Context:",
            advice_context_value,
            "",
            "The challenge I'm facing:",
            advice_challenge_value,
            "",
            "What I've already tried:",
            advice_tried_value,
            "",
            "What I'm looking for:",
            guidance_value,
            "",
            "Any input appreciated.",
        ]
    )
    template_payloads["share_update"]["title"] = f"Update on {venture_value}"
    template_payloads["share_update"]["content"] = "\n".join(
        [
            "Company:",
            venture_value,
            "",
            "What we shipped / achieved:",
            _placeholder("What we shipped / achieved"),
            "",
            "What's next:",
            update_next_value,
            "",
            "Where we need help:",
            guidance_value,
            "",
            f"Building in {update_building_line}",
        ]
    )
    template_cards = [
        {
            "key": "find_cofounder",
            "label": "Find a Co-Founder",
            "description": "Populate the editor with a venture and partner search template.",
        },
        {
            "key": "ask_advice",
            "label": "Ask for Advice",
            "description": "Structure a focused ask with context and what you've tried.",
        },
        {
            "key": "share_update",
            "label": "Share an Update",
            "description": "Turn your latest momentum into a clear progress post.",
        },
        {
            "key": "write_freely",
            "label": "Write Freely",
            "description": "Start from a blank post and choose your own format.",
        },
    ]
    is_first_post = False if edit_post else not Post.objects.filter(user=user).exists()
    intro_template = template_payloads["introduction"]
    initial_template_key = ""

    if edit_post:
        default_form_data = {
            "title": edit_post.title or "",
            "post_type": edit_post.post_type or Post.PostType.UPDATE,
            "content": edit_post.content or "",
            "quote_content": edit_post.quote_content or "",
            "quote_color": edit_post.quote_color or "",
        }
    else:
        default_form_data = {
            "title": "",
            "post_type": intro_template["post_type"] if is_first_post else Post.PostType.UPDATE,
            "content": "",
            "quote_content": "",
            "quote_color": "",
        }

    if form_data:
        default_form_data.update(form_data)

    context = {
        "first_name": first_name,
        "is_first_post": is_first_post,
        "is_editing": bool(edit_post),
        "edit_post": edit_post,
        "post_page_title": "Edit Post" if edit_post else "Create Post",
        "post_kicker": "Edit Post" if edit_post else "Create Post",
        "post_form_action": reverse("Edit Post", args=[edit_post.id]) if edit_post else reverse("Create Post"),
        "post_submit_label": "Save Changes" if edit_post else "Post to network",
        "post_back_url": reverse("Post Detail", args=[edit_post.id]) if edit_post else reverse("Home"),
        "post_back_label": "Back to post" if edit_post else "Back to feed",
        "initial_template_key": initial_template_key,
        "post_type_choices": Post.PostType.choices,
        "template_cards": template_cards,
        "template_payloads": template_payloads,
        "form_data": default_form_data,
        "error_message": error_message,
    }
    return context


def _render_post_editor(request, context, *, status=200):
    response = render(request, "create_post.html", context, status=status)
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


def _save_post_from_editor(request, *, post=None):
    context = _build_post_editor_context(request.user, edit_post=post)

    if request.method != "POST":
        return _render_post_editor(request, context)

    title = request.POST.get("title", "").strip()
    post_type = request.POST.get("post_type", Post.PostType.UPDATE).strip()
    content = request.POST.get("content", "").strip()
    quote_content = request.POST.get("quote_content", "").strip()
    raw_quote_color = request.POST.get("quote_color", "").strip()
    quote_color = raw_quote_color if re.match(r'^#[0-9a-fA-F]{3,6}$', raw_quote_color) else ""
    uploaded_images = [image for image in request.FILES.getlist("images") if image]
    if not uploaded_images:
        legacy_image = request.FILES.get("image")
        if legacy_image:
            uploaded_images = [legacy_image]

    context["form_data"] = {
        "title": title,
        "post_type": post_type,
        "content": content,
        "quote_content": quote_content,
        "quote_color": quote_color,
    }

    valid_post_types = {choice for choice, _label in Post.PostType.choices}
    if not title or not content:
        context["error_message"] = "Title and post content are required."
        return _render_post_editor(request, context, status=400)

    if len(uploaded_images) > 6:
        context["error_message"] = "You can upload up to 6 images per post."
        return _render_post_editor(request, context, status=400)

    if post_type not in valid_post_types:
        context["error_message"] = "Select a valid post type."
        return _render_post_editor(request, context, status=400)

    if context["is_first_post"]:
        post_type = Post.PostType.UPDATE
        context["form_data"]["post_type"] = post_type

    with transaction.atomic():
        if post is None:
            post = Post.objects.create(
                user=request.user,
                title=title,
                post_type=post_type,
                theme_color=Post.ThemeColor.DEFAULT,
                content=content,
                quote_content=quote_content,
                quote_color=quote_color,
            )
        else:
            post.title = title
            post.post_type = post_type
            post.content = content
            post.quote_content = quote_content
            post.quote_color = quote_color
            post.save(update_fields=["title", "post_type", "content", "quote_content", "quote_color"])

        if uploaded_images:
            post.gallery_images.all().delete()
            if getattr(post, "image", None):
                post.image.delete(save=False)
                post.image = None
                post.save(update_fields=["image"])
            for index, image_file in enumerate(uploaded_images[:6]):
                PostImage.objects.create(
                    post=post,
                    image=image_file,
                    sort_order=index,
                )

        PostMention.objects.filter(post=post).delete()
        mention_matches = _resolve_post_mentions(content, exclude_user_id=request.user.id)
        for raw_handle, mentioned_user in mention_matches:
            PostMention.objects.get_or_create(
                post=post,
                mentioned_user=mentioned_user,
                handle_text=raw_handle,
            )
    _attach_post_feed_metadata([post], current_user=request.user)
    profile = getattr(request.user, "profile", None)
    if profile and getattr(profile, "requires_intro_post", False):
        profile.requires_intro_post = False
        profile.save(update_fields=["requires_intro_post"])
    if context["is_editing"]:
        return redirect("Post Detail", post_id=post.id)
    _create_post_notifications(post)
    _create_post_mention_notifications(post)
    _send_post_alert_email(post)
    return redirect("Post Detail", post_id=post.id)


@login_required
def create_post(request):
    return _save_post_from_editor(request)


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post.objects.prefetch_related("gallery_images"), id=post_id)
    if post.user_id != request.user.id:
        return JsonResponse({"error": "Forbidden"}, status=403)
    return _save_post_from_editor(request, post=post)

def _load_messages_page_state(user):
    try:
        _normalize_visible_private_conversations(user)
        _normalize_friend_contacts(user)
    except Exception as exc:
        logger.exception("Messages page normalization failed for user=%s", user.id)
        send_messaging_failure_alert(
            action="load_messages_page",
            reason="normalization_failed",
            actor=user,
            details={"exception": str(exc)},
        )

    conversations = list(
        Conversation.objects.filter(participants=user)
        .prefetch_related("participants__profile", "messages__sender", "messages__reactions", "messages__receipts", "user_states")
        .order_by("-last_message_at", "-updated_at")
        .distinct()
    )
    serialized_conversations = []
    for conversation in conversations:
        try:
            serialized_conversations.append(_serialize_conversation(conversation, user))
        except Exception as exc:
            send_messaging_failure_alert(
                action="load_conversation",
                reason="serialization_failed",
                actor=user,
                conversation=conversation,
                details={"exception": str(exc)},
            )

    try:
        friend_options = [
            {
                "id": str(friend.id),
                "display_name": _display_name(friend),
                "avatar_initials": friend.avatar_initials,
                "avatar_url": _user_avatar_url(friend),
            }
            for friend in _friend_queryset(user)
            if not _has_user_blocked(user, friend)
        ]
    except Exception as exc:
        logger.exception("Messages page friend options failed for user=%s", user.id)
        send_messaging_failure_alert(
            action="load_messages_page",
            reason="friend_options_failed",
            actor=user,
            details={"exception": str(exc)},
        )
        friend_options = []

    return {
        "conversation_data": serialized_conversations,
        "friend_options": friend_options,
    }


def _resolve_messages_active_conversation_id(requested_conversation_id, serialized_conversations):
    if requested_conversation_id and any(item["id"] == requested_conversation_id for item in serialized_conversations):
        return requested_conversation_id
    if serialized_conversations:
        return serialized_conversations[0]["id"]
    return ""


def _messages_error_message(error_code):
    if error_code == "conversation_unavailable":
        return "We couldn't open this conversation right now. Please try again."
    return error_code


@login_required
def messages(request):
    state = _load_messages_page_state(request.user)
    requested_conversation_id = request.GET.get("conversation", "").strip()
    active_conversation_id = _resolve_messages_active_conversation_id(
        requested_conversation_id,
        state["conversation_data"],
    )
    message_error = _messages_error_message(request.GET.get("error", "").strip())

    return render(
        request,
        'messages.html',
        {
            "conversation_data": state["conversation_data"],
            "friend_options": state["friend_options"],
            "active_conversation_id": active_conversation_id,
            "message_error": message_error,
        },
    )


@login_required
def messages_state(request):
    state = _load_messages_page_state(request.user)
    requested_conversation_id = request.GET.get("conversation", "").strip()
    active_conversation_id = _resolve_messages_active_conversation_id(
        requested_conversation_id,
        state["conversation_data"],
    )
    return JsonResponse(
        {
            "ok": True,
            "conversation_data": state["conversation_data"],
            "friend_options": state["friend_options"],
            "active_conversation_id": active_conversation_id,
        }
    )


@login_required
def requests_page(request):
    conversation_requests = list(
        ConversationRequest.objects.filter(Q(requester=request.user) | Q(recipient=request.user))
        .select_related("requester__profile", "recipient__profile")
        .order_by(
            Case(
                When(recipient=request.user, status=ConversationRequest.Status.PENDING, then=0),
                When(requester=request.user, status=ConversationRequest.Status.PENDING, then=1),
                default=2,
                output_field=IntegerField(),
            ),
            "-created_at",
        )
    )
    conversation_requests = [
        item for item in conversation_requests if not _is_blocked_pair(item.requester, item.recipient)
    ]
    serialized = [_serialize_conversation_request(item, request.user) for item in conversation_requests]
    return render(request, "requests.html", {"conversation_requests": serialized})


@login_required
@require_POST
def start_private_conversation(request, user_id):
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        raise Http404("User not found")
    if target_user == request.user:
        return redirect("Messages")
    if _is_blocked_pair(request.user, target_user):
        return redirect(f"{reverse('Public Profile', args=[target_user.id])}?blocked_message=1")
    if not _can_view_profile(request.user, target_user):
        raise Http404("Profile not available")

    redirect_url = _safe_redirect_url(request, reverse("Public Profile", args=[target_user.id]))
    outgoing_pending_request = (
        ConversationRequest.objects.filter(
            requester=request.user,
            recipient=target_user,
            status=ConversationRequest.Status.PENDING,
        )
        .order_by("-created_at")
        .first()
    )
    if outgoing_pending_request:
        outgoing_pending_request.delete()
        return redirect(redirect_url)

    existing_request = (
        ConversationRequest.objects.filter(
            Q(requester=request.user, recipient=target_user) | Q(requester=target_user, recipient=request.user),
            status=ConversationRequest.Status.PENDING,
        )
        .distinct()
        .first()
    )
    if existing_request:
        return redirect("Requests")

    try:
        existing_conversation = _merge_private_conversations(request.user, target_user)
    except Exception as exc:
        logger.exception(
            "Failed to merge private conversations sender=%s target=%s",
            request.user.id,
            target_user.id,
        )
        send_messaging_failure_alert(
            action="start_private_conversation",
            reason="merge_failed",
            actor=request.user,
            target_user=target_user,
            details={"exception": str(exc)},
        )
        existing_conversation = None
    if existing_conversation:
        return redirect(f"{reverse('Messages')}?conversation={existing_conversation.id}")

    if _are_friends(request.user, target_user):
        try:
            conversation = _normalize_contact_pair(request.user, target_user)
        except Exception as exc:
            logger.exception(
                "Failed to normalize private conversation sender=%s target=%s",
                request.user.id,
                target_user.id,
            )
            send_messaging_failure_alert(
                action="start_private_conversation",
                reason="normalize_failed",
                actor=request.user,
                target_user=target_user,
                details={"exception": str(exc)},
            )
            return redirect(f"{reverse('Messages')}?error=conversation_unavailable")
        return redirect(f"{reverse('Messages')}?conversation={conversation.id}")

    try:
        ConversationRequest.objects.create(
            requester=request.user,
            recipient=target_user,
        )
    except Exception as exc:
        logger.exception(
            "Failed to create private conversation request sender=%s target=%s",
            request.user.id,
            target_user.id,
        )
        send_messaging_failure_alert(
            action="start_private_conversation",
            reason="request_create_failed",
            actor=request.user,
            target_user=target_user,
            details={"exception": str(exc)},
        )
        return redirect(f"{reverse('Public Profile', args=[target_user.id])}?request_error=1")

    try:
        dispatch_notification(
            recipient=target_user,
            actor=request.user,
            notification_type=Notification.NotificationType.CONVERSATION_REQUEST,
            title=f"{_display_name(request.user)} wants to start a private chat",
            body="Open Messages to review the request and decide whether to accept it.",
            target_url=reverse("Messages"),
        )
    except Exception as exc:
        logger.exception(
            "Failed to dispatch private conversation request notification sender=%s target=%s",
            request.user.id,
            target_user.id,
        )
        send_messaging_failure_alert(
            action="start_private_conversation",
            reason="request_notification_failed",
            actor=request.user,
            target_user=target_user,
            details={"exception": str(exc)},
        )
    return redirect("Requests")


@login_required
@require_POST
def create_group_conversation(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _messaging_error_response(
            "We could not read that group request. Please try again.",
            code="malformed_payload",
            status=400,
        )

    group_name = str(payload.get("group_name", "")).strip()
    participant_ids = payload.get("participant_ids", [])
    if not group_name:
        return _messaging_error_response(
            "Add a group name before creating the conversation.",
            code="missing_group_name",
            status=400,
        )
    if not isinstance(participant_ids, list):
        participant_ids = []

    friend_map = {str(friend.id): friend for friend in _friend_queryset(request.user)}
    selected_friends = []
    seen_ids = set()
    for participant_id in participant_ids:
        normalized = str(participant_id)
        if normalized in seen_ids:
            continue
        seen_ids.add(normalized)
        friend = friend_map.get(normalized)
        if friend and not _has_user_blocked(request.user, friend):
            selected_friends.append(friend)

    if not selected_friends:
        return _messaging_error_response(
            "Choose at least one friend to add to the group.",
            code="no_group_participants",
            status=400,
        )

    try:
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.GROUP,
            created_by=request.user,
            group_name=group_name[:160],
        )
        conversation.participants.add(request.user, *selected_friends)
    except Exception as exc:
        send_messaging_failure_alert(
            action="create_group_conversation",
            reason="create_group_failed",
            actor=request.user,
            details={"exception": str(exc)},
        )
        return _messaging_error_response(
            "We could not create that group right now. Please try again.",
            code="create_group_failed",
            status=500,
        )

    return JsonResponse({"ok": True, "conversation_id": str(conversation.id)})


@login_required
@require_POST
def respond_to_conversation_request(request, request_id, action):
    request_item = ConversationRequest.objects.filter(
        id=request_id,
        recipient=request.user,
        status=ConversationRequest.Status.PENDING,
    ).first()
    if not request_item:
        send_messaging_failure_alert(
            action="respond_to_request",
            reason="request_not_found",
            actor=request.user,
            details={"request_id": str(request_id), "action": action},
        )
        return _messaging_error_response(
            "This message request is no longer available.",
            code="request_not_found",
            status=404,
        )
    if _is_blocked_pair(request_item.requester, request_item.recipient):
        request_item.status = ConversationRequest.Status.DECLINED
        request_item.responded_at = timezone.now()
        request_item.save(update_fields=["status", "responded_at"])
        send_messaging_failure_alert(
            action="respond_to_request",
            reason="messaging_blocked",
            actor=request.user,
            conversation=request_item.conversation,
            target_user=request_item.requester,
            details={"request_id": str(request_item.id), "action": action},
        )
        return _messaging_error_response(
            "You cannot message this user because one of you has blocked the other.",
            code="messaging_blocked",
            status=403,
        )

    if action == "accept":
        try:
            conversation = _normalize_contact_pair(request_item.requester, request_item.recipient)
            request_item.status = ConversationRequest.Status.ACCEPTED
            request_item.conversation = conversation
            request_item.responded_at = timezone.now()
            request_item.save(update_fields=["status", "conversation", "responded_at"])
            dispatch_notification(
                recipient=request_item.requester,
                actor=request.user,
                notification_type=Notification.NotificationType.REQUEST_ACCEPTED,
                title=f"{_display_name(request.user)} accepted your chat request",
                body="Your private conversation is ready. Open Messages to continue.",
                target_url=f"{reverse('Messages')}?conversation={conversation.id}",
            )
            try:
                _send_founders_team_welcome_message(
                    request_item=request_item,
                    conversation=conversation,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to send founders welcome message for request=%s",
                    request_item.id,
                )
                send_messaging_failure_alert(
                    action="respond_to_request",
                    reason="founders_welcome_message_failed",
                    actor=request_item.requester,
                    conversation=conversation,
                    target_user=request_item.recipient,
                    details={"request_id": str(request_item.id), "exception": str(exc)},
                )
            return JsonResponse({"ok": True, "conversation_id": str(conversation.id)})
        except Exception as exc:
            send_messaging_failure_alert(
                action="respond_to_request",
                reason="accept_failed",
                actor=request.user,
                conversation=request_item.conversation,
                target_user=request_item.requester,
                details={"request_id": str(request_item.id), "exception": str(exc)},
            )
            return _messaging_error_response(
                "We could not accept this request right now. Please try again.",
                code="accept_failed",
                status=500,
            )

    if action == "decline":
        try:
            request_item.status = ConversationRequest.Status.DECLINED
            request_item.responded_at = timezone.now()
            request_item.save(update_fields=["status", "responded_at"])
            return JsonResponse({"ok": True})
        except Exception as exc:
            send_messaging_failure_alert(
                action="respond_to_request",
                reason="decline_failed",
                actor=request.user,
                conversation=request_item.conversation,
                target_user=request_item.requester,
                details={"request_id": str(request_item.id), "exception": str(exc)},
            )
            return _messaging_error_response(
                "We could not decline this request right now. Please try again.",
                code="decline_failed",
                status=500,
            )

    send_messaging_failure_alert(
        action="respond_to_request",
        reason="invalid_action",
        actor=request.user,
        conversation=request_item.conversation,
        target_user=request_item.requester,
        details={"request_id": str(request_item.id), "action": action},
    )
    return _messaging_error_response("Invalid request action.", code="invalid_action", status=400)


@login_required
@require_POST
def send_message(request, conversation_id):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        send_messaging_failure_alert(
            action="http_send_message",
            reason="malformed_payload",
            actor=request.user,
            details={"conversation_id": str(conversation_id)},
        )
        return _messaging_error_response(
            "We could not read that message. Please try again.",
            code="malformed_payload",
            status=400,
        )

    try:
        send_result = deliver_text_message(
            conversation_id=conversation_id,
            sender=request.user,
            message_text=payload.get("message", ""),
        )
    except MessagingError as exc:
        send_messaging_failure_alert(
            action="http_send_message",
            reason=exc.code,
            actor=request.user,
            details={"conversation_id": str(conversation_id), **exc.details},
        )
        return _messaging_error_response(exc.user_message, code=exc.code, status=exc.status_code)
    except Exception as exc:
        send_messaging_failure_alert(
            action="http_send_message",
            reason="unexpected_exception",
            actor=request.user,
            details={"conversation_id": str(conversation_id), "exception": str(exc)},
        )
        return _messaging_error_response(
            "We could not send your message right now. Please try again.",
            code="send_failed",
            status=500,
        )

    message = send_result["message"]
    conversation = send_result["conversation"]
    try:
        broadcast_chat_message(
            conversation=conversation,
            message=message,
            sender=request.user,
        )
    except RealtimeDeliveryError as exc:
        send_messaging_failure_alert(
            action="http_send_message",
            reason=exc.code,
            actor=request.user,
            conversation=conversation,
            details={"message_id": str(message.id), **exc.details},
        )
    except Exception as exc:
        send_messaging_failure_alert(
            action="http_send_message",
            reason="broadcast_failed",
            actor=request.user,
            conversation=conversation,
            details={"message_id": str(message.id), "exception": str(exc)},
        )
    return JsonResponse(
        {
            "ok": True,
            "conversation_id": str(conversation.id),
            "message": _serialize_message(
                message,
                viewer=request.user,
                is_ephemeral=send_result.get("is_ephemeral", False),
            ),
            "preview": message.body,
            "time": _relative_time_label(message.created_at),
        }
    )


@login_required
@require_POST
def send_media_message(request, conversation_id):
    uploaded_file = request.FILES.get("attachment")
    requested_type = request.POST.get("message_type", "")
    caption = request.POST.get("caption", "")
    alert_worthy_media_errors = {"unsupported_attachment_type", "attachment_too_large"}

    try:
        send_result = deliver_media_message(
            conversation_id=conversation_id,
            sender=request.user,
            uploaded_file=uploaded_file,
            requested_type=requested_type,
            caption=caption,
        )
    except MessagingError as exc:
        if exc.code in alert_worthy_media_errors:
            send_messaging_failure_alert(
                action="http_send_media_message",
                reason=exc.code,
                actor=request.user,
                details={"conversation_id": str(conversation_id), **exc.details},
            )
        return _messaging_error_response(exc.user_message, code=exc.code, status=exc.status_code)
    except Exception as exc:
        send_messaging_failure_alert(
            action="http_send_media_message",
            reason="unexpected_exception",
            actor=request.user,
            details={"conversation_id": str(conversation_id), "exception": str(exc)},
        )
        return _messaging_error_response(
            "We could not send that attachment right now. Please try again.",
            code="send_failed",
            status=500,
        )

    message = send_result["message"]
    conversation = send_result["conversation"]
    try:
        broadcast_chat_message(
            conversation=conversation,
            message=message,
            sender=request.user,
        )
    except RealtimeDeliveryError as exc:
        send_messaging_failure_alert(
            action="http_send_media_message",
            reason=exc.code,
            actor=request.user,
            conversation=conversation,
            details={"message_id": str(message.id), **exc.details},
        )
    except Exception as exc:
        send_messaging_failure_alert(
            action="http_send_media_message",
            reason="broadcast_failed",
            actor=request.user,
            conversation=conversation,
            details={"message_id": str(message.id), "exception": str(exc)},
        )
    return JsonResponse(
        {
            "ok": True,
            "conversation_id": str(conversation.id),
            "message": _serialize_message(message, viewer=request.user),
            "preview": (
                message.body
                or (
                    "Sent an image"
                    if message.message_type == Message.MessageType.IMAGE
                    else "Sent a voice message"
                    if message.message_type == Message.MessageType.VOICE
                    else f"Shared {message.attachment_name or 'a file'}"
                )
            ),
            "time": _relative_time_label(message.created_at),
        }
    )


@login_required
@require_POST
def mark_messages_seen(request, conversation_id):
    conversation = (
        Conversation.objects.filter(
            id=conversation_id,
            participants=request.user,
        )
        .distinct()
        .first()
    )
    if not conversation:
        send_messaging_failure_alert(
            action="mark_messages_seen",
            reason="conversation_not_found",
            actor=request.user,
            details={"conversation_id": str(conversation_id)},
        )
        return _messaging_error_response(
            "This conversation is no longer available.",
            code="conversation_not_found",
            status=404,
        )

    try:
        updates = mark_conversation_seen(conversation=conversation, user=request.user)
    except Exception as exc:
        send_messaging_failure_alert(
            action="mark_messages_seen",
            reason="mark_seen_failed",
            actor=request.user,
            conversation=conversation,
            details={"exception": str(exc)},
        )
        return _messaging_error_response(
            "We could not update message status right now.",
            code="mark_seen_failed",
            status=500,
        )

    if updates:
        try:
            broadcast_message_receipts_seen(
                conversation_id=conversation.id,
                seen_by_user_id=request.user.id,
                updates=updates,
            )
        except Exception as exc:
            send_messaging_failure_alert(
                action="mark_messages_seen",
                reason="broadcast_receipts_failed",
                actor=request.user,
                conversation=conversation,
                details={"exception": str(exc), "updates": updates},
            )

    return JsonResponse({"ok": True, "updates": updates})


@login_required
@require_POST
def toggle_conversation_mute(request, conversation_id):
    conversation = (
        Conversation.objects.filter(
            id=conversation_id,
            participants=request.user,
        )
        .distinct()
        .first()
    )
    if not conversation:
        send_messaging_failure_alert(
            action="toggle_conversation_mute",
            reason="conversation_not_found",
            actor=request.user,
            details={"conversation_id": str(conversation_id)},
        )
        return _messaging_error_response(
            "This conversation is no longer available.",
            code="conversation_not_found",
            status=404,
        )

    try:
        state, _created = ConversationUserState.objects.get_or_create(
            conversation=conversation,
            user=request.user,
        )
        state.mute_notifications = not state.mute_notifications
        state.save(update_fields=["mute_notifications", "updated_at"])
        return JsonResponse({"ok": True, "mute_notifications": state.mute_notifications})
    except Exception as exc:
        send_messaging_failure_alert(
            action="toggle_conversation_mute",
            reason="mute_update_failed",
            actor=request.user,
            conversation=conversation,
            details={"exception": str(exc)},
        )
        return _messaging_error_response(
            "We could not update notification settings right now.",
            code="mute_update_failed",
            status=500,
        )


@login_required
@require_POST
def report_conversation_user(request, conversation_id):
    conversation = (
        Conversation.objects.filter(
            id=conversation_id,
            conversation_type=Conversation.ConversationType.PRIVATE,
            participants=request.user,
        )
        .prefetch_related("participants")
        .distinct()
        .first()
    )
    if not conversation:
        send_messaging_failure_alert(
            action="report_conversation_user",
            reason="conversation_not_found",
            actor=request.user,
            details={"conversation_id": str(conversation_id)},
        )
        return _messaging_error_response(
            "This conversation is no longer available.",
            code="conversation_not_found",
            status=404,
        )

    partner = _conversation_partner(conversation, request.user)
    if not partner:
        send_messaging_failure_alert(
            action="report_conversation_user",
            reason="partner_not_found",
            actor=request.user,
            conversation=conversation,
        )
        return _messaging_error_response(
            "We could not identify the other participant in this conversation.",
            code="partner_not_found",
            status=409,
        )

    reason = request.POST.get("report_reason", "").strip()
    other_reason = request.POST.get("report_reason_other", "").strip()
    should_block_user = _as_bool(request.POST.get("block_user"))
    if reason == "Other":
        reason = other_reason
    if not reason:
        send_messaging_failure_alert(
            action="report_conversation_user",
            reason="empty_reason",
            actor=request.user,
            conversation=conversation,
            target_user=partner,
        )
        return _messaging_error_response(
            "Please tell us what went wrong before sending the report.",
            code="empty_reason",
            status=400,
        )

    if not _send_user_report_email(request.user, partner, reason):
        send_messaging_failure_alert(
            action="report_conversation_user",
            reason="report_email_failed",
            actor=request.user,
            conversation=conversation,
            target_user=partner,
        )
        return _messaging_error_response(
            "We could not send your report right now. Please try again.",
            code="report_email_failed",
            status=500,
        )

    if should_block_user:
        BlockedUser.objects.get_or_create(blocker=request.user, blocked=partner)
        ConversationRequest.objects.filter(
            Q(requester=request.user, recipient=partner) | Q(requester=partner, recipient=request.user),
            status=ConversationRequest.Status.PENDING,
        ).update(
            status=ConversationRequest.Status.DECLINED,
            responded_at=timezone.now(),
        )

    return JsonResponse(
        {
            "ok": True,
            "blocked": should_block_user,
            "message": (
                "Your report was sent and this user has been blocked."
                if should_block_user
                else "Your report was sent."
            ),
        }
    )


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    conversation = (
        Conversation.objects.filter(
            id=conversation_id,
            conversation_type=Conversation.ConversationType.PRIVATE,
            participants=request.user,
        )
        .prefetch_related("participants")
        .distinct()
        .first()
    )
    if not conversation:
        send_messaging_failure_alert(
            action="delete_conversation",
            reason="conversation_not_found",
            actor=request.user,
            details={"conversation_id": str(conversation_id)},
        )
        return _messaging_error_response(
            "This conversation is no longer available.",
            code="conversation_not_found",
            status=404,
        )

    partner = _conversation_partner(conversation, request.user)
    conversation_id_str = str(conversation.id)
    try:
        try:
            broadcast_conversation_deleted(
                conversation_id=conversation.id,
                deleted_by_user_id=request.user.id,
            )
        except Exception as exc:
            send_messaging_failure_alert(
                action="delete_conversation",
                reason="broadcast_delete_failed",
                actor=request.user,
                conversation=conversation,
                target_user=partner,
                details={"exception": str(exc)},
            )

        ConversationRequest.objects.filter(conversation=conversation).delete()
        conversation.delete()
        return JsonResponse({"ok": True, "conversation_id": conversation_id_str})
    except Exception as exc:
        send_messaging_failure_alert(
            action="delete_conversation",
            reason="delete_failed",
            actor=request.user,
            conversation=conversation,
            target_user=partner,
            details={"exception": str(exc)},
        )
        return _messaging_error_response(
            "We could not delete this conversation right now.",
            code="delete_failed",
            status=500,
        )


@login_required
@require_POST
def toggle_conversation_recording(request, conversation_id):
    conversation = (
        Conversation.objects.filter(
            id=conversation_id,
            participants=request.user,
        )
        .distinct()
        .first()
    )
    if not conversation:
        send_messaging_failure_alert(
            action="toggle_conversation_recording",
            reason="conversation_not_found",
            actor=request.user,
            details={"conversation_id": str(conversation_id)},
        )
        return _messaging_error_response(
            "This conversation is no longer available.",
            code="conversation_not_found",
            status=404,
        )

    try:
        conversation.recording_mode = (
            Conversation.RecordingMode.EPHEMERAL
            if conversation.recording_mode == Conversation.RecordingMode.RECORDED
            else Conversation.RecordingMode.RECORDED
        )
        conversation.save(update_fields=["recording_mode", "updated_at"])
        return JsonResponse(
            {
                "ok": True,
                "recording_mode": conversation.recording_mode,
                "banner": (
                    "Messages in this conversation are currently ephemeral and will not be saved."
                    if conversation.recording_mode == Conversation.RecordingMode.EPHEMERAL
                    else "Messages in this conversation are being saved normally."
                ),
            }
        )
    except Exception as exc:
        send_messaging_failure_alert(
            action="toggle_conversation_recording",
            reason="recording_update_failed",
            actor=request.user,
            conversation=conversation,
            details={"exception": str(exc)},
        )
        return _messaging_error_response(
            "We could not update recording settings right now.",
            code="recording_update_failed",
            status=500,
        )


@login_required
def notifications_list(request):
    enabled_types = enabled_in_app_notification_types(request.user)
    show_all = request.GET.get("all") in {"1", "true", "yes"}
    notifications = Notification.objects.filter(recipient=request.user, is_read=False)
    if enabled_types:
        notifications = notifications.filter(notification_type__in=enabled_types)
    else:
        notifications = notifications.none()
    unread_count = notifications.count()
    notifications = notifications.select_related("actor")
    notifications = list(notifications if show_all else notifications[:4])
    return JsonResponse(
        {
            "notifications": [serialize_notification(notification) for notification in notifications],
            "unread_count": unread_count,
            "show_all": show_all,
            "has_more": unread_count > 4,
        }
    )


@login_required
@require_POST
def notifications_mark_read(request, notification_id):
    notification = Notification.objects.filter(id=notification_id, recipient=request.user).first()
    if not notification:
        raise Http404("Notification not found")
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def toggle_block_user(request, user_id):
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        send_messaging_failure_alert(
            action="toggle_block_user",
            reason="user_not_found",
            actor=request.user,
            details={"user_id": str(user_id)},
        )
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return _messaging_error_response("User not found.", code="user_not_found", status=404)
        raise Http404("User not found")
    if target_user == request.user:
        send_messaging_failure_alert(
            action="toggle_block_user",
            reason="self_block_forbidden",
            actor=request.user,
            target_user=target_user,
            details={"user_id": str(user_id)},
        )
        return _messaging_error_response("You cannot block yourself.", code="self_block_forbidden", status=400)

    try:
        existing_block = BlockedUser.objects.filter(blocker=request.user, blocked=target_user).first()
        blocked_now = False
        if existing_block:
            existing_block.delete()
        else:
            BlockedUser.objects.create(blocker=request.user, blocked=target_user)
            blocked_now = True

        ConversationRequest.objects.filter(
            Q(requester=request.user, recipient=target_user) | Q(requester=target_user, recipient=request.user),
            status=ConversationRequest.Status.PENDING,
        ).update(
            status=ConversationRequest.Status.DECLINED,
            responded_at=timezone.now(),
        )
    except Exception as exc:
        send_messaging_failure_alert(
            action="toggle_block_user",
            reason="block_update_failed",
            actor=request.user,
            target_user=target_user,
            details={"user_id": str(user_id), "exception": str(exc)},
        )
        return _messaging_error_response(
            "Unable to update block status right now.",
            code="block_update_failed",
            status=500,
        )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": True,
                "blocked": blocked_now,
                "message": (
                    f"You blocked {_display_name(target_user)}."
                    if blocked_now
                    else f"You unblocked {_display_name(target_user)}."
                ),
            }
        )

    next_url = request.POST.get("next", "").strip() or request.META.get("HTTP_REFERER") or reverse("Settings")
    suffix = "blocked=1" if blocked_now else "unblocked=1"
    joiner = "&" if "?" in next_url else "?"
    return redirect(f"{next_url}{joiner}{suffix}")

@login_required
def projects(request):
    project_cards = [
        _project_card_context(project)
        for project in Project.objects.filter(is_active=True)
        .exclude(user__profile__is_account_paused=True)
        .select_related("user", "user__profile")
    ]
    response = render(request, "project.html", {"projects": project_cards})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


@login_required
def project_detail(request, project_slug):
    project = (
        Project.objects.select_related("user", "user__profile")
        .filter(slug=project_slug, is_active=True)
        .exclude(user__profile__is_account_paused=True)
        .first()
    )
    if not project:
        raise Http404("Project not found")

    score = project.alignment_score
    if score >= 85:
        alignment_band = "high"
    elif score >= 70:
        alignment_band = "medium"
    else:
        alignment_band = "low"

    founder_name = project.founder_name or "CoVise Founder"
    if project.user and project.user.full_name:
        founder_name = project.user.full_name

    founder_initials = project.founder_initials or "CV"
    if project.user and getattr(project.user, "avatar_initials", ""):
        founder_initials = project.user.avatar_initials

    context = {
        "project": project,
        "alignment_band": alignment_band,
        "project_founder_name": founder_name,
        "project_founder_initials": founder_initials,
        "project_founder_avatar_url": _user_avatar_url(project.user) if project.user else "",
    }
    return render(request, "project_detail.html", context)

def _can_view_profile(viewer, target_user):
    if viewer == target_user:
        return True

    try:
        target_profile = target_user.profile
    except Profile.DoesNotExist:
        target_profile = None
    if getattr(target_profile, "is_account_paused", False):
        return False

    preferences = getattr(target_user, "preferences", None)
    visibility = getattr(preferences, "profile_visibility", "everyone")

    if visibility == "nobody":
        return False
    if visibility == "matched_only":
        return False
    return True


def _profile_section_status_message(request, success_map):
    status = request.GET.get("status", "").strip().lower()
    return success_map.get(status, "")


def _build_profile_display_context(request, target_user, is_own_profile):
    profile_page = build_profile_context(target_user)
    preferences = profile_page.get("preferences", {})
    can_view_profile_data = is_own_profile or preferences.get("read_profile_data", True)
    target_profile = getattr(target_user, "profile", None)
    is_onboarded = _is_profile_onboarded(target_profile)
    extended_onboarding_complete = _has_completed_extended_onboarding(target_profile)
    onboarding_prompts = {
        "headline": "Complete your profile",
        "location": "Add your location",
        "what_im_building": "Add your one-liner and market focus to show founders what you're building.",
        "looking_for": "Add the skills, commitment, and collaborator type you are looking for.",
    }

    if not can_view_profile_data:
        profile_page["headline"] = "This user prefers to keep their profile details private."
        profile_page["location"] = "Private"
        profile_page["what_im_building"] = ""
        profile_page["what_im_building_tags"] = []
        profile_page["looking_for"] = ""
        profile_page["looking_for_tags"] = []
    elif not is_own_profile:
        if not target_profile:
            profile_page["headline"] = "This user has not added public profile details yet."
            profile_page["location"] = "Location not shared"
            profile_page["what_im_building"] = "No public project summary yet."
            profile_page["what_im_building_tags"] = []
            profile_page["looking_for"] = "No collaborator preferences shared yet."
            profile_page["looking_for_tags"] = []
            profile_page["conviction_title"] = "Profile details limited"
            profile_page["conviction_sub"] = "This user has not added enough public profile data yet."
        else:
            if not profile_page.get("headline") or profile_page.get("headline") == onboarding_prompts["headline"]:
                profile_page["headline"] = "This user has not added a public bio yet."
            if not profile_page.get("location") or profile_page.get("location") == onboarding_prompts["location"]:
                profile_page["location"] = "Location not shared"
            if not profile_page.get("what_im_building") or profile_page.get("what_im_building") == onboarding_prompts["what_im_building"]:
                profile_page["what_im_building"] = "No public project summary yet."
                profile_page["what_im_building_tags"] = []
            if not profile_page.get("looking_for") or profile_page.get("looking_for") == onboarding_prompts["looking_for"]:
                profile_page["looking_for"] = "No collaborator preferences shared yet."
                profile_page["looking_for_tags"] = []
            if not profile_page.get("conviction_score"):
                profile_page["conviction_title"] = "Profile details limited"
                profile_page["conviction_sub"] = "This user has not added enough public profile data yet."

    viewer_blocked_ids = _blocked_user_ids(request.user)
    is_blocked_user = target_user.id in viewer_blocked_ids and not is_own_profile
    messaging_blocked = _is_blocked_pair(request.user, target_user) and not is_own_profile
    is_friend = _are_friends(request.user, target_user) and not is_own_profile
    has_pending_outgoing_request = (
        ConversationRequest.objects.filter(
            requester=request.user,
            recipient=target_user,
            status=ConversationRequest.Status.PENDING,
        ).exists()
        and not is_own_profile
    )
    founders_can_delete_account = _is_founders_admin(request.user) and not is_own_profile
    report_error_code = request.GET.get("report_error", "").strip()
    report_error_message = ""
    if report_error_code == "empty":
        report_error_message = "Please tell us what went wrong before sending the report."
    elif report_error_code == "email":
        report_error_message = "We could not send your report right now. Please try again."
    elif report_error_code == "self":
        report_error_message = "You cannot report your own profile."

    experiences = list(
        target_user.experiences.order_by("-id")
    ) if can_view_profile_data else []
    active_projects = list(
        target_user.active_projects.order_by("-id")
    ) if can_view_profile_data else []
    posts = list(
        _mark_saved_posts(
            target_user.posts.select_related("user", "user__profile")
            .prefetch_related("gallery_images", "mentions__mentioned_user")
            .exclude(user_id__in=viewer_blocked_ids)
            .order_by("-created_at"),
            request.user,
        )
    ) if can_view_profile_data else []
    if posts:
        _attach_post_feed_metadata(posts, current_user=request.user)
        _attach_post_comment_threads(posts, current_user=request.user)

    saved_posts = build_saved_post_items(request.user) if is_own_profile else []

    if is_own_profile:
        profile_home_url = reverse("Profile")
        profile_personal_data_url = reverse("Profile Personal Data")
        profile_experience_url = reverse("Profile Experience")
        profile_active_projects_url = reverse("Profile Active Projects")
        profile_saved_posts_url = reverse("Profile Saved Posts")
        profile_posts_url = reverse("Profile Posts")
    else:
        profile_home_url = reverse("Public Profile", args=[target_user.id])
        profile_personal_data_url = ""
        profile_experience_url = reverse("Public Profile Experience", args=[target_user.id])
        profile_active_projects_url = reverse("Public Profile Active Projects", args=[target_user.id])
        profile_saved_posts_url = ""
        profile_posts_url = reverse("Public Profile Posts", args=[target_user.id])

    context = {
        "ui_user": build_ui_user_context(target_user),
        "viewer_ui_user": build_ui_user_context(request.user),
        "viewed_user_id": target_user.id,
        "profile_page": profile_page,
        "profile_show_cofounder_badge": can_view_profile_data and _profile_has_visible_cofounder_badge(target_profile),
        "experiences": experiences,
        "experience_preview": experiences[:3],
        "has_more_experiences": len(experiences) > 3,
        "active_projects": active_projects,
        "active_projects_preview": active_projects[:2],
        "has_more_active_projects": len(active_projects) > 2,
        "posts": posts,
        "posts_preview": posts[:2],
        "has_more_posts": len(posts) > 2,
        "saved_posts": saved_posts,
        "saved_posts_preview": saved_posts[:2],
        "has_more_saved_posts": len(saved_posts) > 2,
        "is_own_profile": is_own_profile,
        "profile_read_only": not is_own_profile,
        "can_view_profile_data": can_view_profile_data,
        "profile_home_url": profile_home_url,
        "profile_personal_data_url": profile_personal_data_url,
        "profile_experience_url": profile_experience_url,
        "profile_active_projects_url": profile_active_projects_url,
        "profile_saved_posts_url": profile_saved_posts_url,
        "profile_posts_url": profile_posts_url,
        "blocked_users": _blocked_user_items(request.user) if is_own_profile else [],
        "is_blocked_user": is_blocked_user,
        "messaging_blocked": messaging_blocked,
        "is_friend": is_friend,
        "has_pending_outgoing_request": has_pending_outgoing_request,
        "founders_can_delete_account": founders_can_delete_account,
        "is_onboarded": is_onboarded,
        "extended_onboarding_complete": extended_onboarding_complete,
        "profile_error_message": (
            "Messaging is disabled because one of you has blocked the other."
            if request.GET.get("blocked_message") == "1"
            else "We could not send your request right now. Please try again."
            if request.GET.get("request_error") == "1"
            else ""
        ),
        "profile_report_success_message": (
            "Your report has been sent. Our team will review it, and this user was added to your blocked list."
            if request.GET.get("reported") == "blocked"
            else "Your report has been sent. Our team will review it."
            if request.GET.get("reported") == "1"
            else ""
        ),
        "profile_report_error_message": report_error_message,
    }
    return context


def _render_profile_page(request, target_user, is_own_profile):
    return render(request, "profile.html", _build_profile_display_context(request, target_user, is_own_profile))


def _build_profile_section_context(request, target_user, is_own_profile, *, section_key, section_title, section_description):
    context = _build_profile_display_context(request, target_user, is_own_profile)
    context.update(
        {
            "profile_section_key": section_key,
            "profile_section_title": section_title,
            "profile_section_description": section_description,
        }
    )
    return context


def _public_profile_section_target(request, user_id):
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        raise Http404("User not found")
    if not _can_view_profile(request.user, target_user):
        raise Http404("Profile not available")
    return target_user


def _parse_profile_skills(raw_value):
    skill_config = get_onboarding_skill_config()
    allowed_skills = set(skill_config["options"])
    values = []
    for item in re.split(r"[,|\n]", raw_value or ""):
        normalized = item.strip()
        if normalized and normalized in allowed_skills and normalized not in values:
            values.append(normalized)
    return values[: skill_config["max_selected"]]


@login_required
def profile_personal_data(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    context = _build_profile_section_context(
        request,
        request.user,
        True,
        section_key="personal_data",
        section_title="Personal Data",
        section_description="Update the details people use to recognize and trust your profile.",
    )
    context.update(
        {
            "profile_photo_max_size_bytes": PROFILE_PHOTO_MAX_SIZE_BYTES,
            "profile_photo_max_size_mb": PROFILE_PHOTO_MAX_SIZE_MB,
            "settings_page": build_settings_context(request.user),
            "profile_section_success_message": _profile_section_status_message(
                request,
                {"updated": "Your personal data is updated."},
            ),
            "profile_section_error_message": "",
        }
    )

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        profile_photo_action = request.POST.get("profile_photo_action", "").strip()
        uploaded_profile_image = request.FILES.get("profile_image")

        if email and email != request.user.email:
            if User.objects.filter(email=email).exclude(pk=request.user.pk).exists():
                context["profile_section_error_message"] = "This email is already registered on CoVise."
                return render(request, "profile_section.html", context, status=400)
            request.user.email = email
            request.user.save(update_fields=["email"])

        profile.phone_number = phone_number
        profile.linkedin = request.POST.get("linkedin", "").strip()
        profile.github = request.POST.get("github", "").strip()
        profile.proof_of_work_url = request.POST.get("proof_of_work_url", "").strip()
        profile.country = request.POST.get("location", "").strip()
        profile.nationality = request.POST.get("nationality", "").strip()
        profile.bio = request.POST.get("bio", "").strip()
        profile.skills = _parse_profile_skills(request.POST.get("skills", ""))

        update_fields = [
            "phone_number",
            "linkedin",
            "github",
            "proof_of_work_url",
            "country",
            "nationality",
            "bio",
            "skills",
        ]

        if profile_photo_action == "remove":
            if profile.profile_image:
                profile.profile_image.delete(save=False)
            profile.profile_image = None
            update_fields.append("profile_image")
        elif uploaded_profile_image:
            if uploaded_profile_image.size > PROFILE_PHOTO_MAX_SIZE_BYTES:
                context["profile_section_error_message"] = (
                    f"Profile photo must be {PROFILE_PHOTO_MAX_SIZE_MB} MB or smaller."
                )
                return render(request, "profile_section.html", context, status=400)
            profile.profile_image = uploaded_profile_image
            update_fields.append("profile_image")

        profile.save(update_fields=update_fields)
        return redirect(f"{reverse('Profile Personal Data')}?status=updated")

    return render(request, "profile_section.html", context)


@login_required
def profile_experience(request):
    context = _build_profile_section_context(
        request,
        request.user,
        True,
        section_key="experience",
        section_title="Experience",
        section_description="Show your track record, operating context, and the work that gives you credibility.",
    )
    context.update(
        {
            "profile_section_success_message": _profile_section_status_message(
                request,
                {
                    "created": "Experience added.",
                    "updated": "Experience updated.",
                    "deleted": "Experience removed.",
                },
            ),
            "profile_section_error_message": "",
        }
    )

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        experience_id = request.POST.get("experience_id", "").strip()
        title = request.POST.get("title", "").strip()
        date = request.POST.get("date", "").strip()
        desc = request.POST.get("desc", "").strip()

        if action == "delete":
            experience = get_object_or_404(Experiences, id=experience_id, user=request.user)
            experience.delete()
            return redirect(f"{reverse('Profile Experience')}?status=deleted")

        if not title or not date or not desc:
            context["profile_section_error_message"] = "Title, date, and description are required."
            return render(request, "profile_section.html", context, status=400)

        if action == "update":
            experience = get_object_or_404(Experiences, id=experience_id, user=request.user)
            experience.title = title
            experience.date = date
            experience.desc = desc
            experience.save(update_fields=["title", "date", "desc"])
            return redirect(f"{reverse('Profile Experience')}?status=updated")

        Experiences.objects.create(user=request.user, title=title, date=date, desc=desc)
        return redirect(f"{reverse('Profile Experience')}?status=created")

    return render(request, "profile_section.html", context)


@login_required
def profile_active_projects(request):
    context = _build_profile_section_context(
        request,
        request.user,
        True,
        section_key="active_projects",
        section_title="Active Projects",
        section_description="Show what you are building now, where it stands, and what deserves attention next.",
    )
    context.update(
        {
            "profile_section_success_message": _profile_section_status_message(
                request,
                {
                    "created": "Project added.",
                    "updated": "Project updated.",
                    "deleted": "Project removed.",
                },
            ),
            "profile_section_error_message": "",
        }
    )

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        project_id = request.POST.get("project_id", "").strip()
        name = request.POST.get("name", "").strip()
        status_text = request.POST.get("status_text", "").strip()
        desc = request.POST.get("desc", "").strip()

        if action == "delete":
            active_project = get_object_or_404(Active_projects, id=project_id, user=request.user)
            active_project.delete()
            return redirect(f"{reverse('Profile Active Projects')}?status=deleted")

        if not name or not desc:
            context["profile_section_error_message"] = "Project name and description are required."
            return render(request, "profile_section.html", context, status=400)

        if action == "update":
            active_project = get_object_or_404(Active_projects, id=project_id, user=request.user)
            active_project.name = name
            active_project.status = status_text
            active_project.desc = desc
            active_project.save(update_fields=["name", "status", "desc"])
            return redirect(f"{reverse('Profile Active Projects')}?status=updated")

        Active_projects.objects.create(
            user=request.user,
            name=name,
            status=status_text,
            desc=desc,
        )
        return redirect(f"{reverse('Profile Active Projects')}?status=created")

    return render(request, "profile_section.html", context)


@login_required
def profile_saved_posts(request):
    context = _build_profile_section_context(
        request,
        request.user,
        True,
        section_key="saved_posts",
        section_title="Saved Posts",
        section_description="Keep track of the posts you want to revisit, respond to, or learn from later.",
    )
    context.update(
        {
            "profile_section_success_message": _profile_section_status_message(
                request,
                {"removed": "Saved post removed."},
            ),
            "profile_section_error_message": "",
        }
    )

    if request.method == "POST":
        post_id = request.POST.get("post_id", "").strip()
        SavedPost.objects.filter(user=request.user, post_id=post_id).delete()
        return redirect(f"{reverse('Profile Saved Posts')}?status=removed")

    return render(request, "profile_section.html", context)


@login_required
def profile_posts(request):
    context = _build_profile_section_context(
        request,
        request.user,
        True,
        section_key="posts",
        section_title="Posts",
        section_description="Review the updates, asks, and builds you have shared with the CoVise network.",
    )
    return render(request, "profile_section.html", context)


@login_required
def public_profile_experience(request, user_id):
    target_user = _public_profile_section_target(request, user_id)
    if target_user == request.user:
        return redirect(reverse("Profile Experience"))
    context = _build_profile_section_context(
        request,
        target_user,
        False,
        section_key="experience",
        section_title="Experience",
        section_description="A read-only view of this member's public background and operating context.",
    )
    return render(request, "profile_section.html", context)


@login_required
def public_profile_active_projects(request, user_id):
    target_user = _public_profile_section_target(request, user_id)
    if target_user == request.user:
        return redirect(reverse("Profile Active Projects"))
    context = _build_profile_section_context(
        request,
        target_user,
        False,
        section_key="active_projects",
        section_title="Active Projects",
        section_description="A read-only view of the projects this member is currently showing on their profile.",
    )
    return render(request, "profile_section.html", context)


@login_required
def public_profile_posts(request, user_id):
    target_user = _public_profile_section_target(request, user_id)
    if target_user == request.user:
        return redirect(reverse("Profile Posts"))
    context = _build_profile_section_context(
        request,
        target_user,
        False,
        section_key="posts",
        section_title="Posts",
        section_description="A read-only view of this member's public posts and updates.",
    )
    return render(request, "profile_section.html", context)


@login_required
def profile(request):
    return _render_profile_page(request, request.user, True)


@login_required
def agreement(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    next_url = _agreement_next_url(request)
    read_only = profile.has_accepted_platform_agreement

    if not read_only and not _is_profile_onboarded(profile):
        onboarding_url = reverse("Onboarding")
        if next_url:
            return redirect(f"{onboarding_url}?next={quote(next_url)}")
        return redirect(onboarding_url)

    if request.method == "POST":
        if read_only:
            return redirect(reverse("Agreement"))
        if request.POST.get("agree") != "on":
            return render(
                request,
                "agreement.html",
                {
                    "agreement_error_message": "You need to agree before entering CoVise.",
                    "agreement_next_url": next_url,
                    "agreement_profile": profile,
                    "agreement_read_only": read_only,
                },
                status=400,
            )

        profile.has_accepted_platform_agreement = True
        profile.platform_agreement_accepted_at = timezone.now()
        profile.platform_agreement_version = "2026.04"
        if not Post.objects.filter(user=request.user).exists():
            profile.requires_intro_post = True
        profile.save(
            update_fields=[
                "has_accepted_platform_agreement",
                "platform_agreement_accepted_at",
                "platform_agreement_version",
                "requires_intro_post",
            ]
        )
        try:
            _send_platform_welcome_email(request.user)
        except Exception:
            logger.exception("Failed to send platform welcome email for user=%s", request.user.id)
        if profile.requires_intro_post:
            return redirect(reverse("Home"))
        return redirect(next_url)

    return render(
        request,
        "agreement.html",
        {
            "agreement_next_url": next_url,
            "agreement_profile": profile,
            "agreement_read_only": read_only,
        },
    )


@login_required
def public_profile(request, user_id):
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        raise Http404("User not found")
    if not _can_view_profile(request.user, target_user):
        raise Http404("Profile not available")
    return _render_profile_page(request, target_user, request.user == target_user)


@login_required
@require_POST
def report_user_profile(request, user_id):
    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        raise Http404("User not found")
    if target_user == request.user:
        return redirect(f"{reverse('Public Profile', args=[user_id])}?report_error=self")

    reason = request.POST.get("report_reason", "").strip()
    other_reason = request.POST.get("report_reason_other", "").strip()
    should_block_user = _as_bool(request.POST.get("block_user"))
    if reason == "Other":
        reason = other_reason
    if not reason:
        return redirect(f"{reverse('Public Profile', args=[user_id])}?report_error=empty")

    if _send_user_report_email(request.user, target_user, reason):
        reported_state = "1"
        if should_block_user:
            BlockedUser.objects.get_or_create(blocker=request.user, blocked=target_user)
            ConversationRequest.objects.filter(
                Q(requester=request.user, recipient=target_user) | Q(requester=target_user, recipient=request.user),
                status=ConversationRequest.Status.PENDING,
            ).update(
                status=ConversationRequest.Status.DECLINED,
                responded_at=timezone.now(),
            )
            reported_state = "blocked"
        return redirect(f"{reverse('Public Profile', args=[user_id])}?reported={reported_state}")
    return redirect(f"{reverse('Public Profile', args=[user_id])}?report_error=email")


@login_required
def post_action(request, comment_id, action):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    comment = get_object_or_404(
        Comment.objects.select_related("user", "post__user").prefetch_related("reactions"),
        id=comment_id,
    )
    reaction_type = COMMENT_REACTION_ACTION_MAP.get(action)
    if not reaction_type:
        return JsonResponse({"error": "Invalid action"}, status=400)

    legacy_values_map = {
        CommentReaction.ReactionType.THUMBS_UP: ["up", CommentReaction.ReactionType.THUMBS_UP],
        CommentReaction.ReactionType.THUMBS_DOWN: ["down", CommentReaction.ReactionType.THUMBS_DOWN],
        CommentReaction.ReactionType.FIRE: [CommentReaction.ReactionType.FIRE],
        CommentReaction.ReactionType.ROCKET: [CommentReaction.ReactionType.ROCKET],
        CommentReaction.ReactionType.CRAZY: [CommentReaction.ReactionType.CRAZY],
    }
    legacy_values = legacy_values_map.get(reaction_type, [reaction_type])
    mutually_exclusive_values = []
    if reaction_type == CommentReaction.ReactionType.THUMBS_UP:
        mutually_exclusive_values = legacy_values_map[CommentReaction.ReactionType.THUMBS_DOWN]
    elif reaction_type == CommentReaction.ReactionType.THUMBS_DOWN:
        mutually_exclusive_values = legacy_values_map[CommentReaction.ReactionType.THUMBS_UP]

    existing_reaction = CommentReaction.objects.filter(
        user=request.user,
        comment=comment,
        reaction__in=legacy_values,
    ).first()
    if existing_reaction:
        CommentReaction.objects.filter(user=request.user, comment=comment, reaction__in=legacy_values).delete()
    else:
        if mutually_exclusive_values:
            CommentReaction.objects.filter(
                user=request.user,
                comment=comment,
                reaction__in=mutually_exclusive_values,
            ).delete()
        CommentReaction.objects.create(
            user=request.user,
            comment=comment,
            reaction=reaction_type,
        )

    reaction_totals = comment.reactions.aggregate(
        thumbs_up=Count("id", filter=Q(reaction__in=[CommentReaction.ReactionType.THUMBS_UP, "up"])),
        thumbs_down=Count("id", filter=Q(reaction__in=[CommentReaction.ReactionType.THUMBS_DOWN, "down"])),
        fire=Count("id", filter=Q(reaction=CommentReaction.ReactionType.FIRE)),
        rocket=Count("id", filter=Q(reaction=CommentReaction.ReactionType.ROCKET)),
        crazy=Count("id", filter=Q(reaction=CommentReaction.ReactionType.CRAZY)),
    )
    comment.up = reaction_totals["thumbs_up"] or 0
    comment.down = reaction_totals["thumbs_down"] or 0
    comment.save(update_fields=["up", "down"])
    viewer_reactions = []
    for value in CommentReaction.objects.filter(user=request.user, comment=comment).values_list("reaction", flat=True):
        if value in {CommentReaction.ReactionType.THUMBS_UP, "up"} and CommentReaction.ReactionType.THUMBS_UP not in viewer_reactions:
            viewer_reactions.append(CommentReaction.ReactionType.THUMBS_UP)
        elif value in {CommentReaction.ReactionType.THUMBS_DOWN, "down"} and CommentReaction.ReactionType.THUMBS_DOWN not in viewer_reactions:
            viewer_reactions.append(CommentReaction.ReactionType.THUMBS_DOWN)
        elif value == CommentReaction.ReactionType.FIRE and CommentReaction.ReactionType.FIRE not in viewer_reactions:
            viewer_reactions.append(CommentReaction.ReactionType.FIRE)
        elif value == CommentReaction.ReactionType.ROCKET and CommentReaction.ReactionType.ROCKET not in viewer_reactions:
            viewer_reactions.append(CommentReaction.ReactionType.ROCKET)
        elif value == CommentReaction.ReactionType.CRAZY and CommentReaction.ReactionType.CRAZY not in viewer_reactions:
            viewer_reactions.append(CommentReaction.ReactionType.CRAZY)
    return JsonResponse({
        "thumbs_up": comment.up,
        "thumbs_down": comment.down,
        "fire": reaction_totals["fire"] or 0,
        "rocket": reaction_totals["rocket"] or 0,
        "crazy": reaction_totals["crazy"] or 0,
        "viewer_reactions": viewer_reactions,
        "upvotes": comment.up,
        "downvotes": comment.down,
        "user_reaction": viewer_reactions[0] if len(viewer_reactions) == 1 else "",
    })


@login_required
@require_POST
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment.objects.select_related("user"), id=comment_id)
    if comment.user_id != request.user.id:
        return JsonResponse({"ok": False, "error": "You can only edit your own comment."}, status=403)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid request payload."}, status=400)
    content = str(payload.get("content", "")).strip()
    if not content:
        return JsonResponse({"ok": False, "error": "Comment cannot be empty."}, status=400)
    comment.content = content[:200]
    comment.edited_at = timezone.now()
    comment.save(update_fields=["content", "edited_at"])
    return JsonResponse({"ok": True, "content": comment.content, "edited": True})


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment.objects.select_related("user", "post__user"), id=comment_id)
    if request.user.id not in {comment.user_id, comment.post.user_id}:
        return JsonResponse({"ok": False, "error": "You cannot delete this comment."}, status=403)
    post = comment.post
    comment.delete()
    post.comments_number = post.comments.count()
    post.save(update_fields=["comments_number"])
    return JsonResponse({"ok": True, "comments_count": post.comments_number})


@login_required
@require_POST
def toggle_comment_pin(request, comment_id):
    comment = get_object_or_404(Comment.objects.select_related("post__user"), id=comment_id)
    if request.user.id != comment.post.user_id:
        return JsonResponse({"ok": False, "error": "Only the post owner can pin comments."}, status=403)
    comment.is_pinned = not comment.is_pinned
    comment.save(update_fields=["is_pinned"])
    return JsonResponse({"ok": True, "is_pinned": comment.is_pinned})


@login_required
@require_POST
def toggle_message_reaction(request, message_id, reaction):
    reaction_type = MESSAGE_REACTION_ACTION_MAP.get(reaction)
    if not reaction_type:
        return JsonResponse({"ok": False, "error": "Invalid reaction."}, status=400)

    message = get_object_or_404(
        Message.objects.select_related("conversation", "sender").prefetch_related("conversation__participants", "reactions"),
        id=message_id,
    )
    if not message.conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({"ok": False, "error": "Message not available."}, status=404)

    existing_reaction = MessageReaction.objects.filter(
        user=request.user,
        message=message,
        reaction=reaction_type,
    ).first()
    if existing_reaction:
        existing_reaction.delete()
    else:
        MessageReaction.objects.create(
            user=request.user,
            message=message,
            reaction=reaction_type,
        )

    reaction_counts, viewer_reactions = _message_reaction_payload(message, viewer=request.user)
    return JsonResponse(
        {
            "ok": True,
            "message_id": str(message.id),
            "reaction_counts": reaction_counts,
            "viewer_reactions": viewer_reactions,
        }
    )


@login_required
@require_POST
def delete_message(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("conversation", "sender").prefetch_related("conversation__participants"),
        id=message_id,
    )
    conversation = message.conversation
    if not conversation.participants.filter(id=request.user.id).exists():
        return _messaging_error_response("Message not available.", code="message_not_found", status=404)
    if message.sender_id != request.user.id:
        return _messaging_error_response("You can only delete messages you sent.", code="delete_forbidden", status=403)

    try:
        had_attachment = bool(message.attachment_file)
        deleted_message_id = str(message.id)
        conversation_id = str(conversation.id)
        message.delete()

        latest_message = conversation.messages.order_by("-created_at").first()
        conversation.last_message_at = latest_message.created_at if latest_message else None
        conversation.save(update_fields=["last_message_at"])

        return JsonResponse(
            {
                "ok": True,
                "message_id": deleted_message_id,
                "conversation_id": conversation_id,
                "last_message_time": _relative_time_label(latest_message.created_at) if latest_message else "New",
                "last_message_preview": _message_preview_text(latest_message) if latest_message else "Start the conversation",
                "had_attachment": had_attachment,
            }
        )
    except Exception as exc:
        send_messaging_failure_alert(
            action="delete_message",
            reason="delete_failed",
            actor=request.user,
            conversation=conversation,
            details={"message_id": str(message_id), "exception": str(exc)},
        )
        return _messaging_error_response(
            "We could not delete this message right now.",
            code="delete_failed",
            status=500,
        )


@login_required
@require_POST
def report_message(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("conversation", "sender").prefetch_related("conversation__participants"),
        id=message_id,
    )
    conversation = message.conversation
    if not conversation.participants.filter(id=request.user.id).exists():
        return _messaging_error_response("Message not available.", code="message_not_found", status=404)
    if message.sender_id == request.user.id:
        return _messaging_error_response("You cannot report your own message.", code="report_forbidden", status=400)

    reason = request.POST.get("report_reason", "").strip()
    other_reason = request.POST.get("report_reason_other", "").strip()
    if reason == "Other":
        reason = other_reason
    if not reason:
        return _messaging_error_response(
            "Please tell us what went wrong before sending the report.",
            code="empty_reason",
            status=400,
        )

    if not _send_message_report_email(request.user, message.sender, message, reason):
        send_messaging_failure_alert(
            action="report_message",
            reason="report_email_failed",
            actor=request.user,
            conversation=conversation,
            target_user=message.sender,
            details={"message_id": str(message.id)},
        )
        return _messaging_error_response(
            "We could not send your report right now. Please try again.",
            code="report_email_failed",
            status=500,
        )

    return JsonResponse({"ok": True, "message": "Your report was sent successfully."})



@login_required
def profile_card(request):
    return render(request, 'profile_card.html', {
        'profile_card': build_profile_card_context(request.user),
    })
@login_required
def map_view(request):
    return render(request, 'map.html')
@login_required
def chatbot(request):
    response = render(request, "coming_soon.html", {"page_name": "CoVise Advisor"})
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response
@login_required
def settings(request):
    if request.method == "POST":
        return _handle_settings_post(
            request,
            template_name="settings.html",
            redirect_url=reverse("Settings"),
        )

    context = _build_settings_view_context(request)
    return render(request, "settings.html", context)


@login_required
def settings_section(request, section_slug):
    section = _get_settings_section_config(section_slug)
    template_name = "settings_section.html"
    redirect_url = section["url"]

    if request.method == "POST":
        return _handle_settings_post(
            request,
            template_name=template_name,
            redirect_url=redirect_url,
            section_slug=section_slug,
        )

    context = _build_settings_view_context(request, section_slug=section_slug)
    return render(request, template_name, context)


@login_required
def account_security(request):
    preferences, _ = UserPreference.objects.get_or_create(user=request.user)
    context = {}

    if request.method == "POST":
        try:
            if request.POST.get("save_section") == "security":
                security_action = request.POST.get("security_action", "").strip()

                if security_action == "enable_2fa":
                    preferences.two_factor_enabled = True
                    preferences.save(update_fields=["two_factor_enabled"])
                    return redirect(f"{reverse('Account Security')}?security=2fa-enabled")

                if security_action == "disable_2fa":
                    preferences.two_factor_enabled = False
                    preferences.save(update_fields=["two_factor_enabled"])
                    return redirect(f"{reverse('Account Security')}?security=2fa-disabled")

                if security_action == "logout_session":
                    session_key = request.POST.get("session_key", "").strip()
                    if session_key:
                        Session.objects.filter(session_key=session_key).delete()
                        if session_key == request.session.session_key:
                            logout(request)
                            return redirect(f"{reverse('Login')}?logged_out=1")
                    return redirect(f"{reverse('Account Security')}?security=session-ended")

                if security_action == "logout_other_sessions":
                    current_session_key = request.session.session_key or ""
                    for session in _active_user_sessions(request.user):
                        if session.session_key and session.session_key != current_session_key:
                            session.delete()
                    return redirect(f"{reverse('Account Security')}?security=other-sessions-ended")

        except Exception:
            pass

    context["settings_page"] = _build_settings_page_context(request)
    security_action = request.GET.get("security", "").strip()
    if security_action == "2fa-enabled":
        context["success_message"] = "Two-factor authentication is now enabled."
    if security_action == "2fa-disabled":
        context["success_message"] = "Two-factor authentication has been disabled."
    if security_action == "session-ended":
        context["success_message"] = "That session has been logged out."
    if security_action == "other-sessions-ended":
        context["success_message"] = "All other active sessions have been logged out."
    return render(request, 'account_security.html', context)


@login_required
@require_POST
def request_data_export(request):
    redirect_url = _safe_redirect_url(request, reverse("Settings"))
    export_request = DataExportRequest.objects.create(
        user=request.user,
        status=DataExportRequest.Status.PENDING,
        delivery_email=request.user.email,
    )
    try:
        _send_data_export_email(request.user)
        export_request.status = DataExportRequest.Status.COMPLETED
        export_request.completed_at = timezone.now()
        export_request.save(update_fields=["status", "completed_at"])
        return redirect(_append_query_params(redirect_url, data_export="completed"))
    except Exception:
        export_request.status = DataExportRequest.Status.FAILED
        export_request.save(update_fields=["status"])
        return redirect(_append_query_params(redirect_url, data_export="error"))


@login_required
@require_POST
def request_account_pause(request):
    redirect_url = _safe_redirect_url(request, reverse("Settings"))
    profile, _ = Profile.objects.get_or_create(user=request.user)
    action = request.POST.get("action", "").strip().lower()
    if action not in {AccountPauseRequest.Action.PAUSE, AccountPauseRequest.Action.REACTIVATE}:
        return redirect(_append_query_params(redirect_url, account_pause="error"))

    pause_request = AccountPauseRequest.objects.create(
        user=request.user,
        action=action,
        status=AccountPauseRequest.Status.COMPLETED,
    )
    try:
        if action == AccountPauseRequest.Action.PAUSE:
            profile.is_account_paused = True
            profile.account_paused_at = timezone.now()
            profile.save(update_fields=["is_account_paused", "account_paused_at"])
            pause_request.processed_at = timezone.now()
            pause_request.save(update_fields=["processed_at"])
            return redirect(_append_query_params(redirect_url, account_pause="paused"))

        profile.is_account_paused = False
        profile.account_paused_at = None
        profile.save(update_fields=["is_account_paused", "account_paused_at"])
        pause_request.processed_at = timezone.now()
        pause_request.save(update_fields=["processed_at"])
        return redirect(_append_query_params(redirect_url, account_pause="reactivated"))
    except Exception:
        pause_request.status = AccountPauseRequest.Status.FAILED
        pause_request.save(update_fields=["status"])
        return redirect(_append_query_params(redirect_url, account_pause="error"))


@login_required
@require_POST
def request_data_deletion(request):
    redirect_url = _safe_redirect_url(request, reverse("Settings"))
    deletion_request = DataDeletionRequest.objects.create(
        user=request.user,
        status=DataDeletionRequest.Status.PENDING,
    )
    try:
        with transaction.atomic():
            _execute_member_data_wipe(request.user, current_deletion_request=deletion_request)
            deletion_request.status = DataDeletionRequest.Status.COMPLETED
            deletion_request.processed_at = timezone.now()
            deletion_request.notes = "Immediate member data wipe completed while preserving login access."
            deletion_request.save(update_fields=["status", "processed_at", "notes"])
        try:
            _send_data_deletion_request_emails(request.user)
        except Exception:
            deletion_request.notes = "Immediate member data wipe completed, but confirmation email failed."
            deletion_request.save(update_fields=["notes"])
    except Exception:
        deletion_request.status = DataDeletionRequest.Status.FAILED
        deletion_request.notes = "Data wipe failed before completion."
        deletion_request.processed_at = timezone.now()
        deletion_request.save(update_fields=["status", "notes", "processed_at"])
        return redirect(_append_query_params(redirect_url, data_deletion="error"))
    return redirect(_append_query_params(redirect_url, data_deletion="completed"))


@login_required
@require_POST
def delete_account(request):
    redirect_url = _safe_redirect_url(request, reverse("Settings"))
    confirm_text = request.POST.get("confirm_delete", "").strip()
    delete_feedback = request.POST.get("delete_feedback", "").strip()
    if confirm_text != "DELETE" or not delete_feedback:
        return redirect(f"{redirect_url}#danger-zone")

    deletion_request = AccountDeletionRequest.objects.create(
        user=request.user,
        user_id_snapshot=request.user.id,
        email_snapshot=request.user.email,
        feedback=delete_feedback,
        status=AccountDeletionRequest.Status.PENDING,
    )

    user_email = request.user.email
    logger.info("Delete account feedback for user %s: %s", user_email, delete_feedback)
    try:
        deletion_request.status = AccountDeletionRequest.Status.COMPLETED
        deletion_request.processed_at = timezone.now()
        deletion_request.save(update_fields=["status", "processed_at"])
        try:
            _send_account_deletion_request_emails(request.user)
        except Exception:
            logger.exception("Account deletion confirmation email failed for user %s", user_email)
        request.user.delete()
        request.session.flush()
        logger.info("Deleted account for user with email: %s", user_email)
    except Exception:
        deletion_request.status = AccountDeletionRequest.Status.FAILED
        deletion_request.processed_at = timezone.now()
        deletion_request.save(update_fields=["status", "processed_at"])
        return redirect(f"{_append_query_params(redirect_url, delete_account='error')}#danger-zone")

    return redirect("Landing Page")


@login_required
@require_POST
def founders_delete_account(request, user_id):
    if not _is_founders_admin(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)

    target_user = get_object_or_404(User, id=user_id)
    if target_user.id == request.user.id:
        return JsonResponse({"ok": False, "error": "Use your own account settings to delete this account."}, status=400)

    redirect_url = _safe_redirect_url(request, reverse("Home"))
    delete_feedback = request.POST.get("delete_feedback", "").strip() or "Deleted by founders admin."

    deletion_request = AccountDeletionRequest.objects.create(
        user=target_user,
        user_id_snapshot=target_user.id,
        email_snapshot=target_user.email,
        feedback=delete_feedback,
        status=AccountDeletionRequest.Status.PENDING,
    )

    target_email = target_user.email
    try:
        deletion_request.status = AccountDeletionRequest.Status.COMPLETED
        deletion_request.processed_at = timezone.now()
        deletion_request.save(update_fields=["status", "processed_at"])
        target_user.delete()
        logger.info("Founders admin deleted account for user with email: %s", target_email)
    except Exception:
        deletion_request.status = AccountDeletionRequest.Status.FAILED
        deletion_request.processed_at = timezone.now()
        deletion_request.save(update_fields=["status", "processed_at"])
        return redirect(_append_query_params(redirect_url, deleted_account="error"))

    return redirect(_append_query_params(redirect_url, deleted_account="1"))


@login_required
def logout_page(request):    
    logout(request)
    return render(request, 'logout.html')


def terms(request):
    return render(request, 'terms.html')

def privacy(request):
    return render(request, 'privacy.html')

def security(request):
    return render(request, 'security.html')

def login_view(request):
    next_url = request.POST.get('next') or request.GET.get('next')
    if request.method == 'GET':
        context = {'next': next_url}
        if request.GET.get("logged_out") == "1":
            context["success_message"] = "You have been logged out."
        return render(request, 'login.html', context)

    challenge_id = request.POST.get("challenge_id", "").strip()
    if challenge_id:
        challenge = TwoFactorChallenge.objects.select_related("user", "user__profile").filter(id=challenge_id).first()
        context = {
            "two_factor_required": True,
            "challenge_id": challenge_id,
            "challenge_email": getattr(challenge, "email", ""),
            "next": next_url,
        }

        if challenge is None:
            context["two_factor_required"] = False
            context["error_message"] = "Your security check expired. Please log in again."
            return render(request, 'login.html', context, status=400)

        if request.POST.get("resend_2fa") == "1":
            try:
                challenge.code = _generate_verification_code()
                challenge.expires_at = timezone.now() + timedelta(minutes=10)
                challenge.consumed_at = None
                challenge.save(update_fields=["code", "expires_at", "consumed_at"])
                _send_two_factor_code_email(challenge.user, challenge)
            except Exception:
                context["error_message"] = "We could not send a new security code right now. Please try again."
                return render(request, 'login.html', context, status=500)
            context["info_message"] = "We sent a fresh security code to your email."
            return render(request, 'login.html', context)

        two_factor_code = "".join(ch for ch in request.POST.get("two_factor_code", "") if ch.isdigit())[:6]
        if not two_factor_code:
            context["error_message"] = "Enter the 6-digit security code we emailed you."
            return render(request, 'login.html', context, status=400)
        if not _is_valid_two_factor_challenge(challenge):
            context["two_factor_required"] = False
            context["error_message"] = "That security code expired. Please log in again."
            return render(request, 'login.html', context, status=400)
        if challenge.code != two_factor_code:
            _record_sign_in_event(challenge.user, request, status=SignInEvent.Status.FAILURE)
            context["error_message"] = "That security code is incorrect. Please try again."
            return render(request, 'login.html', context, status=400)

        user = challenge.user
        if not hasattr(user, "profile"):
            sync_profile_for_user(user)
        Profile.objects.get_or_create(user=user)
        UserPreference.objects.get_or_create(user=user)
        login(request, user)
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["consumed_at"])
        _record_successful_sign_in(user)
        _record_sign_in_event(
            user,
            request,
            status=SignInEvent.Status.SUCCESS,
            session_key=request.session.session_key or "",
        )
        return redirect(_post_auth_redirect_url(user, next_url))

    email = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '').strip()
    context = {
        "form_data": {
            "email": email,
        }
    }
    if not email or not password:
        context["error_message"] = "Both email and password are required."
        return render(request, 'login.html', context, status=400)

    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user is None: #There is no user with this email yet
        approved_waitlist_entry = WaitlistEntry.objects.filter(
            email__iexact=email,
            status=WaitlistEntry.Status.APPROVED,
        ).first()

        if approved_waitlist_entry is not None:
            context["error_message"] = "Your email is approved. But you need to create your account from sign in first."
        else:
            context["error_message"] = "This is a private community. You can only access it if your application has been approved. Please request access to become a member."
        return render(request, 'login.html', context, status=400)
    
    try:
        identify_hasher(existing_user.password)
    except Exception:
        logger.error(
            "User %s has a password value that is not a Django password hash. Reset or recreate this account with set_password().",
            existing_user.email,
        )
    user = authenticate(request, email=existing_user.email, password=password)
    if user is None:
        _record_sign_in_event(existing_user, request, status=SignInEvent.Status.FAILURE)
        context["error_message"] = "Incorrect password. Please try again."
        return render(request, 'login.html', context, status=400)

    if not hasattr(user, "profile"):
        sync_profile_for_user(user)
    Profile.objects.get_or_create(user=user)
    preferences, _ = UserPreference.objects.get_or_create(user=user)
    if preferences.two_factor_enabled:
        try:
            challenge = _issue_two_factor_challenge(user)
        except Exception:
            context["error_message"] = "We could not send your security code right now. Please try again."
            return render(request, 'login.html', context, status=500)
        context["two_factor_required"] = True
        context["challenge_id"] = str(challenge.id)
        context["challenge_email"] = user.email
        context["info_message"] = "We sent a 6-digit security code to your email."
        return render(request, 'login.html', context)

    login(request, user)
    _record_successful_sign_in(user)
    _record_sign_in_event(
        user,
        request,
        status=SignInEvent.Status.SUCCESS,
        session_key=request.session.session_key or "",
    )
    return redirect(_post_auth_redirect_url(user, next_url))


def signin(request):
    if request.method != 'POST':
        return render(request, 'signin.html')
    
    email = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '').strip()
    confirm_password = request.POST.get('confirm_password', '').strip()
    context = {
        "form_data": {
            "email": email,
        }
    }
    if not email or not password or not confirm_password:
        context["error_message"] = "All fields are required."
        return render(request, 'signin.html', context, status=400)
    
    if User.objects.filter(email__iexact=email).exists():
        context["error_message"] = "This email is already registered on CoVise. Please log in instead."
        return render(request, 'signin.html', context, status=400)
    
    approved_waitlist_entry = WaitlistEntry.objects.filter(
        email__iexact=email,
        status=WaitlistEntry.Status.APPROVED,
    ).first()
    if approved_waitlist_entry is None:
        context["error_message"] = "This email is not registered in CoVise or has not been approved yet. Please request access to become a member."
        return render(request, 'signin.html', context, status=400)
    
    if password != confirm_password:
        context["error_message"] = "Passwords do not match."
        return render(request, 'signin.html', context, status=400)
    
    if password and len(password) < 8:
        context["error_message"] = "Passwords must be at least 8 characters long."
        return render(request, 'signin.html', context, status=400)


    try:
        user = User.objects.create_user(
            email=email,
            full_name=approved_waitlist_entry.full_name,
            password=password,
        )
    except IntegrityError: #this error raises when there is a duplicate email in the database due to the unique constraint on the email field
        context["error_message"] = "This email is already registered on CoVise. Please log in instead."
        return render(request, 'signin.html', context, status=400)

    sync_profile_for_user(user, waitlist_entry=approved_waitlist_entry)
    UserPreference.objects.get_or_create(user=user)
    if approved_waitlist_entry.status != WaitlistEntry.Status.ACTIVATED:
        approved_waitlist_entry.status = WaitlistEntry.Status.ACTIVATED
        approved_waitlist_entry.save(update_fields=["status"])
    try:
        _send_new_account_alert(user, waitlist_entry=approved_waitlist_entry)
    except Exception:
        logger.exception("Failed to trigger new account alert for %s", user.email)
    try:
        _ensure_founders_team_request(user)
    except Exception as exc:
        logger.exception("Failed to create founders team request for %s", user.email)
        send_messaging_failure_alert(
            action="signup_founders_request",
            reason="request_create_failed",
            actor=user,
            details={"exception": str(exc)},
        )
    user = authenticate(request, email=email, password=password)
    if user is None:
        context["error_message"] = "Your account was created, but we could not sign you in automatically. Please try logging in."
        return render(request, 'signin.html', context, status=500)
    login(request, user)
    _record_successful_sign_in(user)
    _record_sign_in_event(
        user,
        request,
        status=SignInEvent.Status.SUCCESS,
        session_key=request.session.session_key or "",
    )
    return redirect(_post_auth_redirect_url(user, reverse("Home")))


def onboarding_final(request):
    target_url = reverse("Onboarding")
    query_string = request.META.get("QUERY_STRING", "").strip()
    if query_string:
        target_url = f"{target_url}?{query_string}"
    return redirect(target_url)


@ensure_csrf_cookie
def onboarding(request):
    flow, onboarding_error_message = _load_boarding_flow()
    onboarding_unavailable = flow is None
    initial_answers = {}
    redirect_url = reverse("Sign In")
    requested_step = str(request.GET.get("step", "")).strip().lower()
    start_step_id = "S1_PROFILE_COMPLETION"
    next_url = str(request.GET.get("next", "")).strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        redirect_url = next_url
    if getattr(request.user, "is_authenticated", False):
        profile = getattr(request.user, "profile", None)
        waitlist_initial_answers = _waitlist_to_onboarding_initial_answers(
            getattr(profile, "waitlist_snapshot", {})
        )
        initial_answers.update(waitlist_initial_answers)
        initial_answers.update(_clean_onboarding_answers(getattr(profile, "onboarding_answers", {})))
        initial_answers["email"] = request.user.email
        if profile:
            if getattr(profile, "bio", "") and "headline" not in initial_answers:
                initial_answers["headline"] = profile.bio
        initial_answers.pop("location", None)
        initial_answers.pop("profile_links", None)
        profile_completion_complete = _has_profile_completion(profile)
        if requested_step == "intent" and profile_completion_complete:
            start_step_id = _first_extended_onboarding_step_id(flow, initial_answers)
        profile_has_accepted_agreement = bool(getattr(profile, "has_accepted_platform_agreement", False))
        final_target = redirect_url if next_url else reverse("Home")
        if profile_has_accepted_agreement:
            redirect_url = final_target
        else:
            redirect_url = f"{reverse('Agreement')}?next={quote(final_target)}"
    elif request.session.get("waitlist_email"):
        initial_answers.update(
            _waitlist_to_onboarding_initial_answers(
                {
                    "email": request.session.get("waitlist_email", ""),
                    "country": request.session.get("waitlist_country", ""),
                    "custom_country": request.session.get("waitlist_custom_country", ""),
                    "non_gcc_business": request.session.get("waitlist_non_gcc_business", False),
                    "description": request.session.get("waitlist_description", ""),
                    "custom_description": request.session.get("waitlist_custom_description", ""),
                    "venture_summary": request.session.get("waitlist_venture_summary", ""),
                    "linkedin": request.session.get("waitlist_linkedin", ""),
                }
            )
        )
    return render(
        request,
        'onboarding.html',
        {
            'boarding_flow': flow,
            'onboarding_initial_answers': initial_answers,
            'onboarding_unavailable': onboarding_unavailable,
            'onboarding_error_message': onboarding_error_message,
            'onboarding_complete_redirect_url': redirect_url,
            'onboarding_start_step_id': start_step_id,
        },
    )


def onboarding_submit(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        if request.POST.get("payload"):
            payload = json.loads(request.POST.get("payload", "") or "{}")
        else:
            payload = json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        return JsonResponse({"error": "answers must be an object."}, status=400)

    flow_name = str(payload.get("flow_name", "")).strip()
    logged_in_user = request.user if getattr(request.user, "is_authenticated", False) else None
    email = (
        str(answers.get("email", "")).strip()
        or str(request.session.get("waitlist_email", "")).strip()
        or (logged_in_user.email if logged_in_user else "")
    )
    if not email:
        return JsonResponse({"error": "Email is required to save onboarding."}, status=400)

    waitlist_id = request.session.get("waitlist_entry_id")
    waitlist_entry = WaitlistEntry.objects.filter(pk=waitlist_id).first() if waitlist_id else None
    if waitlist_entry is None and logged_in_user:
        waitlist_entry = WaitlistEntry.objects.filter(email=logged_in_user.email).first()
    if waitlist_entry is None and not logged_in_user:
        return JsonResponse(
            {"error": "Waitlist session expired or missing. Please restart from the waitlist form."},
            status=400,
        )

    try:
        onboarding_defaults = {field_id: answers.get(field_id) for field_id in PROFILE_ONBOARDING_FIELD_IDS}

        # Link referral if user entered a valid code
        entered_code = str(answers.get("referral_code", "")).strip().upper()
        if entered_code and waitlist_entry is not None:
            referrer = WaitlistEntry.objects.filter(my_referral_code=entered_code).exclude(pk=waitlist_entry.pk).first()
            if referrer and not waitlist_entry.referred_by_id:
                waitlist_entry.referred_by = referrer
                waitlist_entry.save(update_fields=["referred_by"])

        response_defaults = {
            "email": (waitlist_entry.email if waitlist_entry else email) or email,
            "flow_name": flow_name[:200],
            **onboarding_defaults,
            "answers": answers,
        }

        if waitlist_entry is not None:
            onboarding_response, _ = OnboardingResponse.objects.update_or_create(
                waitlist_entry=waitlist_entry,
                defaults=response_defaults,
            )
        else:
            onboarding_response = OnboardingResponse.objects.filter(email=email).order_by("-updated_at").first()
            if onboarding_response:
                for field, value in response_defaults.items():
                    setattr(onboarding_response, field, value)
                onboarding_response.save()
            else:
                onboarding_response = OnboardingResponse.objects.create(**response_defaults)

        user = logged_in_user or User.objects.filter(email=(waitlist_entry.email if waitlist_entry else email) or email).first()
        if user:
            sync_profile_for_user(
                user,
                waitlist_entry=waitlist_entry,
                onboarding_response=onboarding_response,
                flow_name=flow_name[:200],
                answers=answers,
            )
            uploaded_profile_image = request.FILES.get("profile_image")
            remove_profile_image = str(request.POST.get("remove_profile_image", "")).strip().lower() in {"1", "true", "yes"}
            if uploaded_profile_image or remove_profile_image:
                profile, _ = Profile.objects.get_or_create(user=user)
                profile_update_fields = []
                if remove_profile_image:
                    if profile.profile_image:
                        profile.profile_image.delete(save=False)
                    profile.profile_image = None
                    profile_update_fields.append("profile_image")
                elif uploaded_profile_image:
                    if uploaded_profile_image.size > PROFILE_PHOTO_MAX_SIZE_BYTES:
                        return JsonResponse(
                            {"error": f"Profile photo must be {PROFILE_PHOTO_MAX_SIZE_MB} MB or smaller."},
                            status=400,
                        )
                    profile.profile_image = uploaded_profile_image
                    profile_update_fields.append("profile_image")
                if profile_update_fields:
                    profile.save(update_fields=profile_update_fields)
    except Exception as exc:
        details = {
            "flow_name": flow_name[:200],
            "logged_in_user_id": str(logged_in_user.id) if logged_in_user else "",
            "waitlist_entry_id": getattr(waitlist_entry, "id", ""),
            "error": str(exc),
        }
        logger.exception("Onboarding submission failed for %s", email)
        _send_onboarding_failure_alert(email, "submission_failure", details)
        return JsonResponse(
            {"error": "We could not save your onboarding right now. Please try again in a moment."},
            status=500,
        )

    return JsonResponse({"ok": True})

def loading(request):
    return render(request, 'loading.html')

def pricing(request):
    return render(request, 'pricing.html')

def features(request):
    return render(request, 'features.html')

def about(request):
    return render(request, 'about.html')
@login_required
def workspace(request):
    response = render(request, "workspace.html")
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response

@ensure_csrf_cookie
def waitlist_verify_email_send(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    email = _normalize_email(payload.get("email"))
    if not email:
        return JsonResponse({"error": "Email is required."}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "Please enter a valid email address."}, status=400)
    
    # if the email is already on the waitlist:
    if WaitlistEntry.objects.filter(email=email).exists():
        return JsonResponse({"error": "This email is already registered on CoVise."}, status=400)

    existing_verification = WaitlistEmailVerification.objects.filter(
        email=email,
        verified_at__isnull=False,
    ).first()
    if existing_verification: #If the email was verified before:
        request.session["verified_waitlist_email"] = email
        return JsonResponse(
            {
                "ok": True,
                "already_verified": True,
                "message": "Email verified. You can submit now.",
            }
        )
    email_verification = WaitlistEmailVerification.objects.filter(email=email).first()

    #If the email is not verified and new to both WaitlistEmailVerification and WaitlistEntry:
    if email_verification is None:
        email_verification = WaitlistEmailVerification.objects.create(
            email=email,
            token=uuid.uuid4(),
            verification_code=_generate_verification_code(),
        )
    #If the email is not verified and already has a WaitlistEmailVerification record (e.g. from a previous verification attempt), generate a new code and token:
    elif not email_verification.verification_code:
        email_verification.token = uuid.uuid4()
        email_verification.verification_code = _generate_verification_code()
        email_verification.verified_at = None
        email_verification.save(update_fields=["token", "verification_code", "verified_at", "updated_at"])

    try:
        _send_waitlist_verification_email(email_verification)
    except Exception as exc:
        logger.exception("Failed to send verification email for %s: %s", email, exc)
        return JsonResponse(
            {"error": "Failed to send verification email. Please try again in a moment."},
            status=500,
        )

    return JsonResponse(
        {
            "ok": True,
            "message": "A verification code was sent to your email. Enter it below before submitting.",
        }
    )


@ensure_csrf_cookie
def waitlist_verify_email_code(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    email = _normalize_email(payload.get("email"))
    code = str(payload.get("code", "")).strip()
    if not email or not code:
        return JsonResponse({"error": "Email and verification code are required."}, status=400)

    email_verification = WaitlistEmailVerification.objects.filter(email=email).first()
    if email_verification is None:
        return JsonResponse({"error": "Please request a verification code first."}, status=400)

    if email_verification.verified_at is not None:
        request.session["verified_waitlist_email"] = email
        request.session["waitlist_verification_notice"] = "Email verified. You can submit now."
        return JsonResponse({"ok": True, "message": "Email verified. You can submit now."})

    if email_verification.verification_code != code:
        return JsonResponse({"error": "Incorrect verification code. Please try again."}, status=400)

    email_verification.verified_at = timezone.now()
    email_verification.save(update_fields=["verified_at", "updated_at"])
    request.session["verified_waitlist_email"] = email
    request.session["waitlist_verification_notice"] = "Email verified. You can submit now."
    return JsonResponse({"ok": True, "message": "Email verified. You can submit now."})


@ensure_csrf_cookie
def waitlist_verified_email_abandoned(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    email = _normalize_email(request.POST.get("email"))
    if not email and request.body:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        email = _normalize_email(payload.get("email"))

    if not email:
        return JsonResponse({"ok": False, "error": "Email is required."}, status=400)

    if WaitlistEntry.objects.filter(email=email).exists():
        return JsonResponse({"ok": True, "skipped": "entry_exists"})

    verification = WaitlistEmailVerification.objects.filter(
        email=email,
        verified_at__isnull=False,
    ).first()
    if verification is None:
        return JsonResponse({"ok": True, "skipped": "not_verified"})

    if request.session.get("waitlist_abandon_alerted_email") == email:
        return JsonResponse({"ok": True, "skipped": "already_alerted"})

    request.session["waitlist_abandon_alerted_email"] = email
    _send_waitlist_abandonment_alert(email)
    return JsonResponse({"ok": True})


@ensure_csrf_cookie
def waitlist(request):
    context = {
        "initial_waitlist_email": request.session.pop(
            "waitlist_initial_email",
            request.session.get("verified_waitlist_email", ""),
        ),
        "initial_full_name": request.session.pop("waitlist_full_name", ""),
        "initial_phone_number": request.session.pop("waitlist_phone_number", ""),
        "initial_email_verification_code": request.session.pop("waitlist_email_verification_code", ""),
        "initial_verified_email": request.session.get("verified_waitlist_email", ""),
        "initial_verification_notice": request.session.pop("waitlist_verification_notice", ""),
        "initial_verification_pending_email": request.session.pop("waitlist_pending_email", ""),
        "initial_country": request.session.pop("waitlist_country", ""),
        "initial_non_gcc_business": request.session.pop("waitlist_non_gcc_business", False),
        "initial_custom_country": request.session.pop("waitlist_custom_country", ""),
        "initial_description": request.session.pop("waitlist_description", ""),
        "initial_custom_description": request.session.pop("waitlist_custom_description", ""),
        "initial_linkedin": request.session.pop("waitlist_linkedin", ""),
        "initial_no_linkedin": request.session.pop("waitlist_no_linkedin", False),
        "initial_venture_summary": request.session.pop("waitlist_venture_summary", ""),
        "initial_referral_code": request.session.pop("waitlist_referral_code", ""),
        "error_message": request.session.pop("waitlist_error_message", ""),
        "show_second_step": request.session.pop("waitlist_show_second_step", False),
    }

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = _normalize_email(request.POST.get('email'))
        email_verification_code = ''.join(ch for ch in str(request.POST.get('email_verification_code', '')) if ch.isdigit())[:6]
        country = request.POST.get('country', '').strip()
        description = request.POST.get('description', '').strip()
        custom_description = request.POST.get('custom_description', '').strip()
        entered_referral_code = request.POST.get('referral_code', '').strip().upper()
        non_gcc_business = request.POST.get('non_gcc_business') == 'on'
        no_linkedin = request.POST.get('no_linkedin') == 'on'
        custom_country = request.POST.get('custom_country', '').strip()
        linkedin = request.POST.get('linkedin', '').strip()
        venture_summary = request.POST.get('venture_summary', '').strip()
        cv_file = request.FILES.get('cv')

        def redirect_with_error(message, *, pending_email='', show_second_step=None):
            request.session["waitlist_error_message"] = message
            request.session["waitlist_full_name"] = full_name
            request.session["waitlist_phone_number"] = phone_number
            request.session["waitlist_initial_email"] = email
            request.session["waitlist_email_verification_code"] = email_verification_code
            request.session["waitlist_pending_email"] = pending_email
            request.session["waitlist_country"] = country
            request.session["waitlist_non_gcc_business"] = non_gcc_business
            request.session["waitlist_custom_country"] = custom_country
            request.session["waitlist_description"] = description
            request.session["waitlist_custom_description"] = custom_description
            request.session["waitlist_linkedin"] = linkedin
            request.session["waitlist_no_linkedin"] = no_linkedin
            request.session["waitlist_venture_summary"] = venture_summary
            request.session["waitlist_referral_code"] = entered_referral_code
            if show_second_step is None:
                show_second_step = any([
                    country,
                    custom_country,
                    description,
                    custom_description,
                    linkedin,
                    venture_summary,
                    entered_referral_code,
                    non_gcc_business,
                    no_linkedin,
                ])
            request.session["waitlist_show_second_step"] = show_second_step
            return redirect('Waitlist')

        linkedin_missing_when_required = (not no_linkedin) and (not linkedin)
        cv_missing_when_required = no_linkedin and (not cv_file)

        is_email_verified = WaitlistEmailVerification.objects.filter(
            email=email,
            verified_at__isnull=False,
        ).exists()

        if not all([full_name, phone_number, email]) or linkedin_missing_when_required or cv_missing_when_required:
            return redirect_with_error('Please complete all required fields.')
        elif non_gcc_business and not custom_country:
            return redirect_with_error('Please enter your country if you are outside the GCC.')
        elif not description:
            return redirect_with_error('Please select what best describes you.')
        elif description == 'other' and not custom_description:
            return redirect_with_error('Please tell us more if you selected Other.')
        elif entered_referral_code and not WaitlistEntry.objects.filter(my_referral_code=entered_referral_code).exists():
            return redirect_with_error('This referral code is not valid.')
        elif not is_email_verified and not email_verification_code:
            return redirect_with_error('Enter the verification code sent to your email.', pending_email=email)
        elif not is_email_verified:
            email_verification = WaitlistEmailVerification.objects.filter(email=email).first()
            if email_verification is None:
                return redirect_with_error('Please verify your email before submitting.', pending_email=email)
            if email_verification.verification_code != email_verification_code:
                return redirect_with_error('Incorrect verification code. Please try again.', pending_email=email)
            email_verification.verified_at = timezone.now()
            email_verification.save(update_fields=["verified_at", "updated_at"])
            request.session["verified_waitlist_email"] = email
            is_email_verified = True

        if is_email_verified and not non_gcc_business and not country:
            return redirect_with_error('Please select your country.')
        if is_email_verified:
            if non_gcc_business:
                country = ''
            else:
                custom_country = ''

            if description != 'other':
                custom_description = ''

            if WaitlistEntry.objects.filter(email=email).exists():
                return redirect_with_error('This email is already registered on CoVise.')

            # Upload CV before DB retry loop — file object is exhausted after first read
            cv_s3_key = None
            if cv_file:
                cv_s3_key = upload_cv_to_s3(cv_file, email)
                if cv_s3_key is None:
                    logger.warning("[waitlist] S3 upload failed for %s", email)

            referred_by = None
            if entered_referral_code:
                referred_by = WaitlistEntry.objects.filter(my_referral_code=entered_referral_code).first()



            entry = None
            for attempt in range(2):
                generated_referral_code = generate_referral_code()
                try:
                    entry = WaitlistEntry.objects.create(
                        full_name=full_name,
                        phone_number=phone_number,
                        email=email,
                        country=country,
                        non_gcc_business=non_gcc_business,
                        custom_country=custom_country,
                        description=description,
                        custom_description=custom_description,
                        linkedin=linkedin,
                        no_linkedin=no_linkedin,
                        venture_summary=venture_summary,
                        referral_code=entered_referral_code,
                        referred_by=referred_by,
                        cv_s3_key=cv_s3_key,
                        my_referral_code=generated_referral_code,
                    )
                    break
                except IntegrityError as exc:
                    error_text = _integrity_error_text(exc)

                    if (
                        "email" in error_text
                        and WaitlistEntry.objects.filter(email=email).exists()
                    ):
                        _log_waitlist_submission_failure(
                            email,
                            "duplicate_email",
                            verified_already=is_email_verified,
                            cv_uploaded=bool(cv_s3_key),
                            cv_s3_key=cv_s3_key or "",
                            extra={"attempt": attempt + 1},
                        )
                        return redirect_with_error('This email is already registered on CoVise.')

                    if "my_referral_code" in error_text:
                        logger.warning(
                            "Referral code collision while creating waitlist entry for %s on attempt %s",
                            email,
                            attempt + 1,
                        )
                        if attempt == 1:
                            _log_waitlist_submission_failure(
                                email,
                                "referral_code_collision",
                                verified_already=is_email_verified,
                                cv_uploaded=bool(cv_s3_key),
                                cv_s3_key=cv_s3_key or "",
                                extra={"attempts": attempt + 1},
                            )
                            return redirect_with_error('Temporary database issue. Please try again in a moment.')
                        continue

                    logger.exception("Unexpected integrity error while creating waitlist entry for %s", email)
                    _log_waitlist_submission_failure(
                        email,
                        "unexpected_integrity_error",
                        verified_already=is_email_verified,
                        cv_uploaded=bool(cv_s3_key),
                        cv_s3_key=cv_s3_key or "",
                        extra={"attempt": attempt + 1, "error": str(exc)},
                    )
                    return redirect_with_error('Temporary database issue. Please try again in a moment.')
                except OperationalError as exc:
                    # Handle transient DB disconnects (e.g., SSL EOF) by refreshing the connection once.
                    close_old_connections()
                    logger.warning(
                        "OperationalError while creating waitlist entry for %s on attempt %s: %s",
                        email,
                        attempt + 1,
                        exc,
                    )
                    if attempt == 1:
                        logger.exception("Failed to create waitlist entry after retry for %s", email)
                        _log_waitlist_submission_failure(
                            email,
                            "operational_error",
                            verified_already=is_email_verified,
                            cv_uploaded=bool(cv_s3_key),
                            cv_s3_key=cv_s3_key or "",
                            extra={"attempts": attempt + 1, "error": str(exc)},
                        )
                        return redirect_with_error('Temporary database issue. Please try again in a moment.')

            request.session["waitlist_email"] = email
            request.session["waitlist_entry_id"] = entry.id
            request.session["my_referral_code"] = entry.my_referral_code
            request.session.pop("waitlist_abandon_alerted_email", None)
            return redirect('Waitlist Success')

    return render(request, 'waitlist.html', context)


def waitlist_success(request):
    if not request.session.get("waitlist_entry_id"):
        return redirect('Waitlist')

    return render(request, 'waitlist_success.html', {
        'my_referral_code': request.session.get('my_referral_code', ''),
    })


def csrf_failure(request, reason=""):
    context = {"reason": reason}
    return render(request, "csrf_error.html", context, status=403)
