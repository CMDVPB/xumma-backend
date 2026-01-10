from django.contrib import admin

from app.views import User
from ayy.models import AuthorizationStockBatch, CMRStockBatch, ColliType, DamageReport, EmailTemplate, ImageUpload, ItemCost, ItemForItemCost, MailLabelV2, MailMessage, PhoneNumber, UserEmail


@admin.register(CMRStockBatch)
class CMRStockBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'series', 'number_from', 'number_to')

    search_fields = ('series', 'company__company_name',
                     'number_from', 'number_to')


@admin.register(ColliType)
class ColliTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'label',
                    'ldm', 'description', 'is_system')


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


@admin.register(UserEmail)
class UserEmailAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'to', 'status', 'sent_at')

    search_fields = ('to',
                     )


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'company',  'code', 'label',
                    'created_by', 'created_at')


@admin.register(MailLabelV2)
class MailLabelV2Admin(admin.ModelAdmin):
    list_display = ('id', "name", "user", "type", "order")

    list_filter = ("type",)


@admin.register(MailMessage)
class MailMessageAdmin(admin.ModelAdmin):
    list_display = ('id', "user", "to", "subject", "is_read", "created_at")

    list_filter = ("user", "is_read")


@admin.register(ImageUpload)
class ImageUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'file_name', 'load', 'user', 'vehicle')

    list_filter = ('company', "user", "load", 'vehicle')


@admin.register(ItemCost)
class ItemCostAdmin(admin.ModelAdmin):
    list_display = ('id', 'company',
                    )

    search_fields = ('company__company_name',
                     )


@admin.register(ItemForItemCost)
class ItemForItemCostAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'serial_number',
                    'description', 'code', 'vat', 'is_system')

    search_fields = ('company__company_name',
                     )
