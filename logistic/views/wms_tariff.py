from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status

from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHContactTariffHandlingTierOverride, WHStorageBillingMode, WHTariff, WHContactTariffOverride
from logistic.serializers.wms_tariff import WHTariffSerializer


class WHTariffViewSet(ViewSet):

    permission_classes = [IsAuthenticated]

    def _get_default_tariff(self, company):
        default_tariff = (
            WHTariff.objects
            .filter(company=company, is_active=True)
            .first()
        )

        if default_tariff is None:
            default_tariff = WHTariff.objects.create(
                company=company,
                storage_mode=WHStorageBillingMode.PALLET,
                storage_per_unit_per_day=0,
                storage_per_m2_per_day=0,
                storage_per_m3_per_day=0,
                storage_per_euro_pallet_per_day=0,
                storage_per_iso2_pallet_per_day=0,
                storage_per_block_pallet_per_day=0,
                inbound_per_line=0,
                outbound_per_order=0,
                outbound_per_line=0,
                storage_min_days=1,
                handling_tier_mode="bracket",
                is_active=True,
            )

        return default_tariff

    def _extract_override_defaults(self, data):
        def empty_to_none(value):
            return None if value == "" else value

        return {
            "storage_mode": empty_to_none(data.get("storage_mode")),
            "storage_per_unit_per_day": empty_to_none(data.get("storage_per_unit_per_day")),
            "storage_per_m2_per_day": empty_to_none(data.get("storage_per_m2_per_day")),
            "storage_per_m3_per_day": empty_to_none(data.get("storage_per_m3_per_day")),
            "storage_per_euro_pallet_per_day": empty_to_none(data.get("storage_per_euro_pallet_per_day")),
            "storage_per_iso2_pallet_per_day": empty_to_none(data.get("storage_per_iso2_pallet_per_day")),
            "storage_per_block_pallet_per_day": empty_to_none(data.get("storage_per_block_pallet_per_day")),
            "storage_min_days": empty_to_none(data.get("storage_min_days")),
            "inbound_per_line": empty_to_none(data.get("inbound_per_line")),
            "outbound_per_order": empty_to_none(data.get("outbound_per_order")),
            "outbound_per_line": empty_to_none(data.get("outbound_per_line")),
            "handling_tier_mode": empty_to_none(data.get("handling_tier_mode")),
        }
    
    def _sync_handling_tier_overrides(self, override, handling_tiers):
        """
        Replace override handling tiers with submitted payload.
        Ignore incomplete rows.
        """
        WHContactTariffHandlingTierOverride.objects.filter(override=override).delete()

        def empty_to_none(value):
            return None if value in ("", None) else value

        rows_to_create = []

        for index, row in enumerate(handling_tiers or []):
            fee_type = empty_to_none(row.get("fee_type"))
            unit = empty_to_none(row.get("unit"))
            min_quantity = empty_to_none(row.get("min_quantity"))
            max_quantity = empty_to_none(row.get("max_quantity"))
            price = empty_to_none(row.get("price"))
            order = row.get("order", index)

            # skip incomplete rows
            if not fee_type or not unit or min_quantity is None or price is None:
                continue

            rows_to_create.append(
                WHContactTariffHandlingTierOverride(
                    override=override,
                    fee_type=fee_type,
                    unit=unit,
                    min_quantity=min_quantity,
                    max_quantity=max_quantity,
                    price=price,
                    order=order,
                )
            )

        if rows_to_create:
            WHContactTariffHandlingTierOverride.objects.bulk_create(rows_to_create)

    def list(self, request):
            company = get_user_company(request.user)
            default_tariff = self._get_default_tariff(company)

            overrides = (
                WHContactTariffOverride.objects
                .filter(company=company)
                .select_related("contact")
                .prefetch_related("handling_tier_overrides")
            )

            data = []

            for override in overrides:
                contact = override.contact

                storage_mode = override.storage_mode or default_tariff.storage_mode

                storage_per_euro_pallet = (
                    override.storage_per_euro_pallet_per_day
                    if override.storage_per_euro_pallet_per_day is not None
                    else default_tariff.storage_per_euro_pallet_per_day
                )

                storage_per_iso2_pallet = (
                    override.storage_per_iso2_pallet_per_day
                    if override.storage_per_iso2_pallet_per_day is not None
                    else default_tariff.storage_per_iso2_pallet_per_day
                )

                storage_per_block_pallet = (
                    override.storage_per_block_pallet_per_day
                    if override.storage_per_block_pallet_per_day is not None
                    else default_tariff.storage_per_block_pallet_per_day
                )

                storage_per_unit = (
                    override.storage_per_unit_per_day
                    if override.storage_per_unit_per_day is not None
                    else default_tariff.storage_per_unit_per_day
                )

                storage_per_m2 = (
                    override.storage_per_m2_per_day
                    if override.storage_per_m2_per_day is not None
                    else default_tariff.storage_per_m2_per_day
                )

                storage_per_m3 = (
                    override.storage_per_m3_per_day
                    if override.storage_per_m3_per_day is not None
                    else default_tariff.storage_per_m3_per_day
                )

                storage_min_days = (
                    override.storage_min_days
                    if override.storage_min_days is not None
                    else default_tariff.storage_min_days
                )

                inbound = (
                    override.inbound_per_line
                    if override.inbound_per_line is not None
                    else default_tariff.inbound_per_line
                )

                outbound_order = (
                    override.outbound_per_order
                    if override.outbound_per_order is not None
                    else default_tariff.outbound_per_order
                )

                outbound_line = (
                    override.outbound_per_line
                    if override.outbound_per_line is not None
                    else default_tariff.outbound_per_line
                )

                handling_tier_mode = (
                    override.handling_tier_mode
                    if getattr(override, "handling_tier_mode", None)
                    else default_tariff.handling_tier_mode
                )

                handling_tiers = [
                    {
                        "fee_type": tier.fee_type,
                        "unit": tier.unit,
                        "min_quantity": tier.min_quantity,
                        "max_quantity": tier.max_quantity,
                        "price": tier.price,
                        "order": tier.order,
                    }
                    for tier in override.handling_tier_overrides.all()
                ]

                data.append({
                    "contact": contact.uf,
                    "contact_name": contact.company_name,
                    "storage_mode": storage_mode,
                    "storage_per_euro_pallet_per_day": storage_per_euro_pallet,
                    "storage_per_iso2_pallet_per_day": storage_per_iso2_pallet,
                    "storage_per_block_pallet_per_day": storage_per_block_pallet,
                    "storage_per_unit_per_day": storage_per_unit,
                    "storage_per_m2_per_day": storage_per_m2,
                    "storage_per_m3_per_day": storage_per_m3,
                    "storage_min_days": storage_min_days,
                    "inbound_per_line": inbound,
                    "outbound_per_order": outbound_order,
                    "outbound_per_line": outbound_line,
                    "handling_tier_mode": handling_tier_mode,
                    "handling_tiers": handling_tiers,
                    "is_override": True,
                })

            serializer = WHTariffSerializer(data, many=True)
            return Response(serializer.data)
    
    @action(detail=True, methods=["patch"])
    @transaction.atomic
    def update_override(self, request, pk=None):
        company = get_user_company(request.user)

        contact = get_object_or_404(Contact, company=company, uf=pk)

        override, _ = WHContactTariffOverride.objects.get_or_create(
            company=company,
            contact=contact,
        )

        defaults = self._extract_override_defaults(request.data)

        for field, value in defaults.items():
            if field in request.data:
                setattr(override, field, value)

        override.save()

        if "handling_tiers" in request.data:
            self._sync_handling_tier_overrides(
                override=override,
                handling_tiers=request.data.get("handling_tiers") or [],
            )

        return Response({"status": "ok"}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=["post"])
    def create_override(self, request):

        company = get_user_company(request.user)

        data = request.data.copy()

        contact_uf = data.get("contact")

        contact = get_object_or_404(
            Contact,
            company=company,
            uf=contact_uf
        )
        
        mode = data.get("storage_mode")

        fields = {
            "pallet": "storage_per_pallet_per_day",
            "unit": "storage_per_unit_per_day",
            "m2": "storage_per_m2_per_day",
            "m3": "storage_per_m3_per_day",
        }

        # reset all storage prices
        for f in fields.values():
            data[f] = None

        # set the correct one
        if mode in fields:
            field = fields[mode]
            data[field] = data.get(field)


        override, _ = WHContactTariffOverride.objects.update_or_create(
            company=company,
            contact=contact,
            defaults = {
                "storage_mode": data.get("storage_mode"),
                "storage_per_unit_per_day": data.get("storage_per_unit_per_day"),
                "storage_per_m2_per_day": data.get("storage_per_m2_per_day"),
                "storage_per_m3_per_day": data.get("storage_per_m3_per_day"),
                "storage_per_euro_pallet_per_day": data.get("storage_per_euro_pallet_per_day"),
                "storage_per_iso2_pallet_per_day": data.get("storage_per_iso2_pallet_per_day"),
                "storage_per_block_pallet_per_day": data.get("storage_per_block_pallet_per_day"),
                "storage_min_days": data.get("storage_min_days"),
                "inbound_per_line": data.get("inbound_per_line"),
                "outbound_per_order": data.get("outbound_per_order"),
                "outbound_per_line": data.get("outbound_per_line"),
            }
        )

        return Response({"success": True}, status=status.HTTP_200_OK)