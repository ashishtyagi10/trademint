from django.urls import re_path
from . import consumers

websocket_urlpatterns = []

http_urlpatterns = [
    re_path(r'thinkorswim/stream/$', consumers.ThinkOrSwimSSEConsumer.as_asgi()),
] 