from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin


from abb.serializers import CountrySerializer
from app.models import Company, CompanySettings


class CompanySettingsSerializer(WritableNestedModelSerializer):
    class Meta:
        model = CompanySettings
        fields = (
            "diesel_tank_volume_l",
            "adblue_tank_volume_l",
            'uf',
        )


class CompanySerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    country_code_legal = CountrySerializer(allow_null=True)
    country_code_post = CountrySerializer(allow_null=True)

    def to_internal_value(self, data):

        if 'country_code_legal' in data and data['country_code_legal'] == '':
            data['countrycodelegal'] = None
        if 'country_code_post' in data and data['country_code_post'] == '':
            data['countrycodepost'] = None
        if 'logo' in data and data['logo'] == '':
            data['logo'] = None
        if 'stamp' in data and data['stamp'] == '':
            data['stamp'] = None

        return super(CompanySerializer, self).to_internal_value(data)

    class Meta:
        model = Company
        fields = ('logo', 'stamp', 'company_name', 'fiscal_code', 'vat_code', 'uf',
                  'email', 'phone', 'messanger',
                  'zip_code_legal', 'city_legal', 'address_legal', 'county_legal', 'sect_legal',
                  'zip_code_post', 'city_post', 'address_post', 'county_post', 'comment',
                  'country_code_legal', 'country_code_post',
                  )
