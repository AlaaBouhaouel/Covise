import json
import logging
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

try:
    import resend
except ImportError:
    resend = None

from covise_app.models import Conversation, ConversationUserState, Message, MessageReceipt, User
from covise_app.display_utils import public_display_name
from covise_app.notifications import dispatch_notification


logger = logging.getLogger(__name__)
RESEND_API_KEY = getattr(settings, "RESEND_API", "")
MESSAGING_FAILURE_ALERT_EMAIL = getattr(
    settings,
    "MESSAGING_FAILURE_ALERT_EMAIL",
    getattr(settings, "WAITLIST_FAILURE_ALERT_EMAIL", ""),
)
REDIS_OPERATION_RETRY_ATTEMPTS = max(1, int(getattr(settings, "REDIS_OPERATION_RETRY_ATTEMPTS", 3)))
REDIS_OPERATION_RETRY_DELAY_MS = max(0, int(getattr(settings, "REDIS_OPERATION_RETRY_DELAY_MS", 250)))
MAX_CHAT_MEDIA_BYTES = max(1, int(getattr(settings, "MAX_CHAT_MEDIA_BYTES", 15 * 1024 * 1024)))
ALLOWED_CHAT_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
ALLOWED_CHAT_FILE_TYPES = {
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
ALLOWED_CHAT_VOICE_TYPES = {
    "audio/webm",
    "audio/mp4",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
}


class MessagingError(Exception):
    def __init__(self, code, user_message, *, status_code=400, details=None):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.status_code = status_code
        self.details = details or {}


class RealtimeDeliveryError(Exception):
    def __init__(self, code, user_message, *, details=None):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.details = details or {}


def _is_blocked_pair(user_a, user_b):
    if not user_a or not user_b or user_a == user_b:
        return False
    return (
        user_a.blocked_relationships.filter(blocked=user_b).exists()
        or user_b.blocked_relationships.filter(blocked=user_a).exists()
    )


def _conversation_partner(conversation, current_user):
    participants = list(conversation.participants.all()[:2])
    for participant in participants:
        if participant.pk != current_user.pk:
            return participant
    return None


def _conversation_recipients(conversation, sender):
    return [participant for participant in conversation.participants.all() if participant.pk != sender.pk]


def _message_receipt_records(message):
    related = getattr(message, "receipts", None)
    if related is None:
        return []
    if hasattr(related, "all"):
        return list(related.all())
    return list(related)


def message_receipt_state_for_viewer(message, *, viewer):
    if not viewer or not getattr(message, "pk", None):
        return "sent"

    receipts = _message_receipt_records(message)
    if not receipts:
        receipts = list(MessageReceipt.objects.filter(message=message))
    if not receipts:
        return "sent"

    if getattr(message, "sender_id", None) == getattr(viewer, "id", None):
        statuses = [item.status for item in receipts]
        if statuses and all(status == MessageReceipt.Status.SEEN for status in statuses):
            return MessageReceipt.Status.SEEN
        if any(status in {MessageReceipt.Status.DELIVERED, MessageReceipt.Status.SEEN} for status in statuses):
            return MessageReceipt.Status.DELIVERED
        return "sent"

    receipt = next((item for item in receipts if item.user_id == viewer.id), None)
    return receipt.status if receipt else "sent"


def create_message_receipts(*, message, recipients):
    if not getattr(message, "pk", None) or not recipients:
        return []
    receipt_rows = [
        MessageReceipt(message=message, user=recipient, status=MessageReceipt.Status.DELIVERED)
        for recipient in recipients
        if recipient.pk != message.sender_id
    ]
    if receipt_rows:
        MessageReceipt.objects.bulk_create(receipt_rows, ignore_conflicts=True)
    return receipt_rows


def mark_conversation_seen(*, conversation, user):
    if not conversation or not user or not getattr(conversation, "pk", None):
        return []

    receipts_to_mark = list(
        MessageReceipt.objects.filter(
            message__conversation=conversation,
            user=user,
            status=MessageReceipt.Status.DELIVERED,
        )
        .exclude(message__sender=user)
        .select_related("message")
    )
    if not receipts_to_mark:
        return []

    now = timezone.now()
    receipt_ids = [item.id for item in receipts_to_mark]
    message_ids = [item.message_id for item in receipts_to_mark]
    MessageReceipt.objects.filter(id__in=receipt_ids).update(
        status=MessageReceipt.Status.SEEN,
        seen_at=now,
    )

    updated_messages = (
        Message.objects.filter(id__in=message_ids)
        .select_related("sender")
        .prefetch_related("receipts")
    )
    return [
        {
            "message_id": str(message.id),
            "receipt": message_receipt_state_for_viewer(message, viewer=message.sender),
        }
        for message in updated_messages
    ]


def _validate_conversation_sender(*, conversation_id, sender):
    if not sender or not getattr(sender, "is_authenticated", False):
        raise MessagingError("not_authenticated", "Please sign in again to continue messaging.", status_code=401)

    conversation = (
        Conversation.objects.filter(
            id=conversation_id,
            participants=sender,
        )
        .prefetch_related("participants")
        .distinct()
        .first()
    )
    if not conversation:
        raise MessagingError(
            "conversation_not_found",
            "This conversation is no longer available. Please refresh and try again.",
            status_code=404,
            details={"conversation_id": str(conversation_id)},
        )

    recipients = _conversation_recipients(conversation, sender)
    if not recipients:
        raise MessagingError(
            "conversation_invalid",
            "This conversation is not ready yet. Please refresh and try again.",
            status_code=409,
            details={"conversation_id": str(conversation.id)},
        )

    if conversation.conversation_type == Conversation.ConversationType.PRIVATE:
        partner = recipients[0] if recipients else None
        if not partner or not isinstance(partner, User):
            raise MessagingError(
                "conversation_invalid",
                "This conversation is not ready yet. Please refresh and try again.",
                status_code=409,
                details={"conversation_id": str(conversation.id)},
            )
        if _is_blocked_pair(sender, partner):
            raise MessagingError(
                "messaging_blocked",
                "You cannot send a message because one of you has blocked the other.",
                status_code=403,
                details={"partner_id": str(partner.id)},
            )

    return conversation, recipients


def _message_preview(message):
    if message.message_type == Message.MessageType.IMAGE:
        return message.body.strip() or "Sent an image"
    if message.message_type == Message.MessageType.VOICE:
        return message.body.strip() or "Sent a voice message"
    if message.message_type == Message.MessageType.FILE:
        return message.body.strip() or f"Shared {message.attachment_name or 'a file'}"
    return message.body


def _message_notification_body(message):
    preview = _message_preview(message).strip()
    return preview[:180] if preview else "New message"


def _attachment_payload(message):
    attachment_url = ""
    if getattr(message, "attachment_file", None):
        try:
            attachment_url = message.attachment_file.url
        except Exception:
            attachment_url = ""
    return {
        "attachment_url": attachment_url,
        "attachment_name": message.attachment_name or "",
        "attachment_content_type": message.attachment_content_type or "",
        "attachment_size": message.attachment_size,
    }


def _live_message_payload(*, conversation, message, sender):
    created_at = getattr(message, "created_at", None) or timezone.now()
    message_type = getattr(message, "message_type", Message.MessageType.TEXT) or Message.MessageType.TEXT
    message_id = getattr(message, "id", None)
    if not message_id:
        message_id = f"ephemeral-{int(created_at.timestamp() * 1000)}-{sender.id}"

    return {
        "conversation_id": str(conversation.id),
        "message_id": str(message_id),
        "message": getattr(message, "body", "") or "",
        "sender_id": str(sender.id),
        "sender_name": public_display_name(sender),
        "created_at": created_at.isoformat(),
        "receipt": message_receipt_state_for_viewer(message, viewer=sender),
        "message_type": message_type,
        "is_ephemeral": conversation.recording_mode == Conversation.RecordingMode.EPHEMERAL,
        **_attachment_payload(message),
    }


def _is_probable_redis_error(exc):
    error_text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        token in error_text
        for token in ("redis", "timeout", "channel layer", "connection reset", "connection refused")
    )


def _deliver_notification(*, conversation, sender, recipients, message):
    for recipient in recipients:
        try:
            if not conversation_notifications_muted(conversation=conversation, user=recipient):
                title = (
                    f"New message in {conversation.group_name or 'your group'}"
                    if conversation.conversation_type == Conversation.ConversationType.GROUP
                    else f"New message from {public_display_name(sender)}"
                )
                dispatch_notification(
                    recipient=recipient,
                    actor=sender,
                    notification_type="new_message",
                    title=title,
                    body=_message_notification_body(message),
                    target_url=f"/messages/?conversation={conversation.id}",
                )
        except Exception as exc:
            send_messaging_failure_alert(
                action="dispatch_notification",
                reason="notification_failure",
                actor=sender,
                conversation=conversation,
                target_user=recipient,
                details={"exception": str(exc), "message_id": str(message.id)},
            )


def _validate_media_upload(*, uploaded_file, requested_type, user_email=""):
    if uploaded_file is None:
        raise MessagingError(
            "missing_attachment",
            "Choose a file before sending.",
            status_code=400,
            details={"user_email": user_email or ""},
        )

    file_size = getattr(uploaded_file, "size", 0) or 0
    if file_size <= 0:
        raise MessagingError(
            "empty_attachment",
            "That file is empty. Please choose another one.",
            status_code=400,
            details={"user_email": user_email or ""},
        )
    if file_size > MAX_CHAT_MEDIA_BYTES:
        raise MessagingError(
            "attachment_too_large",
            "That file is too large to send right now.",
            status_code=400,
            details={
                "user_email": user_email or "",
                "file_size": file_size,
                "max_bytes": MAX_CHAT_MEDIA_BYTES,
            },
        )

    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    requested_type = (requested_type or "").strip().lower()

    if requested_type == Message.MessageType.VOICE or content_type in ALLOWED_CHAT_VOICE_TYPES:
        message_type = Message.MessageType.VOICE
        allowed = ALLOWED_CHAT_VOICE_TYPES
        error_message = "That voice recording format is not supported."
    elif requested_type == Message.MessageType.IMAGE or content_type in ALLOWED_CHAT_IMAGE_TYPES:
        message_type = Message.MessageType.IMAGE
        allowed = ALLOWED_CHAT_IMAGE_TYPES
        error_message = "That image format is not supported."
    else:
        message_type = Message.MessageType.FILE
        allowed = ALLOWED_CHAT_FILE_TYPES
        error_message = "That file type is not supported."

    if content_type not in allowed:
        raise MessagingError(
            "unsupported_attachment_type",
            error_message,
            status_code=400,
            details={
                "user_email": user_email or "",
                "content_type": content_type or "unknown",
            },
        )

    return message_type, content_type, file_size


def send_messaging_failure_alert(
    *,
    action,
    reason,
    actor=None,
    conversation=None,
    target_user=None,
    details=None,
):
    actor_email = getattr(actor, "email", "") if actor else ""
    conversation_id = getattr(conversation, "id", "") if conversation else ""
    target_email = getattr(target_user, "email", "") if target_user else ""
    payload_details = details or {}

    logger.warning(
        "Messaging failure: action=%s reason=%s actor=%s conversation=%s target=%s details=%s",
        action,
        reason,
        actor_email or "unknown",
        conversation_id or "unknown",
        target_email or "unknown",
        payload_details,
    )

    if resend is None or not RESEND_API_KEY or not MESSAGING_FAILURE_ALERT_EMAIL:
        return

    resend.api_key = RESEND_API_KEY
    timestamp = timezone.now().isoformat()
    html = (
        '<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; color: #e2e8f0; background: #0f1117; border-radius: 12px;">'
        '<div style="text-align: center; margin-bottom: 28px;">'
        '<img src="https://logo-im-g.s3.eu-central-1.amazonaws.com/covise_logo.png" alt="CoVise" style="height: 40px; margin-bottom: 8px;">'
        '<h1 style="font-size: 28px; font-weight: 700; color: #ffffff; margin: 0;">CoVise</h1>'
        '<p style="font-size: 13px; color: #64748b; margin: 4px 0 0; letter-spacing: 0.05em;">MESSAGING FAILURE ALERT</p>'
        "</div>"
        f'<p style="font-size: 14px; color: #cbd5e1; margin: 0 0 10px;"><strong>Action:</strong> {action}</p>'
        f'<p style="font-size: 14px; color: #cbd5e1; margin: 0 0 10px;"><strong>Reason:</strong> {reason}</p>'
        f'<p style="font-size: 14px; color: #cbd5e1; margin: 0 0 10px;"><strong>Actor:</strong> {actor_email or "unknown"}</p>'
        f'<p style="font-size: 14px; color: #cbd5e1; margin: 0 0 10px;"><strong>Target:</strong> {target_email or "unknown"}</p>'
        f'<p style="font-size: 14px; color: #cbd5e1; margin: 0 0 10px;"><strong>Conversation:</strong> {conversation_id or "unknown"}</p>'
        f'<p style="font-size: 14px; color: #cbd5e1; margin: 0 0 10px;"><strong>Date:</strong> {timestamp}</p>'
        f'<pre style="white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.5; color: #94a3b8; background: rgba(255,255,255,0.04); border-radius: 10px; padding: 14px; margin: 18px 0 0;">{json.dumps(payload_details, default=str, indent=2)}</pre>'
        "</div>"
    )
    try:
        resend.Emails.send(
            {
                "from": "CoVise Alerts <founders@covise.net>",
                "to": [MESSAGING_FAILURE_ALERT_EMAIL],
                "subject": f"Messaging failure: {action} / {reason}",
                "html": html,
            }
        )
    except Exception:
        logger.exception("Failed to send messaging failure alert email for action=%s", action)


def build_chat_message_event(*, conversation, message, sender):
    try:
        event = _live_message_payload(conversation=conversation, message=message, sender=sender)
    except Exception as exc:
        raise RealtimeDeliveryError(
            "event_build_failed",
            "We could not prepare this live message for delivery.",
            details={
                "stage": "event_build",
                "exception": str(exc),
                "is_ephemeral": conversation.recording_mode == Conversation.RecordingMode.EPHEMERAL,
            },
        ) from exc

    event["type"] = "chat_message"
    return event


def build_conversation_deleted_event(*, conversation_id, deleted_by_user_id):
    return {
        "type": "conversation_deleted",
        "conversation_id": str(conversation_id),
        "deleted_by_user_id": str(deleted_by_user_id),
    }


def build_message_receipts_seen_event(*, conversation_id, seen_by_user_id, updates):
    return {
        "type": "message_receipts_seen",
        "conversation_id": str(conversation_id),
        "seen_by_user_id": str(seen_by_user_id),
        "updates": updates,
    }


def broadcast_chat_message(*, conversation, message, sender):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    event = build_chat_message_event(conversation=conversation, message=message, sender=sender)
    channel_layer = get_channel_layer()
    if channel_layer is None:
        raise RealtimeDeliveryError(
            "channel_layer_unavailable",
            "Realtime delivery is not available right now.",
            details={
                "stage": "channel_layer",
                "is_ephemeral": conversation.recording_mode == Conversation.RecordingMode.EPHEMERAL,
            },
        )

    last_error = None
    for attempt in range(1, REDIS_OPERATION_RETRY_ATTEMPTS + 1):
        try:
            async_to_sync(channel_layer.group_send)(
                f"chat_{conversation.id.hex}",
                event,
            )
            return event
        except Exception as exc:
            last_error = exc
            if attempt < REDIS_OPERATION_RETRY_ATTEMPTS:
                time.sleep(REDIS_OPERATION_RETRY_DELAY_MS / 1000)

    error_code = "redis_broadcast_failed" if _is_probable_redis_error(last_error) else "group_send_failed"
    error_message = (
        "Live delivery is temporarily unavailable right now."
        if error_code == "redis_broadcast_failed"
        else "We could not deliver this live message right now."
    )
    raise RealtimeDeliveryError(
        error_code,
        error_message,
        details={
            "stage": "group_send",
            "exception": str(last_error),
            "is_ephemeral": conversation.recording_mode == Conversation.RecordingMode.EPHEMERAL,
        },
    ) from last_error


def broadcast_conversation_deleted(*, conversation_id, deleted_by_user_id):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    event = build_conversation_deleted_event(
        conversation_id=conversation_id,
        deleted_by_user_id=deleted_by_user_id,
    )
    channel_layer = get_channel_layer()
    if channel_layer is None:
        raise RuntimeError("Channel layer is not configured.")

    last_error = None
    for attempt in range(1, REDIS_OPERATION_RETRY_ATTEMPTS + 1):
        try:
            async_to_sync(channel_layer.group_send)(
                f"chat_{str(conversation_id).replace('-', '')}",
                event,
            )
            return event
        except Exception as exc:
            last_error = exc
            if attempt < REDIS_OPERATION_RETRY_ATTEMPTS:
                time.sleep(REDIS_OPERATION_RETRY_DELAY_MS / 1000)

    raise last_error


def broadcast_message_receipts_seen(*, conversation_id, seen_by_user_id, updates):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    event = build_message_receipts_seen_event(
        conversation_id=conversation_id,
        seen_by_user_id=seen_by_user_id,
        updates=updates,
    )
    channel_layer = get_channel_layer()
    if channel_layer is None:
        raise RuntimeError("Channel layer is not configured.")

    last_error = None
    for attempt in range(1, REDIS_OPERATION_RETRY_ATTEMPTS + 1):
        try:
            async_to_sync(channel_layer.group_send)(
                f"chat_{str(conversation_id).replace('-', '')}",
                event,
            )
            return event
        except Exception as exc:
            last_error = exc
            if attempt < REDIS_OPERATION_RETRY_ATTEMPTS:
                time.sleep(REDIS_OPERATION_RETRY_DELAY_MS / 1000)

    raise last_error


def conversation_notifications_muted(*, conversation, user):
    if not conversation or not user:
        return False
    state = next(
        (
            item
            for item in getattr(conversation, "user_states", []).all()
            if item.user_id == user.id
        ),
        None,
    ) if hasattr(getattr(conversation, "user_states", None), "all") else None
    if state is None:
        state = ConversationUserState.objects.filter(conversation=conversation, user=user).first()
    return bool(state and state.mute_notifications)


def deliver_text_message(*, conversation_id, sender, message_text):
    conversation, recipients = _validate_conversation_sender(
        conversation_id=conversation_id,
        sender=sender,
    )

    content = str(message_text or "").strip()
    if not content:
        raise MessagingError("empty_message", "Type a message before sending.", status_code=400)

    is_ephemeral = conversation.recording_mode == Conversation.RecordingMode.EPHEMERAL

    if is_ephemeral:
        message = Message(
            conversation=conversation,
            sender=sender,
            message_type=Message.MessageType.TEXT,
            body=content,
        )
        timestamp = timezone.now()
        message.created_at = timestamp
        conversation.last_message_at = timestamp
    else:
        try:
            with transaction.atomic():
                message = Message.objects.create(
                    conversation=conversation,
                    sender=sender,
                    message_type=Message.MessageType.TEXT,
                    body=content,
                )
                create_message_receipts(message=message, recipients=recipients)
                conversation.last_message_at = message.created_at
                conversation.save(update_fields=["last_message_at"])
        except Exception as exc:
            raise MessagingError(
                "message_persist_failed",
                "We could not send your message right now. Please try again.",
                status_code=500,
                details={"exception": str(exc)},
            ) from exc

    _deliver_notification(conversation=conversation, sender=sender, recipients=recipients, message=message)

    return {
        "conversation": conversation,
        "message": message,
        "recipients": recipients,
        "is_ephemeral": is_ephemeral,
    }


def deliver_media_message(*, conversation_id, sender, uploaded_file, requested_type="", caption=""):
    conversation, recipients = _validate_conversation_sender(
        conversation_id=conversation_id,
        sender=sender,
    )

    if conversation.recording_mode == Conversation.RecordingMode.EPHEMERAL:
        raise MessagingError(
            "media_requires_recording",
            "Turn chat history recording on before sending files, images, or voice notes.",
            status_code=409,
        )

    message_type, content_type, file_size = _validate_media_upload(
        uploaded_file=uploaded_file,
        requested_type=requested_type,
        user_email=getattr(sender, "email", ""),
    )

    caption = str(caption or "").strip()

    try:
        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                sender=sender,
                message_type=message_type,
                body=caption,
                attachment_file=uploaded_file,
                attachment_name=getattr(uploaded_file, "name", "")[:255],
                attachment_content_type=content_type,
                attachment_size=file_size,
            )
            create_message_receipts(message=message, recipients=recipients)
            conversation.last_message_at = message.created_at
            conversation.save(update_fields=["last_message_at"])
    except Exception as exc:
        raise MessagingError(
            "media_persist_failed",
            "We could not send that attachment right now. Please try again.",
            status_code=500,
            details={"exception": str(exc), "content_type": content_type},
        ) from exc

    _deliver_notification(conversation=conversation, sender=sender, recipients=recipients, message=message)

    return {
        "conversation": conversation,
        "message": message,
        "recipients": recipients,
        "is_ephemeral": False,
    }
