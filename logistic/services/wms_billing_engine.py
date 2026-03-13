from decimal import Decimal
from datetime import timedelta
from math import ceil

from django.db import transaction
from django.utils import timezone

from logistic.models import (
    WHBillingCharge,
    WHPalletType,
    WHStockLedger,
    WHStorageBillingMode,
    WHTariff,
    WHContactTariffOverride,
)

SECONDS_PER_DAY = Decimal("86400")

MEASURE_FIELD_MAP = {
    WHStorageBillingMode.PALLET: "delta_pallets",
    WHStorageBillingMode.UNIT: "delta_quantity",
    WHStorageBillingMode.M2: "delta_area_m2",
    WHStorageBillingMode.M3: "delta_volume_m3",
}

UNIT_TYPE_MAP = {
    WHStorageBillingMode.PALLET: "pallet_day",
    WHStorageBillingMode.UNIT: "unit_day",
    WHStorageBillingMode.M2: "m2_day",
    WHStorageBillingMode.M3: "m3_day",
}


def _resolve_tariff(company, contact):
    default = (
        WHTariff.objects
        .filter(company=company, is_active=True)
        .order_by("-created_at")
        .first()
    )

    if not default:
        raise ValueError("No active warehouse tariff found")

    override = (
        WHContactTariffOverride.objects
        .filter(company=company, contact=contact)
        .first()
    )

    storage_mode = (
        override.storage_mode
        if override and override.storage_mode
        else default.storage_mode
    )

    def pick_price(field):
        if override and getattr(override, field) is not None:
            return getattr(override, field)
        return getattr(default, field)

    prices = {
        WHStorageBillingMode.UNIT: Decimal(pick_price("storage_per_unit_per_day") or 0),
        WHStorageBillingMode.M2: Decimal(pick_price("storage_per_m2_per_day") or 0),
        WHStorageBillingMode.M3: Decimal(pick_price("storage_per_m3_per_day") or 0),
        WHStorageBillingMode.PALLET: {
            WHPalletType.EURO: Decimal(pick_price("storage_per_euro_pallet_per_day") or 0),
            WHPalletType.ISO2: Decimal(pick_price("storage_per_iso2_pallet_per_day") or 0),
            WHPalletType.BLOCK: Decimal(pick_price("storage_per_block_pallet_per_day") or 0),
        },
    }

    min_days = (
        override.storage_min_days
        if override and override.storage_min_days is not None
        else default.storage_min_days
    ) or 1

    return storage_mode, prices, int(min_days)


def _period_bounds(period):
    start = timezone.make_aware(
        timezone.datetime.combine(period.start_date, timezone.datetime.min.time())
    )
    end = timezone.make_aware(
        timezone.datetime.combine(
            period.end_date + timedelta(days=1),
            timezone.datetime.min.time(),
        )
    )
    return start, end


def _days_between(start, end):
    seconds = Decimal(str((end - start).total_seconds()))
    return ceil(seconds / SECONDS_PER_DAY)


def _calculate_billed_total(rows, measure_field, start_dt, cutoff, min_days):
    """
    FIFO lot billing.

    rows must already be filtered to the exact billing dimension:
    - owner only for unit/m2/m3
    - owner + pallet_type for pallet mode
    """
    lots = []

    before_period = rows.filter(created_at__lt=start_dt)

    for row in before_period:
        delta = Decimal(getattr(row, measure_field) or 0)

        if delta > 0:
            lots.append({
                "qty": delta,
                "remaining": delta,
                "start": row.created_at,
            })
        elif delta < 0:
            to_remove = abs(delta)

            for lot in lots:
                if lot["remaining"] <= 0:
                    continue

                consume = min(lot["remaining"], to_remove)
                lot["remaining"] -= consume
                to_remove -= consume

                if to_remove <= 0:
                    break

    for lot in lots:
        if lot["remaining"] > 0 and lot["start"] < start_dt:
            lot["bill_start"] = start_dt
        else:
            lot["bill_start"] = lot["start"]

    in_period = rows.filter(created_at__gte=start_dt)

    billed_total = Decimal("0")

    for row in in_period:
        if row.created_at >= cutoff:
            break

        delta = Decimal(getattr(row, measure_field) or 0)

        if delta > 0:
            lots.append({
                "qty": delta,
                "remaining": delta,
                "start": row.created_at,
                "bill_start": row.created_at,
            })

        elif delta < 0:
            to_remove = abs(delta)

            for lot in lots:
                if lot["remaining"] <= 0:
                    continue

                consume = min(lot["remaining"], to_remove)

                days = _days_between(lot["bill_start"], row.created_at)
                days = max(days, min_days)

                billed_total += Decimal(consume) * Decimal(days)

                lot["remaining"] -= consume
                to_remove -= consume

                if to_remove <= 0:
                    break

    for lot in lots:
        if lot["remaining"] <= 0:
            continue

        days = _days_between(lot["bill_start"], cutoff)
        days = max(days, min_days)

        billed_total += Decimal(lot["remaining"]) * Decimal(days)

    return billed_total.quantize(Decimal("0.001"))


@transaction.atomic
def generate_storage_billing_for_period(*, company, period, contact_ids=None):
    """
    """

    now = timezone.now()
    start_dt, end_dt = _period_bounds(period)
    cutoff = min(now, end_dt)

    if cutoff <= start_dt:
        return []

    ledger = (
        WHStockLedger.objects
        .filter(company=company, created_at__lt=cutoff)
        .order_by("created_at", "id")
    )

    if contact_ids:
        ledger = ledger.filter(owner_id__in=contact_ids)

    owner_ids = ledger.values_list("owner_id", flat=True).distinct()

    created = []

    for owner_id in owner_ids:
        owner_ledger = ledger.filter(owner_id=owner_id)

        first_row = owner_ledger.first()
        if not first_row:
            continue

        contact = first_row.owner
        storage_mode, prices, min_days = _resolve_tariff(company, contact)
        measure_field = MEASURE_FIELD_MAP.get(storage_mode)
        unit_type = UNIT_TYPE_MAP.get(storage_mode)

        if not measure_field:
            continue

        # remove previously generated, not yet invoiced storage charges
        WHBillingCharge.objects.filter(
            company=company,
            contact_id=owner_id,
            billing_period=period,
            charge_type=WHBillingCharge.Type.STORAGE,
            source_model="storage_period",
            source_uf=period.uf,
            invoiced=False,
        ).delete()

        if storage_mode == WHStorageBillingMode.PALLET:
            pallet_prices = prices.get(WHStorageBillingMode.PALLET, {})

            for pallet_type in (
                WHPalletType.EURO,
                WHPalletType.ISO2,
                WHPalletType.BLOCK,
            ):
                price = Decimal(pallet_prices.get(pallet_type) or 0)
                if price <= 0:
                    continue

                typed_ledger = owner_ledger.filter(pallet_type=pallet_type)

                billed_total = _calculate_billed_total(
                    rows=typed_ledger,
                    measure_field="delta_pallets",
                    start_dt=start_dt,
                    cutoff=cutoff,
                    min_days=min_days,
                )

                if billed_total <= 0:
                    continue

                charge = WHBillingCharge.objects.create(
                    company=company,
                    contact_id=owner_id,
                    billing_period=period,
                    charge_type=WHBillingCharge.Type.STORAGE,
                    quantity=billed_total,
                    unit_price=price,
                    unit_type=unit_type,
                    pallet_type=pallet_type,
                    source_model="storage_period",
                    source_uf=period.uf,
                )
                created.append(charge.uf)

        else:
            price = Decimal(prices.get(storage_mode) or 0)
            if price <= 0:
                continue

            billed_total = _calculate_billed_total(
                rows=owner_ledger,
                measure_field=measure_field,
                start_dt=start_dt,
                cutoff=cutoff,
                min_days=min_days,
            )

            if billed_total <= 0:
                continue

            charge = WHBillingCharge.objects.create(
                company=company,
                contact_id=owner_id,
                billing_period=period,
                charge_type=WHBillingCharge.Type.STORAGE,
                quantity=billed_total,
                unit_price=price,
                unit_type=unit_type,
                source_model="storage_period",
                source_uf=period.uf,
            )
            created.append(charge.uf)

    return created