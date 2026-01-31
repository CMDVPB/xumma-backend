from django.apps import AppConfig


class CldConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cld'

    def ready(self):
        import cld.signals
