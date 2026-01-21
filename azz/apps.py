from django.apps import AppConfig


class AzzConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'azz'

    def ready(self):
        import azz.signals
