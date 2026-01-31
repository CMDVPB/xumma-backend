import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from cld.models import CalendarEvent
from bch.utils import get_user_company_async

logger = logging.getLogger(__name__)


class CalendarEventMixin:
    @action(detail=False)
    async def subscribe_calendar_events(self, **kwargs):
        """
        Subscribe to calendar event changes for current company
        """
        logger.info("WS Subscribed to CalendarEvent changes")

        company = await get_user_company_async(self.scope["user"])

        await self.calendar_event_change.subscribe(
            group_name=f"company_calendar_events_{company.id}"
        )

    @model_observer(CalendarEvent)
    async def calendar_event_change(self, message, **kwargs):
        """
        Send calendar event changes to client
        """
        await self.send_json({
            "type": "calendar_event",
            **message,
        })

    @calendar_event_change.serializer
    def calendar_event_serializer(self, instance, action, **kwargs):
        from cld.serializers import CalendarEventSerializer

        return {
            "action": action.value,   # create / update / delete
            "data": CalendarEventSerializer(instance).data,
        }
