
import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from axx.models import Load, LoadEvent
from bch.utils import get_user_company_async

logger = logging.getLogger(__name__)


class LoadMixin:
    @action(detail=False)
    async def subscribe_load(self, **kwargs):
        logger.info("WS Subscribed to Load changes.")

        company = await get_user_company_async(self.scope["user"])
        group_name = f"company_{company.id}"

        logger.warning("WS subscribing socket to group → %s", group_name)

        # ✅ 1. Subscribe model observer
        await self.load_change.subscribe(group_name=group_name)

        # ✅ 2. ADD SOCKET TO CHANNELS GROUP
        await self.channel_layer.group_add(
            group_name,
            self.channel_name
        )

    # ---------- Load observer ----------
    @model_observer(Load)
    async def load_change(self, message, **kwargs):
        # print("1122", message)

        await self.send_json({
            "type": "load",
            **message
        })

    @load_change.serializer
    def load_serializer(self, instance, action, **kwargs):
        from dff.serializers.serializers_load import LoadListSerializer
        # print('5884')
        return {
            "action": action.value,
            "data": LoadListSerializer(instance).data,
        }

    # ---------- WS forwarder (for Celery) ----------

    async def forward_load(self, event):
        """
        Handles group_send(type="forward_load")
        """
        # print('5892')
        await self.send_json(event["payload"])
