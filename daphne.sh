#!/bin/bash
export DJANGO_SETTINGS_MODULE=trademint.settings
export PYTHONPATH=/Users/atyagi/code/django/trademint:$PYTHONPATH
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear
echo "Starting Daphne..."
daphne -b localhost -p 8000 --websocket_timeout 30 --proxy-headers trademint.asgi:application