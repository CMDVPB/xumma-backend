from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from axx.models import LoadInv


@transaction.atomic
def issue_invoice(load, user, data):
    last_number = (
        LoadInv.objects
        .filter(company=load.company, status='issued')
        .select_for_update()
        .aggregate(Max('invoice_number'))
        .get('invoice_number__max')
    )

    next_number = None

    invoice = LoadInv.objects.create(
        load=load,
        company=load.company,
        invoice_number=next_number,
        issued_by=user,
        issued_date=load.date_cleared,

        amount_mdl=data['invoice_amount'],
        exchange_rate=data['exchange_rate'],
        rate_date=data['rate_date'],

        original_amount=load.freight_price,
        currency=load.currency.currency_code,
        amount_overridden=data['is_overridden'],

        status='issued',
    )

    return invoice
