from rest_framework import serializers

from axx.models import Trip
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
