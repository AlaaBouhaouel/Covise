import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from .models import Conversation, Message


class ChatConsumer(WebsocketConsumer):
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
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name,
            self.channel_name,
        )
        self.accept()

    def receive(self, text_data):
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not self.conversation:
            return

        payload = json.loads(text_data)
        message_text = str(payload.get("message", "")).strip()
        if not message_text:
            return

        message = Message.objects.create(
            conversation=self.conversation,
            sender=user,
            body=message_text,
        )
        self.conversation.last_message_at = message.created_at
        self.conversation.save(update_fields=["last_message_at"])

        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                "type": "chat_message",
                "conversation_id": str(self.conversation.id),
                "message_id": str(message.id),
                "message": message.body,
                "sender_id": str(user.id),
                "sender_name": user.full_name or user.email,
                "created_at": message.created_at.isoformat(),
            },
        )

    def chat_message(self, event):
        self.send(text_data=json.dumps(event))

    def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            async_to_sync(self.channel_layer.group_discard)(
                self.room_group_name,
                self.channel_name,
            )
