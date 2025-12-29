from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import QuerySet, Prefetch, Q, F
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.serializers import CountrySerializer
from abb.utils import get_user_company
from att.models import ContactSite
from ayy.models import ColliType, Detail, Entry
from dff.serializers.serializers_other import ContactBasicReadSerializer, ContactSerializer, ContactSiteBasicReadSerializer, ContactSiteSerializer


class ColliTypeSerializer(WritableNestedModelSerializer):
    class Meta:
        model = ColliType
        fields = ('serial_number', 'code', 'label', 'ldm', 'is_system', 'uf')


class DetailSerializer(WritableNestedModelSerializer):

    colli_type = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=ColliType.objects.all())

    class Meta:
        model = Detail
        fields = ('pieces', 'weight', 'ldm', 'volume', 'dims', 'uf',
                  'colli_type',
                  )


class EntryBasicReadListSerializer(WritableNestedModelSerializer):

    shipper = ContactSiteBasicReadSerializer(allow_null=True)
    country_load = CountrySerializer(allow_null=True)
    entry_details = DetailSerializer(many=True)

    class Meta:
        model = Entry
        fields = ('action', 'order', 'zip_load', 'city_load', 'date_load', 'time_load_min', 'time_load_max', 'uf',
                  'palletexchange', 'tail_lift', 'dangerousgoods', 'dangerousgoods_class', 'temp_control', 'temp_control_details',
                  'shipper', 'country_load', 'entry_details'
                  )


class EntrySerializer(WritableNestedModelSerializer):
    shipper = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=ContactSite.objects.all())
    country_load = CountrySerializer(allow_null=True)

    entry_details = DetailSerializer(many=True)

    def to_internal_value(self, data):
        try:
            data['shipper'] = data['shipper'].get('uf', None)
        except:
            pass

        if 'shipper' in data and data['shipper'] == '':
            data['shipper'] = None
        if 'country_load' in data and data['country_load'] == '':
            data['country_load'] = None
        if 'date_load' in data and data['date_load'] == '':
            data['date_load'] = None
        if 'time_load_min' in data and data['time_load_min'] == '':
            data['time_load_min'] = None
        if 'time_load_max' in data and data['time_load_max'] == '':
            data['time_load_max'] = None
        if 'order' in data and data['order'] == '':
            data['order'] = None

        return super(EntrySerializer, self).to_internal_value(data)

    def to_representation(self, instance):

        response = super().to_representation(instance)

        # response['load'] = instance.load.id if instance.load and instance.load.id else None

        response['shipper'] = ContactSiteSerializer(
            instance.shipper).data if instance.shipper else None

        return response

    def create(self, validated_data):
        # print('6549:', validated_data)
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
        # print('8523', validated_data, instance)
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
        model = Entry
        fields = ('action', 'shipper', 'date_load', 'time_load_min', 'time_load_max', 'is_stackable',
                  'shipperinstructions1', 'shipperinstructions2', 'tail_lift', 'palletexchange',
                  'dangerousgoods', 'dangerousgoods_class', 'temp_control', 'temp_control_details', 'order',
                  'country_load', 'zip_load', 'city_load', 'entry_details', 'uf')
