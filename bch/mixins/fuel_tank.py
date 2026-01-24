import logging
from djangochannelsrestframework.decorators import action
from djangochannelsrestframework.observer import model_observer

from azz.models import TankRefill, TruckFueling
from bch.serializers import FuelTankWSSerializer
from bch.utils import get_user_company_async


logger = logging.getLogger(__name__)


class FuelTankMixin:

    @action(detail=False)
    async def subscribe_fuel_tanks(self, **kwargs):
        logger.info(f'WS Subscribed to FuelTank changes.')
        company = await get_user_company_async(self.scope["user"])
        await self.tank_refill_change.subscribe(
            group_name=f"company_{company.id}"
        )
        await self.truck_fueling_change.subscribe(
            group_name=f"company_{company.id}"
        )

    @model_observer(TankRefill)
    async def tank_refill_change(self, message, **kwargs):
        await self.send_json({
            "type": "fuel_tank_update",
            **message,
        })

    @tank_refill_change.serializer
    def tank_refill_change_serializer(self, instance, action, **kwargs):
        return {
            "action": action.value,
            "data": FuelTankWSSerializer(instance.tank).data,
        }

    @model_observer(TruckFueling)
    async def truck_fueling_change(self, message, **kwargs):
        await self.send_json({
            "type": "fuel_tank_update",
            **message,
        })

    @truck_fueling_change.serializer
    def truck_fueling_change_serializer(self, instance, action, **kwargs):
        return {
            "action": action.value,
            "data": FuelTankWSSerializer(instance.tank).data,
        }

    @tank_refill_change.groups_for_signal
    def tank_refill_groups_for_signal(self, instance, **kwargs):
        yield f"company_{instance.tank.company_id}"

    @tank_refill_change.groups_for_consumer
    def tank_refill_groups_for_consumer(self, group_name=None, **kwargs):
        if group_name:
            yield group_name

    @truck_fueling_change.groups_for_signal
    def truck_fueling_groups_for_signal(self, instance, **kwargs):
        yield f"company_{instance.tank.company_id}"

    @truck_fueling_change.groups_for_consumer
    def truck_fueling_groups_for_consumer(self, group_name=None, **kwargs):
        if group_name:
            yield group_name
