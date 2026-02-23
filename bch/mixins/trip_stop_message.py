import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from bch.utils import get_user_company_async
from driver.models import TripStopMessage

logger = logging.getLogger(__name__)


class TripStopMessageMixin:

    @action(detail=False)
    async def subscribe_trip_stop_messages(self, **kwargs):
        logger.info("WS Subscribed to TripStopMessage changes.")
        company = await get_user_company_async(self.scope["user"])

        await self.tripstopmessage_change.subscribe(
            group_name=f"company_{company.id}"
        )

    @model_observer(TripStopMessage)
    async def tripstopmessage_change(self, message, **kwargs):
        await self.send_json({
            "type": "trip_stop_message",
            **message,
        })

    @tripstopmessage_change.serializer
    def trip_stop_message_serializer(self, instance, action, **kwargs):
        from driver.serializers import TripStopMessageSerializer

        return {
            "action": action.value,     # created / updated / deleted
            "data": {
                **TripStopMessageSerializer(instance).data,
                "trip_stop_uf": instance.trip_stop.uf,   # CRITICAL FOR CLIENT
                "sender_role": instance.sender.groups.filter(name="level_driver").exists()
                and "driver" or "dispatcher"
            },
        }

    async def forward_trip_stop_messages_read(self, event):
        await self.send_json(event["payload"])
