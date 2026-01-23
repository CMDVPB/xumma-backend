
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from axx.models import Trip
from ayy.models import ItemCost
from azz.models import FuelTank, TruckFueling
from azz.tasks import match_unmatched_import_rows


@receiver(post_save, sender=Trip)
def on_trip_closed(sender, instance, **kwargs):
    if instance.date_end:
        match_unmatched_import_rows.delay(company_id=instance.company_id)


# ADBLUE_TANK_CODE = "adblue_tanc"


# def _should_deduct_from_tank(item_cost: ItemCost) -> bool:
#     item = item_cost.item_for_item_cost

#     print('3060', item.code, item_cost.quantity, item_cost.trip)

#     return (
#         item is not None
#         # and item.is_fuel
#         and item.code == ADBLUE_TANK_CODE
#         and item_cost.quantity is not None
#         and item_cost.trip is not None
#         # and getattr(item_cost.trip, "status", None) == "confirmed"
#     )


# @receiver(post_save, sender=ItemCost)
# def sync_truck_fueling_from_item_cost(sender, instance: ItemCost, **kwargs):
#     """
#     Create or update TruckFueling when an ItemCost represents
#     AdBlue consumption from company tank.
#     """

#     print('3460', instance)

#     if not _should_deduct_from_tank(instance):
#         return

#     with transaction.atomic():
#         # Get AdBlue tank
#         try:
#             tank = FuelTank.objects.select_for_update().get(
#                 company=instance.company,
#                 fuel_type=FuelTank.FUEL_ADBLUE,
#             )
#         except FuelTank.DoesNotExist:
#             raise ValidationError("AdBlue tank not configured")

#         # Create or update fueling event
#         fueling, created = TruckFueling.objects.update_or_create(
#             item_cost=instance,
#             defaults={
#                 "tank": tank,
#                 "vehicle": instance.trip.vehicle_tractor,
#                 "quantity_l": instance.quantity,
#                 "fueled_at": instance.date or timezone.now(),
#                 "driver": instance.created_by,
#             },
#         )

#         # Enforce stock validation
#         fueling.full_clean()
#         fueling.save()


# @receiver(post_delete, sender=ItemCost)
# def delete_truck_fueling_on_item_cost_delete(sender, instance: ItemCost, **kwargs):
#     """
#     Reverse fuel deduction when an ItemCost is deleted.
#     """

#     if not hasattr(instance, "fueling_event"):
#         return

#     instance.fueling_event.delete()
