from django.db.models import F
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from abb.utils import get_user_company
from logistic.models import WHStock, WHStockLedger
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
        in_stock = self.request.query_params.get("in_stock")

        if owner:
            qs = qs.filter(product__owner__uf=owner)

        if product:
            qs = qs.filter(product__uf=product)

        if location:
            qs = qs.filter(location__uf=location)

        if in_stock == "true":
            qs = qs.filter(quantity__gt=0)

        return qs.order_by(
            "product__name",
            "location__code",
        )
    
    # RECEIVE INBOUND   
    @action(
        detail=False, 
        methods=["get"], 
        permission_classes=[IsAuthenticated],
    )
    def movements(self, request):
        company = get_user_company(request.user)

        product = request.GET.get("product")
        owner = request.GET.get("owner")
        location = request.GET.get("location")

        qs = (
            WHStockLedger.objects
            .filter(company=company)
            .select_related("product", "location", "owner")
            .order_by("-created_at")
        )

        if product:
            qs = qs.filter(product__uf=product)

        if owner:
            qs = qs.filter(owner__uf=owner)

        if location:
            qs = qs.filter(location__uf=location)

        data = [
            {
                "id": x.uf,
                "product_name": x.product.name,
                "location_name": x.location.name,
                "owner_name": x.owner.company_name,
                "delta_quantity": x.delta_quantity,
                "delta_pallets": x.delta_pallets,
                "delta_m2": x.delta_area_m2,
                "delta_m3": x.delta_volume_m3,
                "movement_direction": x.movement_direction,
                "source_type": x.source_type,
                "created_at": x.created_at,
            }
            for x in qs
        ]

        return Response(data)