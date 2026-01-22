from django.contrib import admin

from azz.models import FuelTank, ImportBatch, ImportRow, SupplierFormat, TankRefill, TruckFueling


@admin.register(SupplierFormat)
class SupplierFormatAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'supplier', 'uf',
                    )


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'supplier', 'status',
                    'created_at', 'finished_at', 'totals',
                    )


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch', 'source_file', 'row_number', 'status', 'error_message',
                    )


@admin.register(FuelTank)
class FuelTankAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'fuel_type', 'capacity_l',
                    )


@admin.register(TankRefill)
class TankRefillAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'supplier', 'quantity_l', 'actual_quantity_l', 'price_l', 'comments',
                    )


@admin.register(TruckFueling)
class TruckFuelingAdmin(admin.ModelAdmin):
    list_display = ('id', 'fueled_at', 'tank', 'vehicle', 'driver', 'quantity_l',
                    )
