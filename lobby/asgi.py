# asgi.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lobby.settings')
django.setup()  # <== This MUST come before importing consumers

from django.core.asgi import get_asgi_application

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from idea import consumers  # Now it's safe to import

websocket_urlpatterns = [
    re_path(r'ws/lobby/(?P<code>\w+)/$', consumers.LobbyConsumer.as_asgi()),
    re_path(r'ws/output/(?P<lobby_code>\w+)/$', consumers.OutputConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
