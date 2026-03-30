from django.urls import path
from covise_app.consumers import ChatConsumer


websocket_urlpatterns = [
    path('ws/messages/<str:room_name>/', ChatConsumer.as_asgi() ),
]