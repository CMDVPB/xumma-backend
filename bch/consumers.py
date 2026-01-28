from rest_framework.permissions import IsAuthenticated
from djangochannelsrestframework.generics import GenericAsyncAPIConsumer
from djangochannelsrestframework.decorators import action

from bch.mixins.contact import ContactMixin
from bch.mixins.issue_document import IssueDocumentMixin
from bch.mixins.item_for_item_cost import ItemForItemCostMixin
from bch.mixins.fuel_tank import FuelTankMixin
from bch.mixins.load import LoadMixin
from bch.mixins.trip import TripMixin


class AppConsumer(
    ItemForItemCostMixin,
    FuelTankMixin,
    ContactMixin,
    TripMixin,
    LoadMixin,
    IssueDocumentMixin,
    GenericAsyncAPIConsumer,
):
    permission_classes = [IsAuthenticated]

    async def connect(self):
        await self.accept()

    @action(detail=False)
    async def ping(self, **kwargs):
        # optional: reply
        await self.send_json({"type": "pong"})
