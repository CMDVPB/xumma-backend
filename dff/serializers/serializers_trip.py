from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.custom_serializers import SlugRelatedGetOrCreateField
from abb.models import BodyType, Currency, ModeType, StatusType
from abb.serializers import CurrencySerializer
from abb.utils import get_user_company
from app.serializers import UserSerializer
from att.models import Contact, Person, Vehicle, VehicleUnit
from att.serializers import BodyTypeSerializer, ModeTypeSerializer, StatusTypeSerializer, VehicleSerializer
from axx.models import Load, Trip, TripDriver
from ayy.models import Comment, Entry, RouteSheet
from ayy.serializers import ItemCostSerializer
from dff.serializers.serializers_load import LoadTripGetSerializer, LoadTripListSerializer
from dff.serializers.serializers_other import CommentSerializer, ContactSerializer, ContactTripListSerializer, HistorySerializer, PersonBasicReadSerializer, PersonSerializer, VehicleBasicReadSerializer, VehicleUnitBasicReadSerializer, VehicleUnitSerializer


User = get_user_model()


class TripSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ("rn", "uf")


class TripListSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get('request')
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            user_company = get_user_company(user)
        else:
            user_company = None

        if user_company:
            self.fields['drivers'].queryset = Vehicle.objects.filter(
                company=user_company
            )
    # Slug based relations (write) with none()
    drivers = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=User.objects.none())

    # Slug based relations (write) with out none()
    status = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=StatusType.objects.all())

    carrier = ContactTripListSerializer(allow_null=True)
    vehicle_tractor = VehicleBasicReadSerializer(allow_null=True)
    vehicle_trailer = VehicleBasicReadSerializer(allow_null=True)
    bt = BodyTypeSerializer(allow_null=True)
    mode = ModeTypeSerializer(allow_null=True)

    trip_loads = LoadTripListSerializer(many=True)
    trip_comments = CommentSerializer(many=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        # print('3748', instance)

        # Check reverse FK: trip_route_sheets
        try:
            trip_route_sheets_qs = getattr(instance, 'trip_route_sheets', None)
            if trip_route_sheets_qs and trip_route_sheets_qs.exists():
                response['rs_number'] = trip_route_sheets_qs.first().rs_number
            else:
                response['rs_number'] = None
        except:
            response['rs_number'] = None
            pass

        return response

    class Meta:
        model = Trip
        fields = ('rn', 'num_loads', 'load_size', 'trip_type', 'date_order', 'date_end', 'uf',
                  'carrier', 'status', 'bt', 'mode', 'vehicle_tractor', 'vehicle_trailer',
                  'trip_loads', 'trip_comments', 'totals_trip',
                  'rs_number',
                  'drivers',
                  )


class TripSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    loading_points_count = serializers.SerializerMethodField()  # Add the read-only field
    unloading_points_count = serializers.SerializerMethodField()  # Add the read-only field

    assigned_user = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all())
    carrier = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    person = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    driver = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Person.objects.filter(is_driver=True), write_only=True)
    vehicle_tractor = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.all(), write_only=True)
    vehicle_trailer = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.all(), write_only=True)

    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Currency.objects.all())
    status = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=StatusType.objects.all())

    drivers = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=User.objects.all())

    mode = ModeTypeSerializer(allow_null=True)
    bt = BodyTypeSerializer(allow_null=True)

    trip_loads = LoadTripListSerializer(many=True, read_only=True)
    trip_comments = CommentSerializer(many=True)
    trip_histories = HistorySerializer(many=True, read_only=True)
    trip_itemcosts = ItemCostSerializer(many=True)

    def to_internal_value(self, data):
        # print('8274', data.get('drivers'))

        try:
            data['carrier'] = data['carrier'].get('uf', None)
        except:
            pass
        try:
            data['person'] = data['person'].get('uf', None)
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

        if 'rn' in data and data['rn'] == '':
            data['rn'] = None
        if 'mode' in data and data['mode'] == '':
            data['mode'] = None
        if 'bt' in data and data['bt'] == '':
            data['bt'] = None
        if 'currency' in data and data['currency'] == '':
            data['currency'] = None
        if 'status' in data and data['status'] == '':
            data['status'] = None
        if 'is_locked' in data and (data['is_locked'] == '' or data['is_locked'] == None):
            data['is_locked'] = False
        if 'date_trip' in data and data['date_trip'] == '':
            data['date_trip'] = None
        if 'date_departure' in data and data['date_departure'] == '':
            data['date_departure'] = None
        if 'date_arrival' in data and data['date_arrival'] == '':
            data['date_arrival'] = None

        return super(TripSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        # print('8787', instance)

        # response['assigned_user'] = UserSerializer(
        #     instance.assigned_user).data if instance.assigned_user else None
        response['carrier'] = ContactSerializer(
            instance.carrier).data if instance.carrier else None
        response['person'] = PersonSerializer(
            instance.person).data if instance.person else None
        response['vehicle_tractor'] = VehicleSerializer(
            instance.vehicle_tractor).data if instance.vehicle_tractor else None
        response['vehicle_trailer'] = VehicleSerializer(
            instance.vehicle_trailer).data if instance.vehicle_trailer else None

        # Check reverse FK: trip_route_sheets
        try:
            trip_route_sheets_qs = getattr(instance, 'trip_route_sheets', None)
            if trip_route_sheets_qs and trip_route_sheets_qs.exists():
                response['rs_number'] = trip_route_sheets_qs.first().rs_number
            else:
                response['rs_number'] = None
        except:
            response['rs_number'] = None
            pass

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

    def get_loading_points_count(self, instance):
        return (
            Entry.objects
            .filter(load__trip=instance, action='loading')
            .count()
        )

    def get_unloading_points_count(self, instance):
        return (
            Entry.objects
            .filter(load__trip=instance, action='unloading')
            .count()
        )

    class Meta:
        model = Trip
        fields = ('rn', 'assigned_user', 'date_order', 'date_end', 'person', 'driver', 'vehicle_tractor', 'incl_loads_costs', 'doc_lang',
                  'vehicle_trailer', 'carrier', 'load_size', 'trip_type', 'load_order', 'mode', 'bt', 'currency', 'status', 'is_locked',
                  'km_departure', 'km_arrival', 'km_exit', 'km_entry', 'trip_number', 'date_trip', 'date_departure', 'date_arrival',
                  'trip_details', 'l_departure', 'l_arrival', 'trip_add_info', 'trip_comments', 'trip_histories', 'uf',
                  'rs_number',
                  'drivers', 'trip_itemcosts', 'trip_loads',
                  # 👇 computed, read-only
                  'loading_points_count',
                  'unloading_points_count'
                  )


class TripTruckSerializer(serializers.ModelSerializer):
    vehicle_tractor = serializers.CharField(
        source='vehicle_tractor.reg_number', read_only=True)
    vehicle_trailer = serializers.CharField(
        source='vehicle_trailer.reg_number', read_only=True)

    class Meta:
        model = Trip
        fields = ('rn', 'vehicle_tractor', 'vehicle_trailer', 'uf',
                  )
