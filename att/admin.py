from django.contrib import admin

from .models import Contact, ContactSite, EmissionClass, PaymentTerm, VehicleBrand, Vehicle, VehicleUnit, Person, BankAccount


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'currency_code', 'company', 'iban_number')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('id', 'company_name', 'fiscal_code', 'vat_code', 'company')

    search_fields = ('company_name', 'fiscal_code',
                     'company__company_name', 'company__uf', 'company__email')


@admin.register(ContactSite)
class ContactSiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'name_site', 'contact')

    search_fields = ('contact__company_name', 'contact__fiscal_code',
                     'contact__compoany__uf', 'contact__company__company_name')


@admin.register(EmissionClass)
class EmissionClassAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'label', 'description')


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'payment_term_short',
                    'payment_term_description', 'payment_term_days')


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name',
                    'contact', 'site', 'is_driver')


@admin.register(VehicleBrand)
class VehicleBrandAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'name', 'serial_number')


@admin.register(VehicleUnit)
class VehicleUnitAdmin(admin.ModelAdmin):
    list_display = ('id', 'reg_number', 'vehicle_type', 'contact')

    search_fields = ('reg_number',)

    ordering = ['-id']


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'contact', 'reg_number', 'vehicle_type')

    search_fields = ('reg_number', 'company')

    ordering = ['-id']
