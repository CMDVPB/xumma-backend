import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from att.models import Contact
from bch.utils import get_user_company_async

logger = logging.getLogger(__name__)


class ContactMixin:
    @action(detail=False)
    async def subscribe_contact(self, **kwargs):
        logger.info(f'WS Subscribed to Contact changes.')
        company = await get_user_company_async(self.scope["user"])
        await self.contact_change.subscribe(
            group_name=f"company_{company.id}"
        )

    @model_observer(Contact)
    async def contact_change(self, message, **kwargs):
        await self.send_json({
            "type": "contact",
            **message
        })

    @contact_change.serializer
    def contact_serializer(self, instance, action, **kwargs):
        from dff.serializers.serializers_other import ContactSerializer
        return {
            "action": action.value,
            "data": ContactSerializer(instance).data,
        }
