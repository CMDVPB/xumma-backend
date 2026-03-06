from decimal import Decimal
from math import ceil
from django.db import transaction
from django.utils import timezone

from logistic.models import (
    WHBillingCharge,
    WHStockLedger,
    WHTariff,
    WHContactTariffOverride,
    WHStorageBillingMode,
)


SECONDS_PER_DAY = 86400


def _resolve_tariff(company, contact):

    default = (
        WHTariff.objects
        .filter(company=company, is_active=True)
        .order_by("-created_at")
        .first()
    )

    override = (
        WHContactTariffOverride.objects
        .filter(company=company, contact=contact)
        .first()
    )

    storage_mode = override.storage_mode if override and override.storage_mode else default.storage_mode

    price = (
        override.storage_per_pallet_per_day
        if override and override.storage_per_pallet_per_day is not None
        else default.storage_per_pallet_per_day
    )

    min_days = (
        override.storage_min_days
        if override and override.storage_min_days is not None
        else default.storage_min_days
    ) or 1

    return storage_mode, Decimal(price), int(min_days)


def _days_between(start, end):
    seconds = (end - start).total_seconds()
    return ceil(seconds / SECONDS_PER_DAY)


@transaction.atomic
def generate_pallet_storage_billing_for_period(*, company, period, contact_ids=None):

    today = timezone.now()
    cutoff = min(today, timezone.make_aware(
        timezone.datetime.combine(period.end_date, timezone.datetime.max.time())
    ))

    ledger = WHStockLedger.objects.filter(
        company=company,
        created_at__lte=cutoff
    ).order_by("created_at")

    if contact_ids:
        ledger = ledger.filter(owner_id__in=contact_ids)

    owners = ledger.values_list("owner_id", flat=True).distinct()

    created = []

    for owner_id in owners:

        owner_ledger = ledger.filter(owner_id=owner_id)

        contact = owner_ledger.first().owner
        storage_mode, price, min_days = _resolve_tariff(company, contact)

        if storage_mode != WHStorageBillingMode.PALLET:
            continue

        inbound_lots = []

        for row in owner_ledger:

            delta = row.delta_pallets or 0

            if delta > 0:
                inbound_lots.append({
                    "qty": delta,
                    "start": row.created_at,
                    "remaining": delta
                })

            elif delta < 0:

                to_remove = abs(delta)

                for lot in inbound_lots:

                    if lot["remaining"] <= 0:
                        continue

                    consume = min(lot["remaining"], to_remove)

                    lot.setdefault("ship_times", []).append(
                        (consume, row.created_at)
                    )

                    lot["remaining"] -= consume
                    to_remove -= consume

                    if to_remove <= 0:
                        break

        pallet_days_total = Decimal("0")

        for lot in inbound_lots:

            start = lot["start"]

            if "ship_times" not in lot:

                days = _days_between(start, cutoff)
                days = max(days, min_days)

                pallet_days_total += Decimal(days * lot["qty"])

            else:

                for qty, ship_time in lot["ship_times"]:

                    days = _days_between(start, ship_time)
                    days = max(days, min_days)

                    pallet_days_total += Decimal(days * qty)

        WHBillingCharge.objects.filter(
            company=company,
            contact_id=owner_id,
            billing_period=period,
            charge_type=WHBillingCharge.Type.STORAGE,
            source_model="storage_period",
            source_uf=period.uf,
            invoiced=False
        ).delete()

        if pallet_days_total <= 0:
            continue

        charge = WHBillingCharge.objects.create(
            company=company,
            contact_id=owner_id,
            billing_period=period,
            charge_type=WHBillingCharge.Type.STORAGE,
            quantity=pallet_days_total,
            unit_price=price,
            unit_type="pallet_day",
            source_model="storage_period",
            source_uf=period.uf,
        )

        created.append(charge.uf)

    return created