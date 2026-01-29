from django.contrib import admin

from avv.models import IssueDocument, Location, Part, PartRequest, StockLot, UnitOfMeasure, Warehouse, WorkOrder, WorkOrderIssue, WorkOrderWorkLine, WorkType


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


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'vehicle', 'mechanic',  'driver',
                    'status', 'parts_cost', 'labor_cost', 'total_cost',)

    search_fields = ("company__company_name",
                     'status', 'uf'
                     )


@admin.register(WorkType)
class WorkTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'name',
                    )

    search_fields = ("company__company_name", 'uf',
                     )


@admin.register(WorkOrderWorkLine)
class WorkOrderWorkLineAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'work_order', 'work_type', 'unit', 'qty',
                    )

    search_fields = ("company__company_name", 'uf',
                     )


@admin.register(StockLot)
class StockLotAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'part', 'unit_cost', 'currency', 'uf',
                    )

    search_fields = ("company__company_name",
                     'uf'
                     )


@admin.register(WorkOrderIssue)
class WorkOrderIssueAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'work_order', 'part', 'lot', 'unit_cost', 'currency', 'qty', 'uf',
                    )

    search_fields = ("company__company_name",
                     'uf'
                     )
