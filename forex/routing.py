from django.urls import re_path
from . import consumers

# For channel layer messages
websocket_urlpatterns = [
    re_path(r'forex/stream/$', consumers.ForexSSEConsumer.as_asgi()),
]

# For HTTP requests
http_urlpatterns = [
    re_path(r'forex/stream/$', consumers.ForexSSEConsumer.as_asgi()),
] 