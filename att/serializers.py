from collections import defaultdict
from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import SlugRelatedField
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin

from abb.models import BodyType, Incoterm, ModeType, StatusType
from abb.serializers_drf_writable import CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer
from abb.utils import get_request_language, get_user_company
from app.models import CategoryGeneral, TypeGeneral
from att.models import Contact, EmissionClass, RouteSheetStockBatch, VehicleBrand, Vehicle


class TypeGeneralSerializer(serializers.ModelSerializer):

    class Meta:
        model = TypeGeneral
        fields = ('serial_number', 'code', 'label', 'is_system', 'uf')
        read_only_fields = ['is_system']


class CategoryGeneralSerializer(serializers.ModelSerializer):

    class Meta:
        model = CategoryGeneral
        fields = ('serial_number', 'code', 'label', 'is_system', 'uf')
        read_only_fields = ['is_system']


class IncotermSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = Incoterm
        fields = ('serial_number',  'code', 'label', 'uf')


class ModeTypeSerializer(WritableNestedModelSerializer):
    serial_number = serializers.CharField(read_only=True)

    class Meta:
        model = ModeType
        fields = ('serial_number', 'code', 'label', 'uf')


class BodyTypeSerializer(serializers.ModelSerializer):
    serial_number = serializers.CharField(read_only=True)

    class Meta:
        model = BodyType
        fields = ('serial_number', 'code', 'label', 'uf')


class EmissionClassSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = EmissionClass
        fields = ('code', 'label', 'description',
                  'is_active', 'is_system', 'uf')


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


class VehicleContactSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):
    class Meta:
        model = Vehicle
        fields = ('reg_number', 'vehicle_type', 'comment', 'uf',
                  )


class VehicleSerializer(WritableNestedModelSerializer):

    contact = SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all())
    brand = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=VehicleBrand.objects.all())
    vehicle_category = serializers.SlugRelatedField(
        allow_null=True, slug_field='code', queryset=CategoryGeneral.objects.all())
    vehicle_category_type = serializers.SlugRelatedField(
        allow_null=True, slug_field='code', queryset=TypeGeneral.objects.all())
    vehicle_body = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=BodyType.objects.all())
    emission_class = serializers.SlugRelatedField(
        allow_null=True, slug_field='code', queryset=EmissionClass.objects.all())

    # vehicle_gendocs = GenDocSerializer(many=True)

    def _empty_strings_to_none(self, data, fields):
        for field in fields:
            if data.get(field) == '':
                data[field] = None
        return data

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

    # def create(self, validated_data):
    #     # print('1614:', validated_data)
    #     relations, reverse_relations = self._extract_relations(validated_data)

    #     # Create or update direct relations (foreign key, one-to-one)
    #     self.update_or_create_direct_relations(
    #         validated_data,
    #         relations,
    #     )

    #     # Create instance with atomic
    #     with transaction.atomic():
    #         instance = super(NestedCreateMixin,
    #                          self).create(validated_data)
    #         self.update_or_create_reverse_relations(
    #             instance, reverse_relations)

    #     return instance

    # def update(self, instance, validated_data):
    #     # print('3347', validated_data, instance)
    #     relations, reverse_relations = self._extract_relations(validated_data)

    #     # Create or update direct relations (foreign key, one-to-one)
    #     self.update_or_create_direct_relations(
    #         validated_data,
    #         relations,
    #     )

    #     # Update instance with atomic
    #     with transaction.atomic():
    #         instance = super(NestedUpdateMixin, self).update(
    #             instance,
    #             validated_data,
    #         )
    #         self.update_or_create_reverse_relations(
    #             instance, reverse_relations)
    #         self.delete_reverse_relations_if_need(instance, reverse_relations)
    #         instance.refresh_from_db()
    #         return instance

    class Meta:
        model = Vehicle
        fields = ('id', 'reg_number', 'vin', 'vehicle_type', 'date_registered', 'is_available', 'is_archived', 'uf',
                  'length', 'width', 'height', 'weight_capacity', 'volume_capacity',
                  'tank_volume', 'change_oil_interval', 'consumption_summer', 'consumption_winter', 'buy_price', 'sell_price', 'km_initial',
                  'interval_taho', 'last_date_unload_taho', 'comment',
                  'brand', 'vehicle_category', 'vehicle_category_type', 'vehicle_body', 'emission_class',
                  'contact',
                  )


class RouteSheetStockBatchSerializer(WritableNestedModelSerializer):
    class Meta:
        model = RouteSheetStockBatch
        fields = ('series', 'received_at', 'number_from', 'number_to', 'total_count', 'uf',
                  'used_count', 'notes', 'available_count',
                  )
        read_only_fields = ("company",)

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        company = get_user_company(user)

        return RouteSheetStockBatch.objects.create(
            company=company,
            **validated_data
        )
