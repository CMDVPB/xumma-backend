import calendar
from datetime import date
from decimal import Decimal
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Sum
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets

from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHBillingCharge, WHBillingInvoice, WHBillingInvoiceLine, WHBillingPeriod
from logistic.serializers.wms_billing import WHBillingInvoiceSerializer, WHBillingPeriodSerializer
from logistic.services.wms_billing_engine import generate_pallet_storage_billing_for_period


###### HELPER ######

def get_or_create_current_period(company):

    today = timezone.localdate()

    period = (
        WHBillingPeriod.objects
        .filter(
            company=company,
            start_date__lte=today,
            end_date__gte=today
        )
        .first()
    )

    if period:
        return period

    # create monthly period
    start = today.replace(day=1)

    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day)

    period = WHBillingPeriod.objects.create(
        company=company,
        start_date=start,
        end_date=end
    )

    return period



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
    @transaction.atomic
    def create_for_contact(self, request):

        company = get_user_company(request.user)

        contact_uf = request.data.get("contact")
        contact = get_object_or_404(Contact, uf=contact_uf)

        today = timezone.localdate()

        period = (
            WHBillingPeriod.objects
            .filter(
                company=company,
                start_date__lte=today,
                end_date__gte=today,
                is_closed=False
            )
            .first()
        )

        period = get_or_create_current_period(company)

        if not period:
            return Response({"detail": "No active billing period"}, status=400)

        if period.is_closed:
            return Response({"detail": "Billing period closed"}, status=400)

        # Generate storage charges ONLY for this contact
        generate_pallet_storage_billing_for_period(
            company=company,
            period=period,
            contact_ids=[contact.id],
        )

        charges = WHBillingCharge.objects.filter(
            company=company,
            contact=contact,
            billing_period=period,
            invoiced=False
        )

        if not charges.exists():
            return Response({"detail": "No charges to invoice"}, status=400)

        total = (
            charges.aggregate(s=Sum("total"))["s"] or Decimal("0")
        ).quantize(Decimal("0.01"))

        invoice = WHBillingInvoice.objects.create(
            company=company,
            contact=contact,
            period=period,
            total_amount=total
        )

        lines = []

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

            lines.append(line)

        return Response({
            "invoice": invoice.uf,
            "lines": len(lines),
            "total": str(total)
        })


    @action(detail=True, methods=["post"])
    def issue(self, request, uf=None):

        invoice = self.get_object()

        if invoice.status != "draft":
            return Response({"detail": "Only draft invoices can be issued"}, status=400)

        invoice.status = "issued"
        invoice.save(update_fields=["status"])

        return Response({"status": "issued"})
    
    # If view is ReadOnlyModelViewSet must add destroy:
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)