from celery import Celery
import django
from django.conf import settings
import os

import dotenv

env_file = os.path.join(os.path.dirname(
    os.path.dirname(os.path.realpath(__file__))), '.env')
dotenv.load_dotenv(env_file)


if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xumma.settings')


# django.setup()


app = Celery("xumma")
app.config_from_object("xumma.celeryconfig")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
