from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin

from driver.models import DriverLocation, DriverTrackPoint, TripStop


@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'driver', 'lat', 'lng', 'speed', 'heading', 'updated_at',
                    )


@admin.register(DriverTrackPoint)
class DriverTrackPointAdmin(LeafletGeoAdmin):
    list_display = ('id', 'driver', 'point', 'speed', 'heading',
                    )


@admin.register(TripStop)
class TripStopAdmin(LeafletGeoAdmin):
    list_display = ('id', 'trip', 'is_visible_to_driver', 'is_completed', 'type', 'status',
                    )
