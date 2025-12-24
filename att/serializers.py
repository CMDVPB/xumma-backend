from collections import defaultdict
from django.db import transaction
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin

from abb.models import BodyType, Incoterm, ModeType, StatusType
from abb.utils import get_request_language
from app.models import CategoryGeneral, TypeGeneral
from att.models import EmissionClass, VehicleBrand, VehicleCompany


class TypeGeneralSerializer(serializers.ModelSerializer):

    class Meta:
        model = TypeGeneral
        fields = ('serial_number', 'code', 'label', 'uf')


class CategoryGeneralSerializer(serializers.ModelSerializer):

    class Meta:
        model = CategoryGeneral
        fields = ('serial_number', 'code', 'label', 'uf')


class IncotermSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = Incoterm
        fields = ('it',  'description', 'serial_number', 'uf')


class ModeTypeSerializer(WritableNestedModelSerializer):
    serial_number = serializers.CharField(read_only=True)

    class Meta:
        model = ModeType
        fields = ('mt',  'description', 'serial_number', 'uf')


class BodyTypeSerializer(serializers.ModelSerializer):
    serial_number = serializers.CharField(read_only=True)

    class Meta:
        model = BodyType
        fields = ('bt', 'description', 'serial_number', 'uf')


class EmissionClassdSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = EmissionClass
        fields = ('code', 'name', 'description', 'is_active', 'uf')


class VehicleBrandSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = VehicleBrand
        fields = ('name', 'serial_number', 'is_active', 'uf')


class StatusTypeSerializer(WritableNestedModelSerializer):
    serial_number = serializers.CharField(read_only=True)
    label = serializers.SerializerMethodField(read_only=True)

    def get_label(self, obj):
        request = self.context.get("request")
        lang = get_request_language(request)

        translation = obj.translations.filter(language=lang).first()

        if translation:
            return translation.label

        # fallback to Romanian
        fallback = obj.translations.filter(language="ro").first()
        return fallback.label if fallback else obj.code

    class Meta:
        model = StatusType
        fields = ('serial_number', 'order_number',
                  'description', 'label', 'uf')


class VehicleCompanySerializer(WritableNestedModelSerializer):
    brand = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=VehicleBrand.objects.all())
    vehicle_body = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=BodyType.objects.all())
    emission_class = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=EmissionClass.objects.all())

    def _empty_strings_to_none(self, data, fields):
        for field in fields:
            if data.get(field) == '':
                data[field] = None
        return data

    # vehicle_gendocs = GenDocSerializer(many=True)
    def to_internal_value(self, data):
        data = data.copy()  # IMPORTANT

        data = self._empty_strings_to_none(data, [
            'buy_price',
            'change_oil_interval',
            'consumption_summer',
            'consumption_winter',
            'height',
            'interval_taho',
            'length',
            'sell_price',
            'tank_volume',
            'volume_capacity',
            'weight_capacity',
            'width',
        ])

        return super().to_internal_value(data)

    def create(self, validated_data):
        # print('1614:', validated_data)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        # print('3347', validated_data, instance)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance with atomic
        with transaction.atomic():
            instance = super(NestedUpdateMixin, self).update(
                instance,
                validated_data,
            )
            self.update_or_create_reverse_relations(
                instance, reverse_relations)
            self.delete_reverse_relations_if_need(instance, reverse_relations)
            instance.refresh_from_db()
            return instance

    class Meta:
        model = VehicleCompany
        fields = ('reg_number', 'vin', 'vehicle_type', 'is_available', 'is_archived', 'uf',
                  'length', 'width', 'height', 'weight_capacity', 'volume_capacity',
                  'tank_volume', 'change_oil_interval', 'consumption_summer', 'consumption_winter', 'buy_price', 'sell_price',
                  'interval_taho', 'last_date_unload_taho', 'comment',
                  'brand', 'vehicle_body', 'emission_class',
                  )
