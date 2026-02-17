from django.conf import settings
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.auth import get_user_model

import logging
logger = logging.getLogger(__name__)

User = get_user_model()


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
