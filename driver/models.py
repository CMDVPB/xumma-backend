from django.conf import settings
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.auth import get_user_model
from django.utils import timezone

import logging

from abb.utils import hex_uuid
from app.models import Company
from axx.models import Load, Trip
from ayy.models import Entry
logger = logging.getLogger(__name__)

User = get_user_model()

###### START TRIP STOPS ######


class TripStop(models.Model):

    STOP_TYPES = [
        ("pickup", "Pickup"),
        ("delivery", "Delivery"),
        ("parking", "Parking"),
        ("custom", "Custom"),
    ]

    STOP_STATUS = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
    ]

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_trip_stops")

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="trip_stops"
    )

    load = models.ForeignKey(          # optional (parking may not have load)
        Load,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="load_stops"
    )

    entry = models.ForeignKey(         # optional but useful
        Entry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entry_stops"
    )

    type = models.CharField(max_length=20, choices=STOP_TYPES)

    # Optional but very useful: stop status instead of boolean
    # If later want richer logic (skipped / failed / cancelled), boolean becomes limiting.
    status = models.CharField(
        max_length=20, choices=STOP_STATUS, default="pending")

    order = models.PositiveIntegerField()

    title = models.CharField(max_length=100, blank=True, null=True)

    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    is_visible_to_driver = models.BooleanField(default=False)

    is_completed = models.BooleanField(default=False)

    date_completed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "trip", "order"],
                name="unique_trip_stop_order"
            )
        ]
        indexes = [
            models.Index(fields=["trip", "order"]),
        ]

    def save(self, *args, **kwargs):
        if self.is_completed and self.date_completed is None:
            self.date_completed = timezone.now()

        if not self.is_completed:
            self.date_completed = None

        super().save(*args, **kwargs)

###### END TRIP STOPS ######


class DriverLocation(models.Model):
    driver = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="driver_location"
    )

    lat = models.FloatField()
    lng = models.FloatField()

    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.driver} → {self.lat}, {self.lng}"


class DriverTrackPoint(models.Model):
    driver = models.ForeignKey(User, on_delete=models.CASCADE)

    point = gis_models.PointField()

    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)

    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # Massive performance boost later
            gis_models.Index(fields=["point"]),
            models.Index(fields=["driver", "recorded_at"]),
        ]

    def __str__(self):
        return f"{self.driver} @ {self.recorded_at}"
