import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from ayy.models import ItemForItemCost
from bch.utils import get_user_company_async

logger = logging.getLogger(__name__)


class ItemForItemCostMixin:
    @action(detail=False)
    async def subscribe_item_for_item_cost(self, **kwargs):
        logger.info(f'WS Subscribed to ItemForItemCost changes.')
        company = await get_user_company_async(self.scope["user"])
        await self.item_for_item_cost_change.subscribe(
            group_name=f"company_{company.id}"
        )

    @model_observer(ItemForItemCost)
    async def item_for_item_cost_change(self, message, **kwargs):
        await self.send_json({
            "type": "item_for_item_cost",
            **message
        })

    @item_for_item_cost_change.serializer
    def item_for_item_inv_cost_serializer(self, instance, action, **kwargs):
        from dff.serializers.serializers_item_inv import ItemForItemCostSerializer
        return {
            "action": action.value,
            "data": ItemForItemCostSerializer(instance).data,
        }
