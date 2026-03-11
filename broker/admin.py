from django.contrib import admin

from broker.models import BrokerBaseSalary, BrokerCommission, CustomerServicePrice, Job, JobLine, PointOfService, ServiceType



@admin.register(PointOfService)
class PointOfServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'name', 'code', 'created_at',
                    )


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'customer', 'point', 'assigned_to', 
                    )



@admin.register(JobLine)
class JobLineAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'service_type', 'quantity', 'unit_price_net', 'vat_percent', 'other_charges',
                    )


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'name',
                    )


@admin.register(CustomerServicePrice)
class CustomerServicePriceAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'customer', 'service_type', 'price', 'is_active',
                    )


@admin.register(BrokerBaseSalary)
class BrokerBaseSalaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'user', 'amount', 'currency', 'valid_from', 'valid_to',
                    )


@admin.register(BrokerCommission)
class BrokerCommissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'customer', 'service_type', 'type', 'value', 'valid_from', 'valid_to',
                    )



