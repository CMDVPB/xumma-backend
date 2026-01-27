from django.contrib import admin

from auu.models import PaymentMethod


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'serial_number',
                    'code', 'label', 'is_system')
