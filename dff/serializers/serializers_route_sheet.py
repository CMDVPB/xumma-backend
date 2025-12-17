from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin

from abb.custom_serializers import SlugRelatedGetOrCreateField
from abb.serializers import CurrencySerializer
from app.serializers import UserSerializer
from att.models import Contact, Person, VehicleUnit
from ayy.models import RouteSheet
from ayy.serializers import ItemCostSerializer

User = get_user_model()


class RouteSheetSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    assigned_user = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    start_location = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    end_location = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    vehicle_tractor = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=VehicleUnit.objects.all(), write_only=True)
    vehicle_trailer = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=VehicleUnit.objects.all(), write_only=True)
    currency = CurrencySerializer(allow_null=True)

    drivers = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)

    route_sheet_itemcosts = ItemCostSerializer(many=True)

    def to_internal_value(self, data):
        # print('8271', data.get('rn'))

        try:
            data['trip'] = data['trip'].get('uf', None)
        except:
            pass
        try:
            data['start_location'] = data['start_location'].get('uf', None)
        except:
            pass
        try:
            data['end_location'] = data['end_location'].get('uf', None)
        except:
            pass
        try:
            data['vehicle_tractor'] = data['vehicle_tractor'].get('uf', None)
        except:
            pass
        try:
            data['vehicle_trailer'] = data['vehicle_trailer'].get('uf', None)
        except:
            pass
        try:
            driver_uf_list = []
            for driver in data.get('drivers', []):
                if not driver:  # None, {}, [], '', False
                    continue

                driver_uf = driver.get('uf')
                if driver_uf is not None:
                    driver_uf_list.append(driver_uf)

            data['drivers'] = driver_uf_list
        except:
            pass

        if 'rs_number' in data and data['rs_number'] == '':
            data['rs_number'] = None
        if 'assigned_user' in data and data['assigned_user'] == '':
            data['assigned_user'] = None
        if 'date_departure' in data and data['date_departure'] == '':
            data['date_departure'] = None
        if 'date_arrival' in data and data['date_arrival'] == '':
            data['date_arrival'] = None
        if 'km_departure' in data and data['km_departure'] == '':
            data['km_departure'] = None
        if 'km_arrival' in data and data['km_arrival'] == '':
            data['km_arrival'] = None
        if 'fuel_start' in data and data['fuel_start'] == '':
            data['fuel_start'] = None
        if 'fuel_end' in data and data['fuel_end'] == '':
            data['fuel_end'] = None
        if 'is_locked' in data and (data['is_locked'] == '' or data['is_locked'] == None):
            data['is_locked'] = False

        if 'currency' in data and data['currency'] == '':
            data['currency'] = None

        return super(RouteSheetSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        from dff.serializers.serializers_other import PersonSerializer
        from dff.serializers.serializers_other import VehicleUnitSerializer
        from dff.serializers.serializers_other import ContactSerializer
        from dff.serializers.serializers_trip import TripSimpleSerializer

        # print('8787', instance)

        response['assigned_user'] = UserSerializer(
            instance.assigned_user).data if instance.assigned_user else None
        response['trip'] = TripSimpleSerializer(
            instance.trip).data if instance.trip else None
        response['start_location'] = ContactSerializer(
            instance.start_location).data if instance.start_location else None
        response['end_location'] = ContactSerializer(
            instance.end_location).data if instance.end_location else None
        response['vehicle_tractor'] = VehicleUnitSerializer(
            instance.vehicle_tractor).data if instance.vehicle_tractor else None
        response['vehicle_trailer'] = VehicleUnitSerializer(
            instance.vehicle_trailer).data if instance.vehicle_trailer else None
        response['drivers'] = PersonSerializer(
            instance.drivers, many=True).data if instance.drivers else None

        return response

    def create(self, validated_data):
        # print('5670', validated_data)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance
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
        model = RouteSheet
        fields = ('assigned_user', 'rs_number', 'date_departure', 'date_arrival', 'km_departure', 'km_arrival', 'fuel_start', 'fuel_end',
                  'notes_date', 'notes_km', 'notes_fuel', 'date_issue', 'is_locked', 'uf',
                  'trip', 'start_location', 'end_location', 'vehicle_tractor', 'vehicle_trailer', 'currency',
                  'drivers', 'route_sheet_itemcosts',
                  )
        read_only_fields = ['trip']
