import logging

from django.conf import settings
from django.utils import timezone
from django.utils.timesince import timesince

try:
    import resend
except ImportError:
    resend = None

from covise_app.models import Notification, UserPreference


RESEND_API_KEY = getattr(settings, "RESEND_API", "")
SITE_URL = getattr(settings, "SITE_URL", "https://covise.net").rstrip("/")
logger = logging.getLogger(__name__)

EMAIL_PREFS_BY_TYPE = {
    Notification.NotificationType.NEW_MESSAGE: "email_new_message",
    Notification.NotificationType.CONVERSATION_REQUEST: "email_connection_request",
    Notification.NotificationType.REQUEST_ACCEPTED: "email_request_accepted",
    Notification.NotificationType.POST_MENTION: "email_platform_updates",
    Notification.NotificationType.NEW_POST: "email_platform_updates",
}

IN_APP_PREFS_BY_TYPE = {
    Notification.NotificationType.NEW_MESSAGE: "in_app_new_message",
    Notification.NotificationType.CONVERSATION_REQUEST: "in_app_connection_request",
    Notification.NotificationType.REQUEST_ACCEPTED: "in_app_request_accepted",
    Notification.NotificationType.POST_MENTION: "in_app_platform_updates",
    Notification.NotificationType.NEW_POST: "in_app_platform_updates",
}


def _preferences_for(user):
    preferences = getattr(user, "preferences", None)
    if preferences is not None:
        return preferences
    preferences, _ = UserPreference.objects.get_or_create(user=user)
    return preferences


def in_app_notification_enabled(user, notification_type):
    preferences = _preferences_for(user)
    field_name = IN_APP_PREFS_BY_TYPE.get(notification_type)
    return getattr(preferences, field_name, True) if field_name else True


def email_notification_enabled(user, notification_type):
    profile = getattr(user, "profile", None)
    if profile is not None and not getattr(profile, "receive_email_notifications", True):
        return False
    preferences = _preferences_for(user)
    field_name = EMAIL_PREFS_BY_TYPE.get(notification_type)
    if field_name and not getattr(preferences, field_name, True):
        return False
    return getattr(preferences, "email_frequency", UserPreference.EmailFrequency.INSTANT) == UserPreference.EmailFrequency.INSTANT


def enabled_in_app_notification_types(user):
    return [
        notification_type
        for notification_type in IN_APP_PREFS_BY_TYPE
        if in_app_notification_enabled(user, notification_type)
    ]


def create_notification(*, recipient, actor=None, notification_type, title, body, target_url=""):
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        title=title,
        body=body,
        target_url=target_url,
    )


def _absolute_target_url(target_url):
    if not target_url:
        return f"{SITE_URL}/"
    if target_url.startswith("http://") or target_url.startswith("https://"):
        return target_url
    if not target_url.startswith("/"):
        target_url = f"/{target_url}"
    return f"{SITE_URL}{target_url}"


def _notification_email_html(notification):
    actor_name = ""
    if notification.actor_id and notification.actor:
        actor_name = notification.actor.full_name or notification.actor.email
    cta_url = _absolute_target_url(notification.target_url)
    timestamp = timezone.localtime(notification.created_at).strftime("%B %d, %Y at %I:%M %p")
    subtitle = actor_name if actor_name else "CoVise notification"
    return (
        '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 24px; color: #e2e8f0; background: #0f1117; border-radius: 12px;">'
        '<div style="text-align: center; margin-bottom: 32px;">'
        '<img src="https://logo-im-g.s3.eu-central-1.amazonaws.com/covise_logo.png" alt="CoVise" style="height: 40px; margin-bottom: 8px;">'
        '<h1 style="font-size: 28px; font-weight: 700; color: #ffffff; margin: 0;">CoVise</h1>'
        '<p style="font-size: 13px; color: #64748b; margin: 4px 0 0; letter-spacing: 0.05em;">THE FOUNDERS COMMUNITY</p>'
        "</div>"
        '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 0 0 28px;">'
        f'<p style="font-size: 12px; color: #7c8ba4; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 8px;">{subtitle}</p>'
        f'<h2 style="font-size: 24px; font-weight: 700; color: #ffffff; margin: 0 0 14px;">{notification.title}</h2>'
        f'<p style="font-size: 15px; color: #cbd5e1; margin: 0 0 18px; line-height: 1.6;">{notification.body}</p>'
        f'<p style="font-size: 13px; color: #94a3b8; margin: 0 0 22px;">Received {timestamp}</p>'
        f'<div style="margin: 0 0 28px;"><a href="{cta_url}" style="display: inline-block; padding: 13px 20px; border-radius: 999px; background: linear-gradient(135deg, #6d86d6 0%, #4b68c9 100%); color: #ffffff; font-size: 14px; font-weight: 700; text-decoration: none; letter-spacing: 0.05em;">View notification</a></div>'
        '<hr style="border: none; border-top: 1px solid rgba(255,255,255,0.06); margin: 0 0 18px;">'
        '<p style="font-size: 13px; color: #cbd5e1; margin: 0;">Log in to your CoVise account to continue the conversation.</p>'
        "</div>"
    )


def send_notification_email(notification):
    if resend is None or not RESEND_API_KEY:
        return False
    if not email_notification_enabled(notification.recipient, notification.notification_type):
        return False

    resend.api_key = RESEND_API_KEY
    payload = {
        "from": "CoVise <founders@covise.net>",
        "to": [notification.recipient.email],
        "subject": notification.title,
        "html": _notification_email_html(notification),
    }
    try:
        resend.Emails.send(payload)
    except Exception:
        logger.exception(
            "Failed to send notification email for recipient=%s type=%s",
            notification.recipient.email,
            notification.notification_type,
        )
        return False

    notification.emailed_at = timezone.now()
    notification.save(update_fields=["emailed_at"])
    return True


def dispatch_notification(*, recipient, actor=None, notification_type, title, body, target_url=""):
    notification = create_notification(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        title=title,
        body=body,
        target_url=target_url,
    )
    send_notification_email(notification)
    return notification


def serialize_notification(notification):
    actor_name = ""
    if notification.actor_id and notification.actor:
        actor_name = notification.actor.full_name or notification.actor.email
    return {
        "id": notification.id,
        "notification_type": notification.notification_type,
        "title": notification.title,
        "body": notification.body,
        "actor_name": actor_name,
        "target_url": notification.target_url,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
        "relative_time": _relative_time_label(notification.created_at),
    }


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
