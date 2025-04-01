"""
ASGI config for trademint project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from forex import routing as forex_routing
from thinkorswim import routing as thinkorswim_routing
from django.urls import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trademint.settings')

# Initialize Django ASGI application early to ensure the AppRegistry is populated
# before importing modules that might import ORM models.
django_asgi_app = get_asgi_application()

# Configure the application
application = ProtocolTypeRouter({
    "http": URLRouter(
        forex_routing.http_urlpatterns +
        thinkorswim_routing.http_urlpatterns +
        [
            # This needs to be last as it catches all remaining URLs
            re_path(r"", django_asgi_app),
        ]
    ),
})
