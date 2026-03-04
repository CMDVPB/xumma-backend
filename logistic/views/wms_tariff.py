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

        default_tariff = WHTariff.objects.filter(
            company=company,
            is_active=True
        ).first()

        if default_tariff is None:
            default_tariff = WHTariff.objects.create(
                company=company,
                storage_per_unit_per_day=0,
                inbound_per_line=0,
                outbound_per_order=0,
                outbound_per_line=0,
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

            storage = (
                override.storage_per_unit_per_day
                if override.storage_per_unit_per_day is not None
                else default_tariff.storage_per_unit_per_day
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
                "storage_per_unit_per_day": storage,
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

        contact_uf = request.data.get("contact")

        contact = Contact.objects.get(
            company=company,
            uf=contact_uf
        )

        override, created = WHContactTariffOverride.objects.update_or_create(
            company=company,
            contact=contact,
            defaults={
                "storage_per_unit_per_day": request.data.get("storage_per_unit_per_day"),
                "inbound_per_line": request.data.get("inbound_per_line"),
                "outbound_per_order": request.data.get("outbound_per_order"),
                "outbound_per_line": request.data.get("outbound_per_line"),
            }
        )

        return Response({"success": True}, status=status.HTTP_200_OK)