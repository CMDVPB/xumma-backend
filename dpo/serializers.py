from __future__ import annotations

from django.contrib.gis.geos import Point
from rest_framework import serializers

from abb.utils import get_user_company
from .models import POI, POIReview, POICategory, POIStatus, POIVisibility, SecurityLevel


class PointField(serializers.Field):
    """
    Accepts either:
      {"lat": 46.77, "lng": 23.59}
    or:
      {"latitude": ..., "longitude": ...}
    Returns:
      {"lat": ..., "lng": ...}
    """

    def to_representation(self, value):
        if value is None:
            return None
        return {"lat": value.y, "lng": value.x}

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                "point must be an object like {'lat':..,'lng':..}")
        lat = data.get("lat", data.get("latitude"))
        lng = data.get("lng", data.get("lon", data.get("longitude")))
        if lat is None or lng is None:
            raise serializers.ValidationError("point requires lat/lng")
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except (TypeError, ValueError):
            raise serializers.ValidationError("lat/lng must be numbers")
        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            raise serializers.ValidationError("lat/lng out of range")
        return Point(lng_f, lat_f, srid=4326)


class POISerializer(serializers.ModelSerializer):
    point = PointField()

    avg_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = POI
        fields = [
            "id",
            "company",
            "name",
            "category",
            "point",
            "address_text",
            "osm_place_id",
            "status",
            "visibility",
            "notes",
            "amenities",
            "parking",
            "pricing",
            "pricing_last_updated_at",
            "has_wc",
            "has_shower",
            "has_diner",
            "has_shop",
            "has_fuel",
            "secure_level",
            "created_by",
            "created_at",
            "updated_at",
            "last_verified_at",
            "verified_by",
            "avg_rating",
            "reviews_count",
        ]
        read_only_fields = [
            "company",
            "created_by",
            "created_at",
            "updated_at",
            "last_verified_at",
            "verified_by",
            "has_wc",
            "has_shower",
            "has_diner",
            "has_shop",
            "has_fuel",
            "secure_level",
            "avg_rating",
            "reviews_count",
        ]

    def validate_category(self, value):
        if value not in POICategory.values:
            raise serializers.ValidationError("Invalid category.")
        return value

    def validate_status(self, value):
        if value not in POIStatus.values:
            raise serializers.ValidationError("Invalid status.")
        return value

    def validate_visibility(self, value):
        if value not in POIVisibility.values:
            raise serializers.ValidationError("Invalid visibility.")
        return value

    def validate_amenities(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "amenities must be a JSON object")
        # allow only known keys (optional strictness)
        allowed = {
            "wc", "shower", "diner", "shop", "petrol_station", "fuel",
            "wifi", "laundry", "truck_wash", "repair", "weighbridge"
        }
        unknown = set(value.keys()) - allowed
        if unknown:
            raise serializers.ValidationError(
                f"Unknown amenities keys: {sorted(unknown)}")
        return value

    def validate_parking(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("parking must be a JSON object")
        lvl = value.get("secure_level")
        if lvl is not None and lvl not in SecurityLevel.values:
            raise serializers.ValidationError(
                f"parking.secure_level must be one of {SecurityLevel.values}")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["created_by"] = request.user

        user = self.context["request"].user
        user_company = get_user_company(user)
        validated_data["company"] = user_company

        poi = super().create(validated_data)
        # save() already syncs denorm flags
        return poi

    def update(self, instance, validated_data):
        poi = super().update(instance, validated_data)
        # save() already syncs denorm flags
        return poi


class POIReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = POIReview
        fields = [
            "id",
            "poi",
            "author",
            "rating_overall",
            "rating_security",
            "rating_cleanliness",
            "rating_value",
            "comment",
            "visited_at",
            "status_visible",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["author", "created_at", "updated_at"]

    def validate_rating_overall(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("rating_overall must be 1..5")
        return value

    def _validate_optional_rating(self, value, field_name):
        if value is None:
            return value
        if not (1 <= value <= 5):
            raise serializers.ValidationError(f"{field_name} must be 1..5")
        return value

    def validate_rating_security(self, value):
        return self._validate_optional_rating(value, "rating_security")

    def validate_rating_cleanliness(self, value):
        return self._validate_optional_rating(value, "rating_cleanliness")

    def validate_rating_value(self, value):
        return self._validate_optional_rating(value, "rating_value")

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
