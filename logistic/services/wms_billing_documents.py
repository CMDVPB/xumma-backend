from decimal import Decimal
from django.db import transaction
from django.db.models import Sum

from logistic.models import (
    WHBillingCharge,
    WHBillingInvoice,
    WHBillingInvoiceLine,
)


def _charge_description(charge, period):
    type_map = {
        WHBillingCharge.Type.STORAGE: "Storage",
        WHBillingCharge.Type.INBOUND: "Inbound",
        WHBillingCharge.Type.OUTBOUND_ORDER: "Outbound order",
        WHBillingCharge.Type.OUTBOUND_LINE: "Outbound line",
        WHBillingCharge.Type.HANDLING_LOADING: "Handling loading",
        WHBillingCharge.Type.HANDLING_UNLOADING: "Handling unloading",
    }

    parts = [type_map.get(charge.charge_type, charge.charge_type)]

    if charge.product:
        parts.append(f"Product: {charge.product.name}")

    if charge.location:
        parts.append(f"Location: {charge.location.code}")

    parts.append(f"Period: {period.start_date} → {period.end_date}")

    return " | ".join(parts)


@transaction.atomic
def issue_billing_documents_for_period(*, company, period, contact_ids=None):
    """
    Create one billing document per contact for a selected billing period.

    Existing behavior:
    - uses already generated charges
    - creates WHBillingInvoice + WHBillingInvoiceLine
    - marks charges as invoiced=True

    Later you can rename these models to Bill/BillLine.
    """

    charges = WHBillingCharge.objects.filter(
        company=company,
        billing_period=period,
        invoiced=False,
    ).select_related("contact", "product", "location")

    if contact_ids:
        charges = charges.filter(contact_id__in=contact_ids)

    contact_id_list = list(
        charges.values_list("contact_id", flat=True).distinct()
    )

    created_documents = []

    for contact_id in contact_id_list:
        contact_charges = charges.filter(contact_id=contact_id)

        if not contact_charges.exists():
            continue

        total = (
            contact_charges.aggregate(total_sum=Sum("total"))["total_sum"]
            or Decimal("0")
        ).quantize(Decimal("0.01"))

        first_charge = contact_charges.first()

        document = WHBillingInvoice.objects.create(
            company=company,
            contact_id=contact_id,
            period=period,
            total_amount=total,
            status="draft",
        )

        for charge in contact_charges:
            description_parts = [f"{charge.charge_type}"]

            if charge.product_id and charge.product:
                description_parts.append(f"Product: {charge.product.name}")

            if charge.location_id and charge.location:
                description_parts.append(f"Location: {charge.location.code}")

            description_parts.append(
                f"Period: {period.start_date} → {period.end_date}"
            )

            line = WHBillingInvoiceLine.objects.create(
                invoice=document,
                charge_type=charge.charge_type,
                description=_charge_description(charge, period),
                quantity=charge.quantity,
                unit_price=charge.unit_price,
                total=charge.total,
            )
            line.charges.add(charge)

        contact_charges.update(invoiced=True)
        created_documents.append(document)

    return created_documents