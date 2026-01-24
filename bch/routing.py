from django.urls import re_path

from bch.consumers import AppConsumer


### Important: need as_asgi() ###

websocket_urlpatterns = [

    re_path(r"^ws/$", AppConsumer.as_asgi()),

]
