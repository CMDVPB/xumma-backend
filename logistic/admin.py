from django.contrib import admin

from logistic.models import WHLocation, WHProduct



@admin.register(WHLocation)
class WHLocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'name', 'is_active',
                    )


@admin.register(WHProduct)
class WHProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'owner', 'sku',
                    )
