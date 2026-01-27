from django.contrib import admin

from avv.models import IssueDocument, Location, Part, PartRequest, UnitOfMeasure, Warehouse


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'name', 'sku', 'uom', 'min_level')

    search_fields = ("company__company_name", 'name', 'sku', 'uom', 'uf')


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code',)

    search_fields = ("company__company_name", 'name', 'code', 'uf')


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'warehouse', 'name', 'code',)

    search_fields = ("warehouse__name", 'warehouse__code', 'code', 'name')


@admin.register(PartRequest)
class PartRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'mechanic', 'vehicle',
                    'driver', 'needed_at', 'note', )

    search_fields = ("mechanic__first_name",
                     'vehicle__reg_number', 'driver_first_name', 'note')


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'serial_number', 'code', 'name', 'is_system', 'uf',
                    )

    search_fields = ("company__company_name",
                     'code', 'name', 'uf'
                     )


@admin.register(IssueDocument)
class IssueDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'status', 'uf',
                    )

    search_fields = ("company__company_name",
                     'status', 'uf'
                     )
