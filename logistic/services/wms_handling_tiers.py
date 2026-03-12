from decimal import Decimal

from django.core.exceptions import ValidationError

from logistic.models import (
    WHTariff,
    WHContactTariffOverride,
    WHTariffHandlingTier,
    WHContactTariffHandlingTierOverride,
    WHTierCalculationMode,
)


def resolve_handling_tiers(*, company, contact, fee_type, unit):
    """
    Resolve effective handling tier config for a contact.

    Rule:
    - active default tariff is required
    - if contact override has any tiers for (fee_type, unit), use ONLY those override tiers
    - otherwise use default tariff tiers
    - handling_tier_mode may also be overridden if WHContactTariffOverride.handling_tier_mode exists

    Returns:
        {
            "tariff": <WHTariff>,
            "override": <WHContactTariffOverride|None>,
            "mode": "band" | "bracket",
            "tiers": [tier, tier, ...],   # queryset evaluated to list
            "source": "override" | "default",
        }
    """
    default_tariff = (
        WHTariff.objects
        .filter(company=company, is_active=True)
        .order_by("-created_at")
        .first()
    )

    if not default_tariff:
        raise ValidationError("No active warehouse tariff found.")

    override = (
        WHContactTariffOverride.objects
        .filter(company=company, contact=contact)
        .first()
    )

    mode = default_tariff.handling_tier_mode

    if override and hasattr(override, "handling_tier_mode") and override.handling_tier_mode:
        mode = override.handling_tier_mode

    override_tiers = []
    if override:
        override_tiers = list(
            WHContactTariffHandlingTierOverride.objects
            .filter(
                override=override,
                fee_type=fee_type,
                unit=unit,
            )
            .order_by("min_quantity", "order", "id")
        )

    if override_tiers:
        return {
            "tariff": default_tariff,
            "override": override,
            "mode": mode,
            "tiers": override_tiers,
            "source": "override",
        }

    default_tiers = list(
        WHTariffHandlingTier.objects
        .filter(
            tariff=default_tariff,
            fee_type=fee_type,
            unit=unit,
        )
        .order_by("min_quantity", "order", "id")
    )

    return {
        "tariff": default_tariff,
        "override": override,
        "mode": mode,
        "tiers": default_tiers,
        "source": "default",
    }


def calculate_tier_amount(*, quantity, tiers, mode):
    """
    Calculate total amount from tier rows.

    Args:
        quantity: Decimal|int|float
        tiers: iterable of rows with fields:
            - min_quantity
            - max_quantity
            - price
        mode:
            - WHTierCalculationMode.BAND
            - WHTierCalculationMode.BRACKET

    BAND:
        Find one matching tier for the total quantity, and charge:
            quantity * tier.price

    BRACKET:
        Progressive calculation. Example:
            tiers:
              0 - 20 => 10
              20 - 50 => 8
              50+ => 6

            quantity 60 =>
              20 * 10 + 30 * 8 + 10 * 6

    Returns:
        Decimal
    """
    qty = Decimal(str(quantity or 0))
    if qty <= 0:
        return Decimal("0.0000")

    normalized_tiers = []
    for tier in tiers:
        min_q = Decimal(str(tier.min_quantity or 0))
        max_q = None if tier.max_quantity is None else Decimal(str(tier.max_quantity))
        price = Decimal(str(tier.price or 0))

        normalized_tiers.append({
            "min": min_q,
            "max": max_q,
            "price": price,
            "raw": tier,
        })

    if not normalized_tiers:
        return Decimal("0.0000")

    if mode == WHTierCalculationMode.BAND:
        for tier in normalized_tiers:
            min_q = tier["min"]
            max_q = tier["max"]

            if qty < min_q:
                continue

            if max_q is None or qty <= max_q:
                return (qty * tier["price"]).quantize(Decimal("0.0001"))

        raise ValidationError(
            f"No handling tier matches quantity {qty} for mode '{mode}'."
        )

    if mode == WHTierCalculationMode.BRACKET:
        total = Decimal("0")
        remaining = qty

        for tier in normalized_tiers:
            min_q = tier["min"]
            max_q = tier["max"]
            price = tier["price"]

            if remaining <= 0:
                break

            if qty <= min_q:
                continue

            if max_q is None:
                slice_qty = max(Decimal("0"), qty - min_q)
            else:
                upper_bound = min(qty, max_q)
                slice_qty = max(Decimal("0"), upper_bound - min_q)

            if slice_qty > 0:
                total += slice_qty * price

        return total.quantize(Decimal("0.0001"))

    raise ValidationError(f"Unsupported tier calculation mode: {mode}")