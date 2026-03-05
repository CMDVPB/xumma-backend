from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Sum
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets

from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHBillingCharge, WHBillingInvoice, WHBillingInvoiceLine, WHBillingPeriod
from logistic.serializers.wms_billing import WHBillingInvoiceSerializer, WHBillingPeriodSerializer
from logistic.services.wms_billing_engine import generate_pallet_storage_billing_for_period



class WHBillingPeriodViewSet(viewsets.ModelViewSet):
    serializer_class = WHBillingPeriodSerializer
    lookup_field = "uf"

    def get_queryset(self):
        user_company = get_user_company(self.request.user)
        qs = WHBillingPeriod.objects.filter(
            company=user_company
        )
        return qs.order_by("-start_date")

    @action(detail=True, methods=["post"], url_path="run-storage")
    def run_storage_billing(self, request, uf=None):
        """
        POST /wms/billing-periods/{uf}/run-storage/
        """

        user_company = get_user_company(request.user)

        period = get_object_or_404(
            WHBillingPeriod,
            uf=uf,
            company=user_company
        )

        if period.is_closed:
            return Response(
                {"detail": "Billing period is closed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        generate_pallet_storage_billing_for_period(
            company=user_company,
            period=period
        )

        return Response(
            {"detail": "Storage billing generated"},
            status=status.HTTP_200_OK,
        )



    @action(detail=True, methods=["post"], url_path="close")
    def close_period(self, request, uf=None):

        period = self.get_object()

        if period.is_closed:
            return Response(
                {"detail": "Period already closed"},
                status=status.HTTP_400_BAD_REQUEST
            )

        period.is_closed = True
        period.save(update_fields=["is_closed"])

        return Response({"detail": "Billing period closed"})


class WHBillingInvoiceViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = WHBillingInvoiceSerializer
    lookup_field = "uf"

    def get_queryset(self):

        company = get_user_company(self.request.user)

        queryset = (
            WHBillingInvoice.objects
            .filter(company=company)
            .select_related("contact", "period")
            .prefetch_related(
                Prefetch(
                    "invoice_wh_lines",
                    queryset=WHBillingInvoiceLine.objects.all()
                )
            )
            .order_by("-created_at")
        )

        period = self.request.query_params.get("period")
        contact = self.request.query_params.get("contact")

        if period:
            queryset = queryset.filter(period__uf=period)

        if contact:
            queryset = queryset.filter(contact__uf=contact)

        return queryset
    
    
    @action(detail=False, methods=["post"], url_path="create-for-contact")
    def create_for_contact(self, request):

        user_company = get_user_company(request.user)

        contact_uf = request.data.get("contact")

        contact = Contact.objects.get(uf=contact_uf)

        charges = WHBillingCharge.objects.filter(
            company=user_company,
            contact=contact,
            invoiced=False
        )

        if not charges.exists():
            return Response({"detail": "No charges to invoice"}, status=400)

        total = charges.aggregate(
            s=Sum("total")
        )["s"]

        invoice = WHBillingInvoice.objects.create(
            company=user_company,
            contact=contact,
            total_amount=total
        )

        for charge in charges:

            line = WHBillingInvoiceLine.objects.create(
                invoice=invoice,
                charge_type=charge.charge_type,
                description=charge.charge_type,
                quantity=charge.quantity,
                unit_price=charge.unit_price,
                total=charge.total
            )

            line.charges.add(charge)

            charge.invoiced = True
            charge.save(update_fields=["invoiced"])

        return Response({"invoice": invoice.uf})
    
