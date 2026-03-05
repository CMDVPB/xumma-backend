
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from logistic.models import WHBillingCharge, WHBillingInvoice, WHBillingInvoiceLine, WHContactTariffOverride, WHPallet, WHStorageBillingMode, WHTariff


@dataclass(frozen=True)
class TariffResolved:
    storage_mode: str
    storage_per_pallet_per_day: Decimal


def _resolve_storage_tariff(company, contact) -> TariffResolved:
    """
    PALLET-only resolution for now.
    Priority:
      1) Override.storage_mode if set else default tariff.storage_mode
      2) Override.storage_per_pallet_per_day if set else default tariff.storage_per_pallet_per_day
    """
    default = (
        WHTariff.objects.filter(company=company, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not default:
        raise ValueError("No active WHTariff found for company")

    override = WHContactTariffOverride.objects.filter(company=company, contact=contact).first()

    storage_mode = (override.storage_mode if override and override.storage_mode else default.storage_mode)
    price = None
    if override and getattr(override, "storage_per_pallet_per_day", None) is not None:
        price = override.storage_per_pallet_per_day
    else:
        price = default.storage_per_pallet_per_day

    if price is None:
        price = Decimal("0")

    return TariffResolved(storage_mode=storage_mode, storage_per_pallet_per_day=Decimal(price))


def _dt_start_of_day(d):
    # timezone-aware start-of-day
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(d, time.min), tz)


def _dt_end_exclusive(d):
    # end-exclusive = start of next day
    return _dt_start_of_day(d) + timedelta(days=1)


def _days_between_exclusive(start_dt, end_dt):
    """
    Count billable days using a day-based rule:
      - we bill whole days
      - interval is [start_dt, end_dt) end-exclusive
    Implementation: floor to dates and count date boundaries.
    """
    if end_dt <= start_dt:
        return 0
    start_date = start_dt.date()
    end_date = end_dt.date()
    # if end_dt is at start-of-day, end_date is not included (end-exclusive)
    # but since end_dt is already exclusive boundary in our engine, using dates diff works:
    return (end_date - start_date).days


def _pallet_billable_interval_for_period(pallet, period_start_dt, period_end_excl_dt):
    """
    Determine a pallet's billable interval inside [period_start_dt, period_end_excl_dt).
    We consider:
      - pallet created_at: storage starts
      - pallet ended_at (if shipped/closed): storage ends (end-exclusive at ended_at)
      - if still active: ends at period_end_excl_dt
    """
    start_dt = max(pallet.created_at, period_start_dt)

    if pallet.ended_at:
        end_dt = min(pallet.ended_at, period_end_excl_dt)
    else:
        end_dt = period_end_excl_dt

    # enforce end-exclusive boundary to day start if you want "midnight count" instead.
    return start_dt, end_dt


@transaction.atomic
def generate_pallet_storage_billing_for_period(
    *,
    company,
    period: "WHBillingPeriod",
    contact_ids=None,
    create_invoice=True,
):
    """
    Generates STORAGE charges + invoice lines for PALLET billing.

    Rule (simple & common):
      - Day-based billing, end-exclusive.
      - Pallet-days = number of calendar days the pallet exists in ACTIVE interval inside the billing period.
      - We stop billing at pallet.ended_at (set when status becomes shipped/closed).
    """
    if period.is_closed:
        raise ValueError("Billing period is closed")

    # period boundaries (end-exclusive)
    period_start_dt = _dt_start_of_day(period.start_date)
    period_end_excl_dt = _dt_end_exclusive(period.end_date)

    # pick owners
    pallets_qs = WHPallet.objects.filter(company=company)
    if contact_ids:
        pallets_qs = pallets_qs.filter(owner_id__in=contact_ids)

    owner_ids = list(pallets_qs.values_list("owner_id", flat=True).distinct())

    for owner_id in owner_ids:
        contact = type(pallets_qs.model).owner.field.related_model.objects.get(pk=owner_id)  # att.Contact
        tariff = _resolve_storage_tariff(company, contact)

        # PALLET only in this engine
        if tariff.storage_mode != WHStorageBillingMode.PALLET:
            continue

        # Idempotency: remove old storage charges for this owner+period
        old_charges = WHBillingCharge.objects.filter(
            company=company,
            contact_id=owner_id,
            billing_period=period,
            charge_type=WHBillingCharge.Type.STORAGE,
            source_model="pallet_storage",
            source_uf=period.uf,
        )
        old_charge_ids = list(old_charges.values_list("id", flat=True))
        old_charges.delete()

        # If we recreate invoice, remove old lines of STORAGE for this invoice later (handled below)

        # Compute pallet-days
        owner_pallets = pallets_qs.filter(owner_id=owner_id)

        pallet_days_total = Decimal("0.000")
        contributing_pallet_ids = []

        for p in owner_pallets.iterator():
            start_dt, end_dt = _pallet_billable_interval_for_period(p, period_start_dt, period_end_excl_dt)
            days = _days_between_exclusive(start_dt, end_dt)
            if days > 0:
                pallet_days_total += Decimal(days)
                contributing_pallet_ids.append(p.id)

        unit_price = tariff.storage_per_pallet_per_day
        total = (pallet_days_total * unit_price).quantize(Decimal("0.0001"))

        # Create one STORAGE charge per owner per period (aggregated)
        # quantity here = pallet-days
        charge = WHBillingCharge.objects.create(
            company=company,
            contact_id=owner_id,
            billing_period=period,
            charge_type=WHBillingCharge.Type.STORAGE,
            quantity=pallet_days_total,
            unit_price=unit_price,
            total=total,
            source_model="pallet_storage",
            source_uf=period.uf,
        )

        if not create_invoice:
            continue

        # Create or get invoice for that owner+period
        invoice, _created = WHBillingInvoice.objects.get_or_create(
            company=company,
            contact_id=owner_id,
            period=period,
            defaults={"total_amount": Decimal("0.00"), "status": "draft"},
        )

        # Remove existing STORAGE invoice line (idempotent) + detach old charges if any
        WHBillingInvoiceLine.objects.filter(
            invoice=invoice,
            charge_type=WHBillingCharge.Type.STORAGE,
        ).delete()

        # Create invoice line
        line = WHBillingInvoiceLine.objects.create(
            invoice=invoice,
            charge_type=WHBillingCharge.Type.STORAGE,
            description=f"Storage (PALLET): pallet-days x price/day",
            quantity=pallet_days_total,
            unit_price=unit_price,
            total=total,
        )
        line.charges.add(charge)

        # Update invoice total_amount (sum all lines)
        lines_sum = (
            WHBillingInvoiceLine.objects.filter(invoice=invoice)
            .aggregate(s=Sum("total"))
            .get("s")
            or Decimal("0.00")
        )

        # invoice.total_amount is 2 decimals, so quantize accordingly
        invoice.total_amount = Decimal(lines_sum).quantize(Decimal("0.01"))
        invoice.save(update_fields=["total_amount"])