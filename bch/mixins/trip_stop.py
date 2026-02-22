import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from bch.utils import get_user_company_async

logger = logging.getLogger(__name__)


class TripStopMixin:
    from driver.models import TripStop

    @action(detail=False)
    async def subscribe_trip_stop(self, **kwargs):
        logger.info(f'WS Subscribed to TripStop changes.')
        company = await get_user_company_async(self.scope["user"])
        await self.tripstop_change.subscribe(
            group_name=f"company_{company.id}"
        )

    @model_observer(TripStop)
    async def tripstop_change(self, message, **kwargs):
        await self.send_json({
            "type": "trip_stop",
            **message
        })

    @tripstop_change.serializer
    def trip_stop_serializer(self, instance, action, **kwargs):
        from driver.serializers import TripStopSerializer
        return {
            "action": action.value,
            "data": {
                **TripStopSerializer(instance).data,
                "trip_uf": instance.trip.uf,
            },
        }

    async def forward_trip_stop(self, event):
        await self.send_json(event["payload"])
