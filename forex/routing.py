from django.urls import re_path
from . import consumers

websocket_urlpatterns = []

http_urlpatterns = [
    re_path(r'forex/stream/$', consumers.ForexSSEConsumer.as_asgi()),
] 