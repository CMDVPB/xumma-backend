from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from logistic.models import WHStock
from logistic.serializers.wms_stock import WHStockSerializer



class WHStockViewSet(ReadOnlyModelViewSet):

    permission_classes = [IsAuthenticated]
    serializer_class = WHStockSerializer
    lookup_field = "uf"

    def get_queryset(self):
        user_company = get_user_company(self.request.user)

        qs = (
            WHStock.objects
            .filter(company=user_company)
            .select_related(
                "product",
                "product__owner",
                "location",
            )
        )

        # optional filters
        owner = self.request.query_params.get("owner")
        product = self.request.query_params.get("product")
        location = self.request.query_params.get("location")

        if owner:
            qs = qs.filter(product__owner__uf=owner)

        if product:
            qs = qs.filter(product__uf=product)

        if location:
            qs = qs.filter(location__uf=location)

        return qs.order_by(
            "product__name",
            "location__code",
        )