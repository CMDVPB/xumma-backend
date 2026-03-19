from dataclasses import dataclass
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q

from logistic.models import WHContactTariffOverride, WHTariff, WHTierCalculationMode

@dataclass
class EffectiveHandlingTier:
    fee_type: str
    unit: str
    min_quantity: Decimal
    max_quantity: Decimal | None
    price: Decimal
    order: int

@dataclass
class EffectiveTariff:
    storage_mode: str | None
    inbound_per_line: Decimal
    outbound_per_order: Decimal
    outbound_per_line: Decimal
    handling_tier_mode: str
    handling_tiers: list


def get_effective_contact_tariff(company, contact, at_date=None) -> EffectiveTariff:
    at_date = at_date or timezone.localdate()

    base = (
        WHTariff.objects
        .filter(company=company, is_active=True)
        .order_by("-created_at")
        .first()
    )

    override = (
        WHContactTariffOverride.objects
        .filter(
            company=company,
            contact=contact,
            is_active=True,
            period_start__lte=at_date,
        )
        .filter(Q(period_end__isnull=True) | Q(period_end__gte=at_date))
        .order_by("-period_start", "-created_at")
        .first()
    )

    if not base and not override:
        return EffectiveTariff(
            storage_mode=None,
            inbound_per_line=Decimal("0"),
            outbound_per_order=Decimal("0"),
            outbound_per_line=Decimal("0"),
            handling_tier_mode=WHTierCalculationMode.BRACKET,
            handling_tiers=[],
        )

    storage_mode = override.storage_mode if override and override.storage_mode else getattr(base, "storage_mode", None)
    inbound_per_line = override.inbound_per_line if override and override.inbound_per_line is not None else getattr(base, "inbound_per_line", Decimal("0"))
    outbound_per_order = override.outbound_per_order if override and override.outbound_per_order is not None else getattr(base, "outbound_per_order", Decimal("0"))
    outbound_per_line = override.outbound_per_line if override and override.outbound_per_line is not None else getattr(base, "outbound_per_line", Decimal("0"))
    handling_tier_mode = override.handling_tier_mode if override and override.handling_tier_mode else getattr(base, "handling_tier_mode", WHTierCalculationMode.BRACKET)

    if override and override.handling_tier_overrides.exists():
        tiers_qs = override.handling_tier_overrides.all()
    else:
        tiers_qs = base.handling_tiers.all() if base else []

    tiers = [
        EffectiveHandlingTier(
            fee_type=t.fee_type,
            unit=t.unit,
            min_quantity=t.min_quantity,
            max_quantity=t.max_quantity,
            price=t.price,
            order=t.order,
        )
        for t in tiers_qs
    ]

    return EffectiveTariff(
        storage_mode=storage_mode,
        inbound_per_line=inbound_per_line,
        outbound_per_order=outbound_per_order,
        outbound_per_line=outbound_per_line,
        handling_tier_mode=handling_tier_mode,
        handling_tiers=tiers,
    )


def resolve_handling_price(effective_tariff, fee_type, unit, quantity):
    qty = Decimal(str(quantity or 0))
    matching = [
        t for t in effective_tariff.handling_tiers
        if t.fee_type == fee_type
        and t.unit == unit
        and qty >= t.min_quantity
        and (t.max_quantity is None or qty < t.max_quantity)
    ]

    if not matching:
        return Decimal("0")

    # if ordering matters, take first after sorting
    matching = sorted(matching, key=lambda x: (x.min_quantity, x.order))
    return matching[0].price


def resolve_handling_unit_price(effective_tariff, fee_type, unit, quantity):
    quantity = Decimal(str(quantity or 0))

    matching = [
        tier
        for tier in effective_tariff.handling_tiers
        if tier.fee_type == fee_type
        and tier.unit == unit
        and quantity >= tier.min_quantity
        and (tier.max_quantity is None or quantity < tier.max_quantity)
    ]

    if not matching:
        return Decimal("0")

    matching = sorted(matching, key=lambda x: (x.min_quantity, x.order))
    return matching[0].price