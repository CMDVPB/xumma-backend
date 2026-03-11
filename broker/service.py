from decimal import Decimal
from django.db.models import Q
from broker.models import BrokerCommission, BrokerCommissionType


def resolve_commission(user, company, job_line, job_date):
    rule = (
        BrokerCommission.objects
        .filter(
            user=user,
            company=company,
            valid_from__lte=job_date,
        )
        .filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=job_date)
        )
       .filter(
            Q(service_type=job_line.service_type) | Q(service_type__isnull=True)
        )
       .filter(
            Q(customer=job_line.job.customer) | Q(customer__isnull=True)
        )
        .order_by(
            "-customer",
            "-service_type"
        )
        .first()
    )


    if not rule:
        return Decimal("0")

    # choose commission base
    if rule.type == BrokerCommissionType.INCL_VAT:
        revenue = job_line.total_net
    else:
        vat_multiplier = Decimal("1") + (job_line.vat_percent / Decimal("100"))
        revenue = (job_line.total_net / vat_multiplier)

    commission = (revenue * rule.value / Decimal("100")).quantize(Decimal("0.01"))

    return commission