from collections import defaultdict
from django.db import transaction
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin

from abb.models import BodyType, Incoterm, ModeType, StatusType
from att.models import EmissionClass, VehicleBrand, VehicleCompany


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

    class Meta:
        model = StatusType
        fields = ('st', 'description', 'serial_number', 'uf')


class VehicleCompanySerializer(WritableNestedModelSerializer):
    brand = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=VehicleBrand.objects.all())
    vehicle_body = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=BodyType.objects.all())
    emission_class = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=EmissionClass.objects.all())

    # vehicle_gendocs = GenDocSerializer(many=True)

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
                  'brand', 'vehicle_body', 'emission_class',
                  )
