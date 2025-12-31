from django.contrib import admin

from axx.models import Load, Trip, TripDriver


@admin.register(Load)
class LoadAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'is_loaded',
                    'is_cleared', 'is_unloaded', 'is_invoiced')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'vehicle_tractor', 'vehicle_trailer')


@admin.register(TripDriver)
class TripDriverAdmin(admin.ModelAdmin):
    list_display = ('id', )
