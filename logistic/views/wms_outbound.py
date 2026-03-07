from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Value, Case, When, DecimalField
from django.db.models.functions import Coalesce
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from abb.utils import get_user_company
from logistic.models import WHOutbound, WHStock, WHStockLedger
from logistic.serializers.wms_outbound import WHOutboundDetailSerializer, WHOutboundSerializer


class WHOutboundViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]    
    lookup_field = "uf"

    def get_serializer_class(self):
        print('4250', self.action)
        if self.action == "create" or self.action == "retrieve" or self.action == "partial_update":
            # print('2592',)
            return WHOutboundDetailSerializer
        return WHOutboundSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        qs = (WHOutbound.objects
                        .filter(
                          company=user_company)
                        .select_related("owner")
                        .prefetch_related("outbound_lines")
            )
        
        if getattr(self, "action", None) == "list":
            qs = qs.annotate(
                total_primary=Coalesce(
                    Case(
                        When(owner__contact_wh_tariff_overrides__storage_mode="unit",
                            then=Sum("outbound_lines__quantity")),
                        When(owner__contact_wh_tariff_overrides__storage_mode="pallet",
                            then=Sum("outbound_lines__pallets")),
                        When(owner__contact_wh_tariff_overrides__storage_mode="m2",
                            then=Sum("outbound_lines__area_m2")),
                        When(owner__contact_wh_tariff_overrides__storage_mode="volume",
                            then=Sum("outbound_lines__volume_m3")),
                        default=Sum("outbound_lines__quantity"),
                    ),
                    Value(0, output_field=DecimalField()),
                )
            )
        
        
        return qs.order_by('-updated_at')
    

    
    def perform_create(self, serializer):
        serializer.save(created_by_user=self.request.user)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def ship(self, request, uf=None):

        outbound = self.get_queryset().select_for_update().get(uf=uf)

        if outbound.status == "shipped":
            return Response(
                {"detail": "Outbound already shipped"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = get_user_company(request.user)

        for line in outbound.outbound_lines.all():

            stock, _ = WHStock.objects.get_or_create(
                                company=company,
                                owner=outbound.owner,
                                product=line.product,
                                location=line.location,
                                defaults={
                                    "quantity": 0,
                                    "pallets": 0,
                                    "area_m2": 0,
                                    "volume_m3": 0,
                                },
                            )

            if stock.quantity < (line.quantity or 0):
                raise ValidationError("Not enough stock")

            WHStockLedger.objects.create(
                company=company,
                owner=outbound.owner,
                product=line.product,
                location=line.location,

                delta_quantity=-(line.quantity or 0),
                delta_pallets=-(line.pallets or 0),
                delta_area_m2=-(line.area_m2 or 0),
                delta_volume_m3=-(line.volume_m3 or 0),

                source_type=WHStockLedger.SourceType.OUTBOUND,
                source_uf=outbound.uf,

                actor_user=request.user,
            )

            # Must update stock snapshot after creating the ledger row
            stock.quantity -= (line.quantity or 0)
            stock.pallets -= (line.pallets or 0)
            stock.area_m2 -= (line.area_m2 or 0)
            stock.volume_m3 -= (line.volume_m3 or 0)
            stock.save(update_fields=["quantity", "pallets", "area_m2", "volume_m3"])

        outbound.status = "shipped"
        outbound.shipped_at = timezone.now()
        outbound.save(update_fields=["status", "shipped_at"])

        return Response({"success": True}, status=status.HTTP_200_OK)
