### Important ! Use Auto Save in order to keep the order of the imports ###

import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xumma.settings')
django.setup()
import bch.routing
from .channelsmiddleware import CookieAuthMiddleware
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    'websocket': AllowedHostsOriginValidator(
        ### Updated middleware ###
        CookieAuthMiddleware(URLRouter(bch.routing.websocket_urlpatterns))
    )
})
