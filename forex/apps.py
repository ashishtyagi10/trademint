from django.apps import AppConfig


class ForexConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'forex'

    def ready(self):
        print("\nForex App: Initializing...")
        try:
            # Import signals
            from . import signals  # This will register the signal handlers
            print("Forex App: Signal handlers registered successfully")
        except Exception as e:
            print(f"Forex App: Error registering signal handlers: {e}")
            import traceback
            print(traceback.format_exc())
