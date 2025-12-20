from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin

from abb.models import Country, Currency


class CountrySerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    class Meta:
        model = Country
        fields = ('label', 'value', 'value_iso3', 'value_numeric', 'uf')


class CurrencySerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    class Meta:
        model = Currency
        fields = ('currency_code', 'currency_name',
                  'currency_symbol', 'currency_numeric', 'uf')
