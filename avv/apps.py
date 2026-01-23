from django.apps import AppConfig


class AvvConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'avv'

    def ready(self):
        import avv.signals
