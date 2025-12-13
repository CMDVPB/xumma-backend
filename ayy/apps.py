from django.apps import AppConfig


class AyyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ayy'

    def ready(self):
        import ayy.signals
