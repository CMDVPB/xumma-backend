from django.contrib import admin

from ayy.models import AuthorizationStockBatch, CMRStockBatch, DamageReport, PhoneNumber


@admin.register(CMRStockBatch)
class CMRStockBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'series', 'number_from', 'number_to')

    search_fields = ('series', 'company__company_name',
                     'number_from', 'number_to')


@admin.register(AuthorizationStockBatch)
class AuthorizationStockBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'company')

    search_fields = ('company__company_name',
                     )


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ('id', )

    search_fields = ('number',
                     )


@admin.register(DamageReport)
class DamageReportAdmin(admin.ModelAdmin):

    list_display = ('id', 'company', 'vehicle', 'driver')

    search_fields = ('company__company_name', 'vehicle__reg_number', 'driver__email', 'driver__first_name', 'driver__last_name',
                     )
