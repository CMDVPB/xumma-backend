from django.contrib import admin

from .models import Contact, ContactSite, ContactStatus, Contract, ContractReferenceDate, ContractReferenceDateTranslation, EmissionClass, PaymentTerm, VehicleBrand, Vehicle, VehicleDocument, VehicleUnit, Person, BankAccount


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'currency_code', 'company', 'iban_number')


@admin.register(ContactStatus)
class ContactStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'name', 'description')


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
    list_display = ('id', 'company',  'serial_number', 'code',
                    'label', 'description', 'is_system')


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


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'contact', 'title')

    search_fields = ('company', 'contact', 'title', 'uf',)

    ordering = ['-id']


@admin.register(ContractReferenceDate)
class ContractReferenceDateAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'code', 'label',
                    'usage', 'order', 'is_system')

    search_fields = ('company', 'uf')

    ordering = ['-id']


@admin.register(ContractReferenceDateTranslation)
class ContractReferenceDateTranslationAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference_date', 'language', 'label',)

    search_fields = ('reference_date', 'language', 'label', 'uf',)

    ordering = ['-id']


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'vehicle', 'document_type', 'file',)

    search_fields = ('uf',)

    ordering = ['-id']
