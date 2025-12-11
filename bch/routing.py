from django.urls import re_path
from channelsmultiplexer import AsyncJsonWebsocketDemultiplexer
# from bch.consumers import ExpSpvConsumer, InvConsumer, NotificationUserConsumer, ItemForItemInvConsumer, SeriesConsumer, ExpConsumer


### Important: need as_asgi() ###

websocket_urlpatterns = [

    re_path(r"^ws/$", AsyncJsonWebsocketDemultiplexer.as_asgi(
        # notificationstream=NotificationUserConsumer.as_asgi(),
        # invstream=InvConsumer.as_asgi(),
        # expstream=ExpConsumer.as_asgi(),
        # expspvstream=ExpSpvConsumer.as_asgi(),
        # itemforiteminvstream=ItemForItemInvConsumer.as_asgi(),
        # seriesstream=SeriesConsumer.as_asgi(),
    )),
]
