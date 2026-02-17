from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin

from driver.models import DriverLocation, DriverTrackPoint


@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'driver', 'lat', 'lng', 'speed', 'heading', 'updated_at',
                    )


@admin.register(DriverTrackPoint)
class DriverTrackPointAdmin(LeafletGeoAdmin):
    list_display = ('id', 'driver', 'point', 'speed', 'heading',
                    )
