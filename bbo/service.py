from django.utils.timezone import now
from django.db.models import F, Sum
from datetime import timedelta

from axx.models import LoadInv


def get_top_customers(days, company):
    start_date = now().date() - timedelta(days=days)

    return (
        LoadInv.objects
        .filter(
            company=company,
            status='issued',
            invoice_type='standard',
            issued_date__gte=start_date,
            load__bill_to__isnull=False,
        )
        .values(
            bill_to_id=F('load__bill_to__id'),
            bill_to_name=F('load__bill_to__company_name'),
        )
        .annotate(revenue=Sum('amount_mdl'))
        .order_by('-revenue')[:10]
    )
