
import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from axx.models import Trip
from bch.utils import get_user_company_async

logger = logging.getLogger(__name__)


class TripMixin:
    @action(detail=False)
    async def subscribe_trip(self, **kwargs):
        logger.info(f'WS Subscribed to Trip changes.')
        company = await get_user_company_async(self.scope["user"])
        await self.trip_change.subscribe(
            group_name=f"company_{company.id}"
        )

    @model_observer(Trip)
    async def trip_change(self, message, **kwargs):
        await self.send_json({
            "type": "trip",
            **message
        })

    @trip_change.serializer
    def trip_serializer(self, instance, action, **kwargs):
        from dff.serializers.serializers_trip import TripListSerializer
        return {
            "action": action.value,
            "data": TripListSerializer(instance).data,
        }
