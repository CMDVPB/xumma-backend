from django.contrib import admin

from azz.models import ImportBatch, ImportRow, SupplierFormat


@admin.register(SupplierFormat)
class SupplierFormatAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'supplier', 'uf',)


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'supplier', 'status',
                    'created_at', 'finished_at', 'totals')


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch', 'source_file', 'row_number', 'status', 'error_message',
                    )
