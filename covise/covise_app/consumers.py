import asyncio
import json
import time

from asgiref.sync import async_to_sync
from django.conf import settings
from channels.generic.websocket import WebsocketConsumer

from .messaging import (
    MessagingError,
    RealtimeDeliveryError,
    broadcast_chat_message,
    deliver_text_message,
    send_messaging_failure_alert,
)
from .models import Conversation


REDIS_OPERATION_RETRY_ATTEMPTS = max(1, int(getattr(settings, "REDIS_OPERATION_RETRY_ATTEMPTS", 3)))
REDIS_OPERATION_RETRY_DELAY_MS = max(0, int(getattr(settings, "REDIS_OPERATION_RETRY_DELAY_MS", 250)))


class ChatConsumer(WebsocketConsumer):
    def _retry_channel_layer_call(self, operation_name, callback, *, user=None):
        last_error = None
        for attempt in range(1, REDIS_OPERATION_RETRY_ATTEMPTS + 1):
            try:
                return callback()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < REDIS_OPERATION_RETRY_ATTEMPTS:
                    time.sleep(REDIS_OPERATION_RETRY_DELAY_MS / 1000)

        send_messaging_failure_alert(
            action=operation_name,
            reason="redis_operation_failed",
            actor=user,
            conversation=getattr(self, "conversation", None),
            details={"exception": str(last_error)},
        )
        raise last_error

    def _send_error(self, code, message):
        self.send(
            text_data=json.dumps(
                {
                    "type": "chat_error",
                    "code": code,
                    "error": message,
                }
            )
        )

    def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            self.close()
            return

        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.conversation = (
            Conversation.objects.filter(id=self.room_name, participants=user)
            .distinct()
            .first()
        )
        if not self.conversation:
            self.close()
            return

        self.room_group_name = f"chat_{self.conversation.id.hex}"
        try:
            self._retry_channel_layer_call(
                "group_add",
                lambda: async_to_sync(self.channel_layer.group_add)(
                    self.room_group_name,
                    self.channel_name,
                ),
                user=user,
            )
        except asyncio.CancelledError:
            self.close()
            return
        except Exception:
            self.close()
            return
        self.accept()

    def receive(self, text_data):
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not self.conversation:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            send_messaging_failure_alert(
                action="socket_receive",
                reason="malformed_payload",
                actor=user,
                conversation=self.conversation,
                details={"payload_preview": text_data[:300]},
            )
            self._send_error("malformed_payload", "We could not read that message. Please try again.")
            return

        try:
            send_result = deliver_text_message(
                conversation_id=self.conversation.id,
                sender=user,
                message_text=payload.get("message", ""),
            )
        except MessagingError as exc:
            send_messaging_failure_alert(
                action="send_message",
                reason=exc.code,
                actor=user,
                conversation=self.conversation,
                details=exc.details,
            )
            self._send_error(exc.code, exc.user_message)
            return
        except Exception as exc:
            send_messaging_failure_alert(
                action="send_message",
                reason="unexpected_exception",
                actor=user,
                conversation=self.conversation,
                details={"exception": str(exc)},
            )
            self._send_error("send_failed", "We could not send your message right now. Please try again.")
            return

        self.conversation = send_result["conversation"]
        message = send_result["message"]

        try:
            broadcast_chat_message(
                conversation=self.conversation,
                message=message,
                sender=user,
            )
        except asyncio.CancelledError:
            return
        except RealtimeDeliveryError as exc:
            send_messaging_failure_alert(
                action="broadcast_chat_message",
                reason=exc.code,
                actor=user,
                conversation=self.conversation,
                details=exc.details,
            )
            fallback_message = (
                "This ephemeral message could not be delivered live."
                if send_result.get("is_ephemeral")
                else "Your message was saved, but live delivery is delayed. Refresh to see it."
            )
            self._send_error(exc.code, exc.user_message or fallback_message)
        except Exception as exc:
            send_messaging_failure_alert(
                action="broadcast_chat_message",
                reason="broadcast_unexpected_exception",
                actor=user,
                conversation=self.conversation,
                details={
                    "exception": str(exc),
                    "is_ephemeral": send_result.get("is_ephemeral", False),
                },
            )
            fallback_message = (
                "This ephemeral message could not be delivered live."
                if send_result.get("is_ephemeral")
                else "Your message was saved, but live delivery is delayed. Refresh to see it."
            )
            self._send_error("broadcast_failed", fallback_message)

    def chat_message(self, event):
        self.send(text_data=json.dumps(event))

    def conversation_deleted(self, event):
        self.send(text_data=json.dumps(event))

    def message_receipts_seen(self, event):
        self.send(text_data=json.dumps(event))

    def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            try:
                self._retry_channel_layer_call(
                    "group_discard",
                    lambda: async_to_sync(self.channel_layer.group_discard)(
                        self.room_group_name,
                        self.channel_name,
                    ),
                    user=self.scope.get("user"),
                )
            except asyncio.CancelledError:
                return
            except Exception:
                return
