from django.urls import re_path
from . import consumers


websocket_urlpatterns = [
    re_path(r'ws/lobby/(?P<code>\w+)/$', consumers.LobbyConsumer.as_asgi()),
    re_path(r'ws/output/(?P<lobby_code>\w+)/$', consumers.OutputConsumer.as_asgi()),
    re_path(r'ws/hostcode/(?P<lobby_code>\w+)/$', consumers.HostCodeConsumer.as_asgi()),
]