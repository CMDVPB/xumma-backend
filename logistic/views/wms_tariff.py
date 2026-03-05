from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status

from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHTariff, WHContactTariffOverride
from logistic.serializers.wms_tariff import WHTariffSerializer


class WHTariffViewSet(ViewSet):

    permission_classes = [IsAuthenticated]

    def list(self, request):

        company = get_user_company(request.user)

        default_tariff = (
            WHTariff.objects
            .filter(company=company, is_active=True)
            .first()
        )

        if default_tariff is None:
            default_tariff = WHTariff.objects.create(
                company=company,
                storage_mode="pallet",
                storage_per_pallet_per_day=0,
                storage_per_unit_per_day=0,
                storage_per_m2_per_day=0,
                storage_per_m3_per_day=0,               
                is_active=True,
            )

        overrides = (
            WHContactTariffOverride.objects
            .filter(company=company)
            .select_related("contact")
        )

        data = []

        for override in overrides:

            contact = override.contact

            storage_mode = (
                override.storage_mode
                if override.storage_mode
                else default_tariff.storage_mode
            )

            storage_per_pallet = (
                override.storage_per_pallet_per_day
                if override.storage_per_pallet_per_day is not None
                else default_tariff.storage_per_pallet_per_day
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
                else getattr(default_tariff, "storage_min_days", 1)
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

            data.append({
                "contact": contact.uf,
                "contact_name": contact.company_name,

                "storage_mode": storage_mode,

                "storage_per_pallet_per_day": storage_per_pallet,
                "storage_per_unit_per_day": storage_per_unit,
                "storage_per_m2_per_day": storage_per_m2,
                "storage_per_m3_per_day": storage_per_m3,

                "storage_min_days": storage_min_days,

                "inbound_per_line": inbound,
                "outbound_per_order": outbound_order,
                "outbound_per_line": outbound_line,

                "is_override": True,
            })

        serializer = WHTariffSerializer(data, many=True)

        return Response(serializer.data)


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
            "volume": "storage_per_m3_per_day",
        }

        # reset all storage prices
        for f in fields.values():
            data[f] = None

        # set the correct one
        if mode in fields:
            field = fields[mode]
            data[field] = request.data.get(field)


        override, created = WHContactTariffOverride.objects.update_or_create(
            company=company,
            contact=contact,
            defaults={
                "storage_mode": request.data.get("storage_mode"),

                "storage_per_pallet_per_day": request.data.get("storage_per_pallet_per_day"),
                "storage_per_unit_per_day": request.data.get("storage_per_unit_per_day"),
                "storage_per_m2_per_day": request.data.get("storage_per_m2_per_day"),
                "storage_per_m3_per_day": request.data.get("storage_per_m3_per_day"),

                "storage_min_days": request.data.get("storage_min_days"),

                "inbound_per_line": request.data.get("inbound_per_line"),
                "outbound_per_order": request.data.get("outbound_per_order"),
                "outbound_per_line": request.data.get("outbound_per_line"),
            }
        )

        return Response({"success": True}, status=status.HTTP_200_OK)