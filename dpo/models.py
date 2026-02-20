from __future__ import annotations
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Q, UniqueConstraint, CheckConstraint

import logging

from abb.utils import hex_uuid
from app.models import Company

logger = logging.getLogger(__name__)

User = get_user_model()


class POICategory(models.TextChoices):
    PARKING = "PARKING", "Parking"
    FUEL = "FUEL", "Fuel station"
    DINER = "DINER", "Diner/Restaurant"
    SHOP = "SHOP", "Shop/Supermarket"
    SERVICE = "SERVICE", "Service/Repair"
    WASH = "WASH", "Truck wash"
    WEIGH = "WEIGH", "Weighbridge"
    OTHER = "OTHER", "Other"


class POIStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PENDING = "PENDING", "Pending review"
    REJECTED = "REJECTED", "Rejected"
    ARCHIVED = "ARCHIVED", "Archived"


class POIVisibility(models.TextChoices):
    COMPANY = "COMPANY", "Company"
    TEAM = "TEAM", "Team"  # optional
    PRIVATE = "PRIVATE", "Private"  # only creator (optional)


class SecurityLevel(models.TextChoices):
    UNKNOWN = "UNKNOWN", "Unknown"
    UNSECURED = "UNSECURED", "Unsecured"
    FENCE_GATE = "FENCE_GATE", "Fence/Gate"
    CCTV = "CCTV", "CCTV"
    GUARDED = "GUARDED", "Guarded"
    ACCESS_CONTROLLED = "ACCESS_CONTROLLED", "Access-controlled"


class POI(models.Model):
    """
    JSON schemas (recommended):

    amenities JSON:
    {
      "wc": true,
      "shower": false,
      "diner": true,
      "shop": true,
      "petrol_station": true,
      "wifi": false,
      "laundry": false,
      "truck_wash": false,
      "repair": false,
      "weighbridge": false
    }

    parking JSON:
    {
      "parking_type": "lot|street|dedicated|none",
      "secure_level": "UNKNOWN|UNSECURED|FENCE_GATE|CCTV|GUARDED|ACCESS_CONTROLLED",
      "overnight_allowed": true,
      "spaces_truck": 40,
      "max_truck_length_m": 16,
      "notes": "barrier after 22:00"
    }

    pricing JSON:
    {
      "currency": "EUR",
      "parking_fee": {"amount": "15.00", "per": "night", "notes": "cash only"},
      "shower_fee": {"amount": "3.00", "per": "use"},
      "wc_fee": {"amount": "0.50", "per": "use"}
    }
    """

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)

    # If you are multi-tenant by company/account/org:
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_pois")

    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=20, choices=POICategory.choices, db_index=True)

    # Geo
    point = gis_models.PointField(geography=True, srid=4326)  # WGS84
    address_text = models.CharField(max_length=400, blank=True, default="")

    # Optional OSM link
    osm_place_id = models.BigIntegerField(null=True, blank=True)

    # Core data
    status = models.CharField(
        max_length=20, choices=POIStatus.choices, default=POIStatus.PENDING, db_index=True)
    visibility = models.CharField(
        max_length=20, choices=POIVisibility.choices, default=POIVisibility.COMPANY, db_index=True)

    notes = models.TextField(blank=True, default="")

    # Structured fields (flexible)
    amenities = models.JSONField(default=dict, blank=True)
    parking = models.JSONField(default=dict, blank=True)
    pricing = models.JSONField(default=dict, blank=True)

    pricing_last_updated_at = models.DateTimeField(null=True, blank=True)

    # Denormalized flags (optional but recommended for fast filtering)
    has_wc = models.BooleanField(default=False, db_index=True)
    has_shower = models.BooleanField(default=False, db_index=True)
    has_diner = models.BooleanField(default=False, db_index=True)
    has_shop = models.BooleanField(default=False, db_index=True)
    has_fuel = models.BooleanField(default=False, db_index=True)
    secure_level = models.CharField(
        max_length=30, choices=SecurityLevel.choices, default=SecurityLevel.UNKNOWN, db_index=True)

    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_by_pois")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    updated_at = models.DateTimeField(auto_now=True)

    last_verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="verified_by_pois"
    )

    class Meta:
        indexes = [
            # Geo index for bbox/within queries
            gis_models.Index(fields=["point"], name="poi_point_gist_idx"),
            # GIN for JSON filtering / containment queries (if you choose to query JSON directly)
            GinIndex(fields=["amenities"], name="poi_amenities_gin_idx"),
            GinIndex(fields=["parking"], name="poi_parking_gin_idx"),
            GinIndex(fields=["pricing"], name="poi_pricing_gin_idx"),
            # A common composite filter for dashboards
            models.Index(fields=["company", "status", "category"],
                         name="poi_company_status_cat_idx"),
        ]
        constraints = [
            # Prevent obvious duplicates by name+point within company? (exact point match)
            UniqueConstraint(
                fields=["company", "name", "point"], name="poi_unique_name_point_per_company"),
            CheckConstraint(check=~Q(name=""), name="poi_name_not_empty"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"

    def sync_denorm_flags_from_json(self) -> None:
        """
        Keep denormalized flags in sync. Call in save() or in serializer update/create.
        """
        am = self.amenities or {}
        self.has_wc = am.get("wc") is True
        self.has_shower = am.get("shower") is True
        self.has_diner = am.get("diner") is True
        self.has_shop = am.get("shop") is True
        self.has_fuel = (am.get("petrol_station") is True) or (
            am.get("fuel") is True)

        pk = self.parking or {}
        lvl = pk.get("secure_level") or pk.get("secure") or self.secure_level
        if lvl in {c[0] for c in SecurityLevel.choices}:
            self.secure_level = lvl
        else:
            self.secure_level = SecurityLevel.UNKNOWN

    def save(self, *args, **kwargs):
        self.sync_denorm_flags_from_json()
        super().save(*args, **kwargs)


class POIReview(models.Model):
    poi = models.ForeignKey(
        POI, on_delete=models.CASCADE, related_name="poi_reviews")
    author = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="auther_poi_reviews")

    rating_overall = models.PositiveSmallIntegerField()  # validate 1..5 in serializer
    rating_security = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_cleanliness = models.PositiveSmallIntegerField(
        null=True, blank=True)
    rating_value = models.PositiveSmallIntegerField(null=True, blank=True)

    comment = models.TextField(blank=True, default="")
    visited_at = models.DateField(null=True, blank=True)

    status_visible = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["poi", "status_visible",
                         "-created_at"], name="poirev_poi_vis_created_idx"),
            models.Index(fields=["author", "-created_at"],
                         name="poirev_author_created_idx"),
        ]
        constraints = [
            CheckConstraint(check=Q(rating_overall__gte=1) & Q(
                rating_overall__lte=5), name="poirev_overall_1_5"),
        ]

    def __str__(self) -> str:
        return f"Review {self.rating_overall}/5 for {self.poi_id}"
