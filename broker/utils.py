from broker.models import BrokerBaseSalary, JobLine
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