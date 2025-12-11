from django.contrib import admin

from .models import Contact, ContactSite, VehicleUnit, Person, BankAccount


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
    list_display = ('id', 'contact', 'name_site')

    search_fields = ('contact__company_name', 'contact__fiscal_code',
                     'contact__compoany__uf', 'contact__company__company_name')


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name')


@admin.register(VehicleUnit)
class VehicleUnitAdmin(admin.ModelAdmin):
    list_display = ('id', 'reg_number', 'vehicle_type', 'contact')

    search_fields = ('reg_number',)

    ordering = ['-id']
