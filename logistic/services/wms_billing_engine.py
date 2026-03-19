from decimal import Decimal
from datetime import timedelta
from math import ceil
from django.db.models import F, Q
from django.db import transaction
from django.utils import timezone

from logistic.models import (
    WHBillingCharge,
    WHHandlingFeeType,
    WHHandlingUnit,
    WHInbound,
    WHInboundCharge,
    WHInboundLine,
    WHOutboundLine,
    WHPalletType,
    WHStockLedger,
    WHStorageBillingMode,
    WHTariff,
    WHContactTariffOverride,
    WHTierCalculationMode,
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


def _resolve_tariff(company, contact, period):
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
        .filter(
            company=company,
            contact=contact,
            is_active=True,
            period_start__lte=period.end_date,
        )
        .filter(
            Q(period_end__isnull=True) | Q(period_end__gte=period.start_date)
        )
        .order_by("-period_start", "-created_at")
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


def _get_tariff_context(company, contact, period):
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
        .filter(
            company=company,
            contact=contact,
            is_active=True,
            period_start__lte=period.end_date,
        )
        .filter(
            Q(period_end__isnull=True) | Q(period_end__gte=period.start_date)
        )
        .order_by("-period_start", "-created_at")
        .first()
    )

    return default, override


def _resolve_handling_config(company, contact, period, fee_type, unit):
    default, override = _get_tariff_context(company, contact, period)

    tier_mode = (
        override.handling_tier_mode
        if override and override.handling_tier_mode
        else default.handling_tier_mode
    )

    override_tiers_qs = None
    if override:
        override_tiers_qs = override.handling_tier_overrides.filter(
            fee_type=fee_type,
            unit=unit,
        ).order_by("min_quantity", "order")

    if override_tiers_qs and override_tiers_qs.exists():
        tiers = list(override_tiers_qs)
    else:
        tiers = list(
            default.handling_tiers.filter(
                fee_type=fee_type,
                unit=unit,
            ).order_by("min_quantity", "order")
        )

    return tier_mode, tiers


def _tier_matches(quantity, tier):
    if quantity < tier.min_quantity:
        return False

    if tier.max_quantity is not None and quantity > tier.max_quantity:
        return False

    return True


def _calculate_handling_total(quantity, tiers, tier_mode):
    quantity = Decimal(quantity or 0)

    if quantity <= 0 or not tiers:
        return Decimal("0.0000")

    if tier_mode == WHTierCalculationMode.BRACKET:
        for tier in tiers:
            if _tier_matches(quantity, tier):
                return (quantity * Decimal(tier.price)).quantize(Decimal("0.0001"))
        return Decimal("0.0000")

    # BAND = progressive
    total = Decimal("0.0000")

    for tier in tiers:
        tier_min = Decimal(tier.min_quantity)
        tier_max = Decimal(tier.max_quantity) if tier.max_quantity is not None else None

        if quantity <= tier_min:
            continue

        upper = quantity if tier_max is None else min(quantity, tier_max)
        band_qty = upper - tier_min

        if band_qty > 0:
            total += band_qty * Decimal(tier.price)

        if tier_max is None or quantity <= tier_max:
            break

    return total.quantize(Decimal("0.0001"))


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
def regenerate_storage_billing_for_period(*, company, period, contact_ids=None):
    locked_qs = WHBillingCharge.objects.filter(
        company=company,
        billing_period=period,
        charge_type=WHBillingCharge.Type.STORAGE,
        invoiced=True,
    )

    if contact_ids:
        locked_qs = locked_qs.filter(contact_id__in=contact_ids)

    if locked_qs.exists():
        raise ValueError(
            "Cannot regenerate storage charges because some storage charges are already billed."
        )

    qs = WHBillingCharge.objects.filter(
        company=company,
        billing_period=period,
        charge_type=WHBillingCharge.Type.STORAGE,
        invoiced=False,
    )

    if contact_ids:
        qs = qs.filter(contact_id__in=contact_ids)

    qs.delete()

    return generate_storage_billing_for_period(
        company=company,
        period=period,
        contact_ids=contact_ids,
    )


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
        storage_mode, prices, min_days = _resolve_tariff(company, contact, period)
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


@transaction.atomic
def regenerate_handling_billing_for_period(*, company, period, contact_ids=None):
    locked_qs = WHBillingCharge.objects.filter(
        company=company,
        billing_period=period,
        charge_type__in=[
            WHBillingCharge.Type.HANDLING_LOADING,
            WHBillingCharge.Type.HANDLING_UNLOADING,
        ],
        invoiced=True,
    )

    if contact_ids:
        locked_qs = locked_qs.filter(contact_id__in=contact_ids)

    if locked_qs.exists():
        raise ValueError(
            "Cannot regenerate handling charges because some handling charges are already billed."
        )

    qs = WHBillingCharge.objects.filter(
        company=company,
        billing_period=period,
        charge_type__in=[
            WHBillingCharge.Type.HANDLING_LOADING,
            WHBillingCharge.Type.HANDLING_UNLOADING,
        ],
        invoiced=False,
    )

    if contact_ids:
        qs = qs.filter(contact_id__in=contact_ids)

    qs.delete()

    return generate_handling_billing_for_period(
        company=company,
        period=period,
        contact_ids=contact_ids,
    )


@transaction.atomic
def generate_handling_billing_for_period(*, company, period, contact_ids=None):
    start_dt, end_dt = _period_bounds(period)
    created = []

    # INBOUND => UNLOADING
    inbound_lines = (
        WHInboundLine.objects
        .select_related("inbound", "product", "location")
        .filter(
            inbound__company=company,
            inbound__status="received",
            inbound__received_at__gte=start_dt,
            inbound__received_at__lt=end_dt,
        )
        .order_by("id")
    )

    if contact_ids:
        inbound_lines = inbound_lines.filter(inbound__owner_id__in=contact_ids)

    for line in inbound_lines:
        contact = line.inbound.owner

        for unit, qty in (
            (WHHandlingUnit.PALLET, line.pallets),
            (WHHandlingUnit.M3, line.volume_m3),
        ):
            qty = Decimal(qty or 0)
            if qty <= 0:
                continue

            tier_mode, tiers = _resolve_handling_config(
                company=company,
                contact=contact,
                period=period,
                fee_type=WHHandlingFeeType.UNLOADING,
                unit=unit,
            )

            if not tiers:
                continue

            total = _calculate_handling_total(qty, tiers, tier_mode)
            if total <= 0:
                continue

            unit_price = (total / qty).quantize(Decimal("0.0001"))

            charge, _ = WHBillingCharge.objects.update_or_create(
                company=company,
                contact=contact,
                billing_period=period,
                charge_type=WHBillingCharge.Type.HANDLING_UNLOADING,
                source_model="inbound_line_handling",
                source_uf=line.uf,
                unit_type=unit,
                pallet_type=None,
                defaults={
                    "quantity": qty,
                    "unit_price": unit_price,
                    "product": line.product,
                    "location": line.location,
                    "invoiced": False,
                },
            )
            created.append(charge.uf)

    # OUTBOUND => LOADING
    outbound_lines = (
        WHOutboundLine.objects
        .select_related("outbound", "product", "location")
        .filter(
            outbound__company=company,
            outbound__status="shipped",
            outbound__shipped_at__gte=start_dt,
            outbound__shipped_at__lt=end_dt,
        )
        .order_by("id")
    )

    if contact_ids:
        outbound_lines = outbound_lines.filter(outbound__owner_id__in=contact_ids)

    for line in outbound_lines:
        contact = line.outbound.owner

        for unit, qty in (
            (WHHandlingUnit.PALLET, line.pallets),
            (WHHandlingUnit.M3, line.volume_m3),
        ):
            qty = Decimal(qty or 0)
            if qty <= 0:
                continue

            tier_mode, tiers = _resolve_handling_config(
                company=company,
                contact=contact,
                period=period,
                fee_type=WHHandlingFeeType.LOADING,
                unit=unit,
            )

            if not tiers:
                continue

            total = _calculate_handling_total(qty, tiers, tier_mode)
            if total <= 0:
                continue

            unit_price = (total / qty).quantize(Decimal("0.0001"))

            charge, _ = WHBillingCharge.objects.update_or_create(
                company=company,
                contact=contact,
                billing_period=period,
                charge_type=WHBillingCharge.Type.HANDLING_LOADING,
                source_model="outbound_line_handling",
                source_uf=line.uf,
                unit_type=unit,
                pallet_type=None,
                defaults={
                    "quantity": qty,
                    "unit_price": unit_price,
                    "product": line.product,
                    "location": line.location,
                    "invoiced": False,
                },
            )
            created.append(charge.uf)

    return created


@transaction.atomic
def regenerate_all_billing_charges_for_period(*, company, period, contact_ids=None):
    storage_created = regenerate_storage_billing_for_period(
        company=company,
        period=period,
        contact_ids=contact_ids,
    )

    handling_created = regenerate_handling_billing_for_period(
        company=company,
        period=period,
        contact_ids=contact_ids,
    )

    inbound_extra_created = regenerate_inbound_extra_charges_for_period(
        company=company,
        period=period,
        contact_ids=contact_ids,
    )    

    return {
        "storage": storage_created,
        "handling": handling_created,
        "inbound_extra": inbound_extra_created,
        "created_count": len(storage_created) + len(handling_created),
    }


@transaction.atomic
def generate_inbound_extra_charges_for_period(*, company, period, contact_ids=None):
    start_dt, end_dt = _period_bounds(period)
    created = []

    inbound_charges = (
        WHInboundCharge.objects
        .select_related("inbound")
        .filter(
            inbound__company=company,
            inbound__status=WHInbound.Status.RECEIVED,
            inbound__received_at__gte=start_dt,
            inbound__received_at__lt=end_dt,
        )
        .order_by("id")
    )

    if contact_ids:
        inbound_charges = inbound_charges.filter(inbound__owner_id__in=contact_ids)

    for extra in inbound_charges:
        inbound = extra.inbound
        contact = inbound.owner

        if extra.charge_type == "handling_unloading":
            billing_charge_type = WHBillingCharge.Type.HANDLING_UNLOADING
        elif extra.charge_type == "handling_loading":
            billing_charge_type = WHBillingCharge.Type.HANDLING_LOADING
        elif extra.charge_type == "inbound_per_line":
            billing_charge_type = WHBillingCharge.Type.INBOUND
        else:
            billing_charge_type = WHBillingCharge.Type.MANUAL

        charge, _ = WHBillingCharge.objects.update_or_create(
            company=company,
            contact=contact,
            billing_period=period,
            charge_type=billing_charge_type,
            source_model="inbound_charge",
            source_uf=extra.uf,
            unit_type=extra.unit_type,
            pallet_type=None,
            defaults={
                "quantity": extra.quantity,
                "unit_price": extra.unit_price,
                "invoiced": False,
            },
        )

        created.append(charge.uf)

    return created


@transaction.atomic
def regenerate_inbound_extra_charges_for_period(*, company, period, contact_ids=None):
    locked_qs = WHBillingCharge.objects.filter(
        company=company,
        billing_period=period,
        source_model="inbound_charge",
        invoiced=True,
    )

    if contact_ids:
        locked_qs = locked_qs.filter(contact_id__in=contact_ids)

    if locked_qs.exists():
        raise ValueError(
            "Cannot regenerate inbound extra charges because some charges are already billed."
        )

    qs = WHBillingCharge.objects.filter(
        company=company,
        billing_period=period,
        source_model="inbound_charge",
        invoiced=False,
    )

    if contact_ids:
        qs = qs.filter(contact_id__in=contact_ids)

    qs.delete()

    return generate_inbound_extra_charges_for_period(
        company=company,
        period=period,
        contact_ids=contact_ids,
    )