import re
from django.db import transaction
from django.core.exceptions import ValidationError

from broker.models import BrokerBaseSalary, BrokerInvoice, JobLine
from broker.service import resolve_commission


def build_broker_settlement_report(company, broker, start, end):        

        job_lines = (
            JobLine.objects
            .select_related(
                "job",
                "job__customer",
                "service_type"
            )
            .filter(
                job__company=company,
                job__assigned_to=broker,
                job__created_at__date__range=[start, end]
            )
        )

        rows = []
        total_revenue = 0
        total_commission = 0

        for line in job_lines:

            revenue = line.total_net

            commission = resolve_commission(
                broker,
                company,
                line,
                line.job.created_at.date()
            )

            total_revenue += revenue
            total_commission += commission

            rows.append({
                "job_uf": line.job.uf,
                "uf": line.uf,                
                "date": line.job.created_at.date(),
                "customer": line.job.customer.company_name,
                "service": line.service_type.name,
                "quantity": line.quantity,
                "revenue": revenue,
                "commission": commission
            })

        salary = (
            BrokerBaseSalary.objects
            .filter(
                user=broker,
                company=company,
                valid_from__lte=end
            )
            .order_by("-valid_from")
            .first()
        )

        base_salary = salary.amount if salary else 0

        report = {
            "summary": {
                "base_salary": base_salary,
                "commission_total": total_commission,
                "total_income": base_salary + total_commission,
                "revenue_total": total_revenue
            },
            "rows": rows
        }

        return report


NUMBERING_RE = re.compile(r"^(?P<prefix>.*?)(?P<number>\d+)$")


def split_invoice_number(value: str):
    match = NUMBERING_RE.match(value or "")
    if not match:
        raise ValidationError(
            "Invoice number must end with digits, e.g. 1, INV-1, AB2026-001."
        )
    return match.group("prefix"), match.group("number")


def increment_invoice_number(value: str) -> str:
    prefix, numeric_part = split_invoice_number(value)
    width = len(numeric_part)
    next_number = str(int(numeric_part) + 1).zfill(width)
    return f"{prefix}{next_number}"


@transaction.atomic
def get_next_broker_invoice_number(company):
    settings = getattr(company, "company_settings", None)

    if not settings or not settings.broker_invoice_start_number:
        raise ValidationError(
            "Broker invoice start number is not configured in company settings."
        )

    last_invoice = (
        BrokerInvoice.objects
        .select_for_update()
        .filter(company=company)
        .order_by("-id")
        .first()
    )

    if not last_invoice:
        return settings.broker_invoice_start_number

    return increment_invoice_number(last_invoice.invoice_number)