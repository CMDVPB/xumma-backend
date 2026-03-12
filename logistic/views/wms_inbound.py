from django.utils import timezone
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from abb.permissions import IsCompanyUserNotContactUser
from abb.utils import get_user_company
from logistic.models import WHInbound, WHStock, WHStockLedger
from logistic.serializers.wms_inbound import (WHInboundDetailSerializer, 
                                              WHInboundSerializer)


class WHInboundViewSet(ModelViewSet):

    permission_classes = [IsAuthenticated]    
    lookup_field = "uf"

    def get_serializer_class(self):
        print('2588', self.action)
        if self.action == "create" or self.action == "retrieve" or self.action == "partial_update":
            # print('2592',)
            return WHInboundDetailSerializer
        return WHInboundSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        return (
            WHInbound.objects
            .filter(company=user_company)
            .select_related("owner")
            .prefetch_related("inbound_lines")
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        user_company = get_user_company(self.request.user)
        serializer.save(
            company=user_company,
            created_by=self.request.user
        )
    
    # RECEIVE INBOUND   
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsCompanyUserNotContactUser])
    def receive(self, request, uf=None):
        inbound = self.get_object()

        if inbound.status == WHInbound.Status.RECEIVED:
            return Response(
                {"detail": "Inbound already received"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        inbound.status = WHInbound.Status.RECEIVED
        inbound.received_at = timezone.now()
        inbound.received_by = request.user
        inbound.save(update_fields=["status", "received_at", "received_by"])

        for line in inbound.inbound_lines.all():
            stock, _ = WHStock.objects.get_or_create(
                company=inbound.company,
                owner=inbound.owner,
                product=line.product,
                location=line.location,
                pallet_type=line.pallet_type,
                defaults=dict(
                    quantity=0,
                    pallets=0,
                    area_m2=0,
                    volume_m3=0,
                ),
            )

            stock.quantity += line.quantity or 0
            stock.pallets += line.pallets or 0
            stock.area_m2 += line.area_m2 or 0
            stock.volume_m3 += line.volume_m3 or 0
            stock.save()

            WHStockLedger.objects.create(
                company=inbound.company,
                owner=inbound.owner,
                product=line.product,
                location=line.location,
                pallet_type=line.pallet_type,
                delta_quantity=line.quantity or 0,
                delta_pallets=line.pallets or 0,
                delta_area_m2=line.area_m2 or 0,
                delta_volume_m3=line.volume_m3 or 0,
                source_type=WHStockLedger.SourceType.INBOUND,
                source_uf=inbound.uf,
                actor_user=request.user,
                movement_direction="in",
            )

        return Response({"status": "received"})