from django.contrib import admin

from .models import BodyType, Country, Currency, ExchangeRate, StatusType, StatusTypeTranslation


@admin.register(BodyType)
class BodyTypeAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'bt', 'description')


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'value', 'label',
                    'value_iso3', 'value_numeric', 'id')

    search_fields = ('label', 'value', 'value_iso3', 'value_numeric')


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'currency_code',
                    'currency_name', 'currency_symbol', 'currency_numeric', 'uf')


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):

    def nbr(self, obj):
        return bool(obj.metadata_nbr)
    nbr.boolean = True

    def nbm(self, obj):
        return bool(obj.metadata_nbm)
    nbm.boolean = True

    def nbu(self, obj):
        return bool(obj.metadata_nbu)
    nbu.boolean = True

    list_display = ('date', 'nbr', 'nbm', 'nbu')


@admin.register(StatusType)
class StatusTypeAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'order_number', 'st', 'description')


@admin.register(StatusTypeTranslation)
class StatusTypeTranslationAdmin(admin.ModelAdmin):
    list_display = ('status', 'language', 'label')
