from django.contrib import admin

from logistic.models import WHLocation



@admin.register(WHLocation)
class WHLocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'name', 'is_active',
                    )
