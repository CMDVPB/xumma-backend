from rest_framework import serializers
from django.conf import settings

from axx.models import Load, LoadEvidence, Trip
from .models import DriverLocation


class DriverLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverLocation
        fields = ("lat", "lng", "speed", "heading")


class ActiveTripSerializer(serializers.ModelSerializer):

    tractor_number = serializers.CharField(
        source='vehicle_tractor.reg_number', allow_null=True
    )

    trailer_number = serializers.CharField(
        source='vehicle_trailer.reg_number', allow_null=True
    )

    drivers = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = (
            'id',
            'rn',
            'tractor_number',
            'trailer_number',
            'drivers',
            'location',
            'uf',
        )

    def get_drivers(self, obj):
        result = []

        for driver in obj.drivers.all():

            loc = getattr(driver, 'driver_location', None)

            result.append({
                'id': driver.id,
                'name': driver.get_full_name(),
                'uf': driver.uf,
                'location': {
                    'lat': loc.lat,
                    'lng': loc.lng,
                    'speed': loc.speed,
                    'heading': loc.heading,
                    'updated_at': loc.updated_at,
                } if loc else None
            })

        return result

    def get_location(self, obj):
        """
        Strategy used by real fleet systems:

        → Use first driver with telemetry
        → Avoid assumptions about tractor device
        """

        driver = obj.drivers.first()
        if not driver:
            return None

        loc = getattr(driver, 'driverlocation', None)
        if not loc:
            return None

        return {
            'lat': loc.lat,
            'lng': loc.lng,
            'speed': loc.speed,
            'heading': loc.heading,
            'updated_at': loc.updated_at,
        }


###### START DRIVER LOADING ######

class ConfirmLoadingSerializer(serializers.Serializer):
    uf = serializers.CharField()


class DriverTripSerializer(serializers.ModelSerializer):
    loads = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            "rn",
            "date_order",
            "loads",
            "uf",
        ]

    def get_loads(self, obj):
        loads = obj.trip_loads.all().order_by("date_order")
        return DriverLoadSerializer(loads, many=True).data


class LoadEvidenceSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = LoadEvidence
        fields = [
            "id",
            "type",
            "image",
            "image_url",
            "created_at",
            'uf'
        ]

    def validate_image(self, value):
        if not value:
            raise serializers.ValidationError("Image is required")

        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image too large")

        return value

    def get_image_url(self, obj):
        return f"{settings.MOBILE_BACKEND_URL}/api/load-evidences/{obj.uf}/"


class DriverLoadSerializer(serializers.ModelSerializer):
    load_evidences = LoadEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = Load
        fields = [
            "sn",
            "load_address",
            "unload_address",
            "load_detail",
            "driver_status",
            "date_loaded",
            "uf",

            "load_evidences",
        ]


###### END DRIVER LOADING ######
