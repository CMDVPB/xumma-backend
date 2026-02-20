from __future__ import annotations
import django_filters
from django.contrib.gis.geos import Polygon
from django.db.models import Q
from django_filters.rest_framework import FilterSet
from .models import POI, SecurityLevel


class BBoxFilter(django_filters.Filter):
    """
    bbox query param: "minLng,minLat,maxLng,maxLat"
    Example: ?bbox=23.5,46.7,23.8,46.9
    """

    def filter(self, qs, value):
        if not value:
            return qs
        try:
            parts = [float(x.strip()) for x in value.split(",")]
            if len(parts) != 4:
                return qs.none()
            min_lng, min_lat, max_lng, max_lat = parts
        except Exception:
            return qs.none()

        if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180 and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            return qs.none()

        # Polygon.from_bbox expects (xmin, ymin, xmax, ymax)
        poly = Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
        poly.srid = 4326
        return qs.filter(point__within=poly)


class AmenitiesAnyFilter(django_filters.CharFilter):
    """
    amenities_any=wc,shower,diner
    Meaning: return POIs that have ANY of these amenities.
    Uses denorm flags when possible for speed.
    """

    def filter(self, qs, value):
        if not value:
            return qs
        keys = [k.strip().lower() for k in value.split(",") if k.strip()]
        if not keys:
            return qs

        q = Q()
        mapping = {
            "wc": Q(has_wc=True),
            "shower": Q(has_shower=True),
            "diner": Q(has_diner=True),
            "shop": Q(has_shop=True),
            "fuel": Q(has_fuel=True),
            "petrol_station": Q(has_fuel=True),
        }
        # For unknown keys, fall back to JSON contains (slower)
        for k in keys:
            if k in mapping:
                q |= mapping[k]
            else:
                q |= Q(amenities__contains={k: True})
        return qs.filter(q)


class AmenitiesAllFilter(django_filters.CharFilter):
    """
    amenities_all=wc,shower
    Meaning: return POIs that have ALL these amenities.
    """

    def filter(self, qs, value):
        if not value:
            return qs
        keys = [k.strip().lower() for k in value.split(",") if k.strip()]
        if not keys:
            return qs

        # Start with qs, apply AND
        mapping = {
            "wc": ("has_wc", True),
            "shower": ("has_shower", True),
            "diner": ("has_diner", True),
            "shop": ("has_shop", True),
            "fuel": ("has_fuel", True),
            "petrol_station": ("has_fuel", True),
        }

        for k in keys:
            if k in mapping:
                field, val = mapping[k]
                qs = qs.filter(**{field: val})
            else:
                qs = qs.filter(amenities__contains={k: True})
        return qs


class POIFilter(FilterSet):
    bbox = BBoxFilter(field_name="point")
    category = django_filters.CharFilter(field_name="category")
    status = django_filters.CharFilter(field_name="status")
    visibility = django_filters.CharFilter(field_name="visibility")

    # quick amenities
    has_wc = django_filters.BooleanFilter(field_name="has_wc")
    has_shower = django_filters.BooleanFilter(field_name="has_shower")
    has_diner = django_filters.BooleanFilter(field_name="has_diner")
    has_shop = django_filters.BooleanFilter(field_name="has_shop")
    has_fuel = django_filters.BooleanFilter(field_name="has_fuel")

    secure_level = django_filters.CharFilter(field_name="secure_level")

    amenities_any = AmenitiesAnyFilter()
    amenities_all = AmenitiesAllFilter()

    class Meta:
        model = POI
        fields = [
            "bbox",
            "category",
            "status",
            "visibility",
            "has_wc",
            "has_shower",
            "has_diner",
            "has_shop",
            "has_fuel",
            "secure_level",
            "amenities_any",
            "amenities_all",
        ]
