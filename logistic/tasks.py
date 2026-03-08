# from xumma.celery import app

# from app.models import Company
# from logistic.models import WHBillingPeriod
# from logistic.services.wms_billing_engine import generate_pallet_storage_billing_for_period



# @app.task(bind=True)
# def run_pallet_storage_billing(self, company_id: int, period_id: int, contact_ids=None):
#     company = Company.objects.get(pk=company_id)
#     period = WHBillingPeriod.objects.get(pk=period_id, company=company)

#     generate_pallet_storage_billing_for_period(
#         company=company,
#         period=period,
#         contact_ids=contact_ids,
#         create_invoice=True,
#     )
#     return {"company_id": company_id, "period_id": period_id, "status": "ok"}