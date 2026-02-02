from django.contrib import admin

from baa.models import VehicleChecklist, VehicleChecklistItem


@admin.register(VehicleChecklist)
class VehicleChecklistAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'vehicle', 'driver', 'started_at', 'finished_at', 'uf',
                    )


@admin.register(VehicleChecklistItem)
class VehicleChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'title', 'description', 'order', 'is_active', 'is_system', 'uf',
                    )
