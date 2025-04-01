from django.apps import AppConfig


class ForexConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'forex'

    def ready(self):
        # Import signals
        from . import signals  # This will register the signal handlers
