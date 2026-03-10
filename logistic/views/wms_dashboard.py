from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHBillingCharge, WHStock, WHStockLedger
from logistic.serializers.wms_dashboard import WmsDashboardCustomersSummarySerializer


class WmsDashboardCustomersSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        company = get_user_company(request.user)

        days = request.query_params.get("days", 30)
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 30

        since_dt = timezone.now() - timedelta(days=days)

        # -----------------------------
        # 1) TOP REVENUE CUSTOMERS
        # -----------------------------
        revenue_rows = (
            WHBillingCharge.objects
            .filter(company=company, created_at__gte=since_dt)
            .values("contact__uf", "contact__company_name")
            .annotate(value=Coalesce(Sum("total"), Decimal("0")))
            .order_by("-value")[:10]
        )

        top_revenue_customers = [
            {
                "uf": row["contact__uf"],
                "name": row["contact__company_name"] or "-",
                "value": row["value"] or Decimal("0"),
            }
            for row in revenue_rows
        ]

        # -----------------------------
        # 2) CUSTOMERS BY PALLET USAGE
        # current stock in warehouse
        # -----------------------------
        pallet_rows = (
            WHStock.objects
            .filter(company=company, owner__isnull=False)
            .values("owner__uf", "owner__company_name")
            .annotate(value=Coalesce(Sum("pallets"), Decimal("0")))
            .filter(value__gt=0)
            .order_by("-value")[:10]
        )

        customers_by_pallet_usage = [
            {
                "uf": row["owner__uf"],
                "name": row["owner__company_name"] or "-",
                "value": row["value"] or Decimal("0"),
            }
            for row in pallet_rows
        ]

        # -----------------------------
        # 3) INACTIVE CUSTOMERS
        # customer universe = customers used in WMS
        # inactive = no ledger movement in last N days
        # -----------------------------
        customer_universe = Contact.objects.filter(
            Q(owner_wh_products__company=company) |
            Q(owner_wh_stocks__company=company) |
            Q(owner_wh_inbounds__company=company) |
            Q(owner_wh_outbounds__company=company)
        ).distinct()

        active_customer_ids = set(
            WHStockLedger.objects
            .filter(company=company, created_at__gte=since_dt)
            .values_list("owner_id", flat=True)
            .distinct()
        )

        inactive_qs = customer_universe.exclude(id__in=active_customer_ids).order_by("company_name")[:10]

        inactive_customers = [
            {
                "uf": c.uf,
                "name": c.company_name or "-",
                "value": Decimal("0"),
            }
            for c in inactive_qs
        ]

        payload = {
            "top_revenue_customers": top_revenue_customers,
            "customers_by_pallet_usage": customers_by_pallet_usage,
            "inactive_customers": inactive_customers,
        }

        serializer = WmsDashboardCustomersSummarySerializer(payload)
        return Response(serializer.data)



class WmsStorageOccupancyAPIView(APIView):

    def get(self, request):
        company = get_user_company(request.user)

        qs = (
            WHStock.objects
            .filter(company=company)
            .values("owner__id", "owner__company_name")
            .annotate(
                pallets=Sum("pallets"),
                m2=Sum("area_m2"),
                m3=Sum("volume_m3"),
                units=Sum("quantity"),
            )
            .order_by("-pallets")[:10]
        )

        data = [
            {
                "id": r["owner__id"],
                "name": r["owner__company_name"],
                "pallets": r["pallets"] or 0,
                "m2": r["m2"] or 0,
                "m3": r["m3"] or 0,
                "units": r["units"] or 0,
            }
            for r in qs
        ]

        return Response(data)