# azz/services/fuel_sync.py
from django.db.models import F
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from azz.models import FuelTank, TankRefill, TruckFueling

FUEL_COST_CODE_TO_TANK = {
    "adblue_tanc": FuelTank.FUEL_ADBLUE,
    "dt_tanc": FuelTank.FUEL_DIESEL,
}


FUEL_COST_CODE_TO_TANK = {
    "adblue_tanc": FuelTank.FUEL_ADBLUE,
    "dt_tanc": FuelTank.FUEL_DIESEL,
}


def fifo_valuation(tank, quantity_l: Decimal):
    remaining = Decimal(quantity_l)
    total_cost = Decimal("0")

    refills = (
        tank.tank_refills
        .filter(actual_quantity_l__gt=0)
        .order_by("date", "id")
        .select_for_update()
    )

    for refill in refills:
        if remaining <= 0:
            break

        available = refill.actual_quantity_l
        take = min(available, remaining)

        total_cost += take * refill.price_l
        remaining -= take

    if remaining > 0:
        raise DjangoValidationError("Not enough fuel in tank")

    unit_price = (total_cost / Decimal(quantity_l)).quantize(Decimal("0.0001"))
    total_cost = total_cost.quantize(Decimal("0.01"))

    return unit_price, total_cost


def sync_fueling_from_item_cost(item_cost):
    item = item_cost.item_for_item_cost

    if not item or not item.code:
        return

    fuel_type = FUEL_COST_CODE_TO_TANK.get(item.code)
    if not fuel_type:
        return  # not a tank-backed fuel cost

    if not item_cost.quantity or not item_cost.trip:
        return

    try:
        with transaction.atomic():
            tank = FuelTank.objects.select_for_update().get(
                company=item_cost.company,
                fuel_type=fuel_type,
            )

            # 🔥 FIFO valuation
            unit_price, total_cost = fifo_valuation(
                tank,
                Decimal(item_cost.quantity)
            )

            # 🚚 Fueling event (physical stock movement)
            fueling, _ = TruckFueling.objects.update_or_create(
                item_cost=item_cost,
                defaults={
                    "tank": tank,
                    "vehicle": item_cost.trip.vehicle_tractor,
                    "quantity_l": item_cost.quantity,
                    "fueled_at": item_cost.date or timezone.now(),
                    "driver": item_cost.created_by,
                },
            )

            fueling.full_clean()
            fueling.save()

            # Write valuation back to ItemCost
            item_cost.amount = unit_price          # price per liter
            item_cost.save(update_fields=["amount"])

    except DjangoValidationError as e:
        raise DRFValidationError(e.message_dict or e.messages)


###### PREVIEW ONLY ######

def fifo_price_preview(*, tank: FuelTank, quantity_l: Decimal):
    """
    Calculate FIFO price preview for a given quantity WITHOUT modifying stock.
    """

    remaining = Decimal(quantity_l)
    total_cost = Decimal("0")
    consumed = Decimal("0")

    refills = (
        TankRefill.objects
        .filter(tank=tank)
        .order_by("date", "id")
    )

    for refill in refills:
        if remaining <= 0:
            break

        available = refill.actual_quantity_l
        if available <= 0:
            continue

        take = min(available, remaining)

        total_cost += take * refill.price_l
        consumed += take
        remaining -= take

    if remaining > 0:
        raise DjangoValidationError("Not enough fuel in tank")

    price_per_l = (total_cost / consumed).quantize(Decimal("0.0001"))

    return {
        "price_per_l": price_per_l,
        "total_cost": total_cost.quantize(Decimal("0.01")),
    }
