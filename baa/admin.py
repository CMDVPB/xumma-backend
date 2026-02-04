from django.contrib import admin

from baa.models import VehicleChecklist, VehicleChecklistAnswer, VehicleChecklistItem


@admin.register(VehicleChecklist)
class VehicleChecklistAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'vehicle', 'driver', 'started_at', 'finished_at', 'uf',
                    )


@admin.register(VehicleChecklistItem)
class VehicleChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'title', 'description', 'order', 'is_active', 'is_system', 'uf',
                    )


@admin.register(VehicleChecklistAnswer)
class VehicleChecklistAnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'checklist', 'item', 'is_ok',
                    )

# 1	lights	Lights & indicators
# 2	tires	Tires & wheels
# 3	mirrors	Mirrors
# 4	brakes	Brakes
# 5	horn	Horn
# 6	fluids	Fluids (oil, coolant, washer)
# 7	documents	Vehicle documents
# 8	fire_ext	Fire extinguisher
# 9	warning_triangle	Warning triangle
# 10	first_aid	First aid kit
