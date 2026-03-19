from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Value, Case, When, DecimalField
from django.db.models.functions import Coalesce
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHHandlingFeeType, WHOutbound, WHStock, WHStockLedger
from logistic.serializers.wms_outbound import WHOutboundChargeOptionSerializer, WHOutboundDetailSerializer, WHOutboundListSerializer
from logistic.services.wms_tariffs import get_effective_contact_tariff, resolve_handling_price


class WHOutboundViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]    
    lookup_field = "uf"

    def get_serializer_class(self):
        if self.action == "list":
            return WHOutboundListSerializer
        return WHOutboundDetailSerializer

    def get_queryset(self):
        user_company = get_user_company(self.request.user)

        qs = (WHOutbound.objects
                        .filter(
                          company=user_company)
                        .select_related("owner")
                        .prefetch_related("outbound_lines", "outbound_charges")
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
                        When(owner__contact_wh_tariff_overrides__storage_mode="m3",
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
                pallet_type=line.pallet_type,
                defaults={
                    "quantity": 0,
                    "pallets": 0,
                    "area_m2": 0,
                    "volume_m3": 0,
                },
            )

            if stock.quantity < (line.quantity or 0):
                raise ValidationError("Not enough quantity in stock")

            if stock.pallets < (line.pallets or 0):
                raise ValidationError("Not enough pallets in stock")

            if stock.area_m2 < (line.area_m2 or 0):
                raise ValidationError("Not enough area in stock")

            if stock.volume_m3 < (line.volume_m3 or 0):
                raise ValidationError("Not enough volume in stock")

            WHStockLedger.objects.create(
                company=company,
                owner=outbound.owner,
                product=line.product,
                location=line.location,
                pallet_type=line.pallet_type,
                delta_quantity=-(line.quantity or 0),
                delta_pallets=-(line.pallets or 0),
                delta_area_m2=-(line.area_m2 or 0),
                delta_volume_m3=-(line.volume_m3 or 0),
                source_type=WHStockLedger.SourceType.OUTBOUND,
                source_uf=outbound.uf,
                actor_user=request.user,
                movement_direction="out",
            )

            stock.quantity -= (line.quantity or 0)
            stock.pallets -= (line.pallets or 0)
            stock.area_m2 -= (line.area_m2 or 0)
            stock.volume_m3 -= (line.volume_m3 or 0)
            stock.save(update_fields=["quantity", "pallets", "area_m2", "volume_m3"])

        outbound.status = "shipped"
        outbound.shipped_at = timezone.now()
        outbound.save(update_fields=["status", "shipped_at"])

        return Response({"success": True}, status=status.HTTP_200_OK)


class WHOutboundChargeOptionsApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        company = get_user_company(request.user)
        contact_uf = request.query_params.get("contact")

        if not contact_uf:
            return Response([])

        contact = Contact.objects.filter(uf=contact_uf).first()
        if not contact:
            return Response([])

        effective_tariff = get_effective_contact_tariff(
            company=company,
            contact=contact,
        )

        result = [
            {
                "code": "outbound_per_order",
                "label": "Outbound per order",
                "charge_type": "outbound_per_order",
                "unit_type": "order",
                "default_quantity": Decimal("1.000"),
                "default_unit_price": effective_tariff.outbound_per_order or Decimal("0"),
                "fee_type": None,
                "handling_unit": None,
            },
            {
                "code": "outbound_per_line",
                "label": "Outbound per line",
                "charge_type": "outbound_per_line",
                "unit_type": "line",
                "default_quantity": Decimal("1.000"),
                "default_unit_price": effective_tariff.outbound_per_line or Decimal("0"),
                "fee_type": None,
                "handling_unit": None,
            },
        ]

        seen_codes = set()

        for tier in effective_tariff.handling_tiers:
            if tier.fee_type != WHHandlingFeeType.LOADING:
                continue

            code = f"handling_{tier.fee_type}_{tier.unit}"

            if code in seen_codes:
                continue

            seen_codes.add(code)

            result.append(
                {
                    "code": code,
                    "label": f"Handling loading / {tier.unit}",
                    "charge_type": "handling_loading",
                    "unit_type": tier.unit,
                    "default_quantity": Decimal("1.000"),
                    "default_unit_price": tier.price or Decimal("0"),
                    "fee_type": tier.fee_type,
                    "handling_unit": tier.unit,
                }
            )

        result.append(
            {
                "code": "other",
                "label": "Other",
                "charge_type": "other",
                "unit_type": "fixed",
                "default_quantity": Decimal("1.000"),
                "default_unit_price": Decimal("0.0000"),
                "fee_type": None,
                "handling_unit": None,
            }
        )

        serializer = WHOutboundChargeOptionSerializer(result, many=True)
        return Response(serializer.data)


class WHOutboundChargePriceApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        company = get_user_company(request.user)

        contact_uf = request.query_params.get("contact")
        charge_type = request.query_params.get("charge_type")
        fee_type = request.query_params.get("fee_type")
        handling_unit = request.query_params.get("handling_unit")
        raw_quantity = request.query_params.get("quantity", "0")

        if not contact_uf:
            return Response({"unit_price": "0.0000"})

        contact = Contact.objects.filter(uf=contact_uf).first()
        if not contact:
            return Response({"unit_price": "0.0000"})

        try:
            quantity = Decimal(str(raw_quantity))
        except (InvalidOperation, TypeError):
            quantity = Decimal("0")

        effective_tariff = get_effective_contact_tariff(
            company=company,
            contact=contact,
        )

        if charge_type == "outbound_per_order":
            unit_price = effective_tariff.outbound_per_order or Decimal("0")

        elif charge_type == "outbound_per_line":
            unit_price = effective_tariff.outbound_per_line or Decimal("0")

        elif charge_type == "handling_loading":
            unit_price = resolve_handling_price(
                effective_tariff=effective_tariff,
                fee_type=fee_type,
                unit=handling_unit,
                quantity=quantity,
            )
        else:
            unit_price = Decimal("0")

        return Response(
            {
                "unit_price": f"{unit_price:.4f}",
            }
        )