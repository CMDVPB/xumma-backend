### Important ! Use Auto Save in order to keep the order of the imports ###
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xumma.settings')
django.setup()
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
import bch.routing
from .channelsmiddleware import CookieAuthMiddleware
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": ASGIStaticFilesHandler(django_asgi_app),
    'websocket': AllowedHostsOriginValidator(
        ### Updated middleware ###
        CookieAuthMiddleware(URLRouter(bch.routing.websocket_urlpatterns))
    )
})

