from decimal import Decimal, InvalidOperation
from django.utils import timezone
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from abb.permissions import IsCompanyUserNotContactUser
from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHHandlingFeeType, WHInbound, WHStock, WHStockLedger
from logistic.serializers.wms_inbound import (WHInboundChargeOptionSerializer, WHInboundDetailSerializer, 
                                              WHInboundSerializer)
from logistic.services.wms_tariffs import get_effective_contact_tariff, resolve_handling_unit_price


class WHInboundViewSet(ModelViewSet):

    permission_classes = [IsAuthenticated]    
    lookup_field = "uf"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WHInboundDetailSerializer

        if self.action in ["create", "update", "partial_update"]:
            return WHInboundSerializer

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
    

class WHInboundChargePriceApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        company = request.user.company

        contact_uf = request.query_params.get("contact")
        charge_type = request.query_params.get("charge_type")
        fee_type = request.query_params.get("fee_type")
        handling_unit = request.query_params.get("handling_unit")
        raw_quantity = request.query_params.get("quantity", "0")

        if not contact_uf:
            return Response({"unit_price": "0.0000"})

        contact = Contact.objects.filter(company=company, uf=contact_uf).first()
        if not contact:
            return Response({"unit_price": "0.0000"})

        try:
            quantity = Decimal(str(raw_quantity))
        except (InvalidOperation, TypeError):
            quantity = Decimal("0")

        effective_tariff = get_effective_contact_tariff(company=company, contact=contact)

        if charge_type == "inbound_per_line":
            unit_price = effective_tariff.inbound_per_line
        elif charge_type in ["handling_loading", "handling_unloading"]:
            unit_price = resolve_handling_unit_price(
                effective_tariff=effective_tariff,
                fee_type=fee_type,
                unit=handling_unit,
                quantity=quantity,
            )
        else:
            unit_price = Decimal("0")

        return Response({
            "unit_price": f"{unit_price:.4f}"
        })
    


class WHInboundChargeOptionsApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        company = get_user_company(request.user)
        contact_uf = request.query_params.get("contact")

        if not contact_uf:
            return Response([])

        contact = Contact.objects.filter(company=company, uf=contact_uf).first()
        if not contact:
            return Response([])

        effective_tariff = get_effective_contact_tariff(company=company, contact=contact)

        result = []

        # 1) Standard inbound fee
        result.append({
            "code": "inbound_per_line",
            "label": "Inbound per line",
            "charge_type": "inbound_per_line",
            "unit_type": "line",
            "default_quantity": Decimal("1.000"),
            "default_unit_price": effective_tariff.inbound_per_line,
            "fee_type": None,
            "handling_unit": None,
        })

        # 2) Handling tiers from effective tariff
        seen_codes = set()

        for tier in effective_tariff.handling_tiers:
            code = f"handling_{tier.fee_type}_{tier.unit}"

            # avoid duplicate options when multiple tier ranges exist
            # frontend picks option first, quantity can later be adjusted
            if code in seen_codes:
                continue

            seen_codes.add(code)

            if tier.fee_type == WHHandlingFeeType.UNLOADING:
                charge_type = "handling_unloading"
                charge_label = f"Handling unloading / {tier.unit}"
            else:
                charge_type = "handling_loading"
                charge_label = f"Handling loading / {tier.unit}"

            result.append({
                "code": code,
                "label": charge_label,
                "charge_type": charge_type,
                "unit_type": tier.unit,
                "default_quantity": Decimal("1.000"),
                "default_unit_price": tier.price,
                "fee_type": tier.fee_type,
                "handling_unit": tier.unit,
            })

        # 3) Free/manual charge
        result.append({
            "code": "other",
            "label": "Other",
            "charge_type": "other",
            "unit_type": "fixed",
            "default_quantity": Decimal("1.000"),
            "default_unit_price": Decimal("0.0000"),
            "fee_type": None,
            "handling_unit": None,
        })

        serializer = WHInboundChargeOptionSerializer(result, many=True)
        return Response(serializer.data)
