from django.apps import AppConfig
import os

class BrokersystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'brokersystem'

    def ready(self):
        # prevent double-start with autoreload
        if os.environ.get("RUN_MAIN") == "true":
            from .scheduler import start_scheduler
            start_scheduler()