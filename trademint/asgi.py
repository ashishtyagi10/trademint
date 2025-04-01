"""
ASGI config for trademint project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trademint.settings')

# Initialize Django
django.setup()

# Now we can safely import modules that use Django models
from forex.routing import http_urlpatterns, websocket_urlpatterns

# Initialize Django ASGI application early to ensure the AppRegistry is populated
# before importing modules that might import ORM models.
django_asgi_app = get_asgi_application()

# Configure the application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
