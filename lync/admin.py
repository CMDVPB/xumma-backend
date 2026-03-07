from django.contrib import admin

from lync.models import LoadSecret

@admin.register(LoadSecret)
class LoadSecretAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'load', 'payload', 'created_by', 'updated_by', 'date_created', 'date_modified')

    search_fields = ('company__company_name', 'load__sn', 'payload',
                     )

    





