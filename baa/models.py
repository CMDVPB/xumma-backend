from att.models import Vehicle
from abb.utils import hex_uuid, image_upload_path
from django.db import models
from django.contrib.auth import get_user_model
import logging

from app.models import Company
from axx.models import Trip
logger = logging.getLogger(__name__)

User = get_user_model()


class VehicleChecklistItem(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=500, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    applies_to_departure = models.BooleanField(default=True)
    applies_to_arrival = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)

    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title


class VehicleChecklist(models.Model):
    INSPECTION_TYPES = (
        ("departure", "Departure"),
        ("arrival", "Arrival"),
    )

    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_checklists')

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="vehicle_checklists"
    )
    driver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="driver_checklists"
    )

    verified_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_checklists")

    verified_at = models.DateTimeField(null=True, blank=True)

    inspection_type = models.CharField(
        max_length=20, choices=INSPECTION_TYPES, db_index=True)

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    mileage = models.PositiveIntegerField(null=True, blank=True)
    general_comment = models.CharField(max_length=1000, blank=True, null=True)

    is_completed = models.BooleanField(default=False)

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="trip_checklists",
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.vehicle} – {self.driver} – {self.started_at.date()}"


class VehicleChecklistAnswer(models.Model):
    checklist = models.ForeignKey(
        VehicleChecklist, on_delete=models.CASCADE, related_name="checklist_answers"
    )
    item = models.ForeignKey(
        VehicleChecklistItem, on_delete=models.PROTECT, related_name="item_answers"
    )

    is_ok = models.BooleanField()
    comment = models.CharField(max_length=500, blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE, blank=True, null=True,
        related_name="created_by_checklist_answers"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("checklist", "item")

    def __str__(self):
        return f"{self.item} – {'OK' if self.is_ok else 'NOT OK'}"


class VehicleChecklistPhoto(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_checklist_photos')

    answer = models.ForeignKey(
        VehicleChecklistAnswer,
        on_delete=models.CASCADE,
        related_name="answer_photos"
    )
    image = models.ImageField(upload_to=image_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)


class VehicleEquipment(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_equipments')

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="vehicle_equipments"
    )
    name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)

    last_updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} x{self.quantity}"
