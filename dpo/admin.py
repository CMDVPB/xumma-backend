from django.contrib import admin

from dpo.models import POI


@admin.register(POI)
class POIAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'category', 'name', 'point', 'status')

    search_fields = ('company__company_name',
                     'category', 'name')
