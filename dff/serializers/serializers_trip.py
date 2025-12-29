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
from att.models import Contact, Person, VehicleCompany, VehicleUnit
from att.serializers import BodyTypeSerializer, ModeTypeSerializer, StatusTypeSerializer, VehicleCompanySerializer
from axx.models import Load, Trip, TripDriver
from ayy.models import Comment, RouteSheet
from dff.serializers.serializers_load import LoadTripGetSerializer, LoadTripListSerializer
from dff.serializers.serializers_other import CommentSerializer, ContactSerializer, ContactTripListSerializer, HistorySerializer, PersonBasicReadSerializer, PersonSerializer, VehicleCompanyBasicReadSerializer, VehicleUnitBasicReadSerializer, VehicleUnitSerializer
from dff.serializers.serializers_route_sheet import RouteSheetSerializer


User = get_user_model()


class TripSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ("rn", "uf")


# class TripCreateUpdateSerializer(serializers.ModelSerializer):

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#         request = self.context.get('request')
#         user = getattr(request, "user", None)

#         if user and user.is_authenticated:
#             user_company = get_user_company(user)
#         else:
#             user_company = None

#         if user_company:
#             self.fields['assigned_user'].queryset = user_company.user.all()
#             # self.fields['drivers'].queryset = user_company.user.all()
#             self.fields['carrier'].queryset = Contact.objects.filter(
#                 company=user_company)
#             self.fields['vehicle_tractor'].queryset = VehicleCompany.objects.filter(
#                 company=user_company)
#             self.fields['vehicle_trailer'].queryset = VehicleCompany.objects.filter(
#                 company=user_company
#             )

#     # Slug based relations (write) with none()
#     assigned_user = serializers.SlugRelatedField(
#         allow_null=True, slug_field='uf', queryset=User.objects.none(), write_only=True
#     )
#     carrier = serializers.SlugRelatedField(
#         allow_null=True, slug_field='uf', queryset=Contact.objects.none(), write_only=True
#     )
#     vehicle_tractor = serializers.SlugRelatedField(
#         allow_null=True, slug_field='uf', queryset=VehicleCompany.objects.none(), write_only=True, required=False
#     )
#     vehicle_trailer = serializers.SlugRelatedField(
#         allow_null=True, slug_field='uf', queryset=VehicleCompany.objects.none(), write_only=True, required=False
#     )

#     # Slug based relations (write) without none()
#     person = serializers.SlugRelatedField(
#         allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True, required=False
#     )
#     currency = serializers.SlugRelatedField(
#         allow_null=True, slug_field='uf', queryset=Currency.objects.all(), required=False)
#     status = serializers.SlugRelatedField(
#         allow_null=True, slug_field='uf', queryset=StatusType.objects.all(), required=False)
#     mode = serializers.SlugRelatedField(
#         allow_null=True, slug_field='serial_number', queryset=ModeType.objects.all(), write_only=True, required=False
#     )
#     bt = serializers.SlugRelatedField(
#         allow_null=True, slug_field='serial_number', queryset=BodyType.objects.all(), write_only=True, required=False
#     )

#     trip_histories = HistorySerializer(many=True, read_only=True)
#     trip_comments = CommentSerializer(many=True, required=False)

#     # M2M Loads by UF

#     trip_route_sheets = serializers.ListField(
#         child=serializers.CharField(), write_only=True, required=False
#     )

#     trip_loads = serializers.ListField(
#         child=serializers.CharField(), write_only=True, required=False
#     )

#     drivers = serializers.ListField(
#         child=serializers.CharField(),
#         required=False,
#         write_only=True,
#     )

#     class Meta:
#         model = Trip
#         fields = (
#             'rn', 'assigned_user', 'date_order', 'is_locked', 'trip_number', 'date_trip', 'uf',
#             'km_departure', 'km_arrival', 'km_exit', 'km_entry',
#             'date_departure', 'date_arrival', 'trip_details', 'l_departure', 'l_arrival', 'trip_add_info', 'trip_comments', 'doc_lang',
#             'load_size', 'load_order',
#             'person', 'vehicle_tractor', 'vehicle_trailer', 'carrier', 'bt', 'currency', 'status', 'mode',
#             'trip_histories',
#             'trip_route_sheets', 'trip_loads', 'drivers',
#         )

#     def to_internal_value(self, data):
#         # print('6778', data.get('drivers'))

#         return super(TripCreateUpdateSerializer, self).to_internal_value(data)

#     # ----------------------------------------
#     # AUTO GET/CREATE by UF
#     # ----------------------------------------

#     def _get_or_create(self, model, uf):
#         if not uf:
#             return None
#         user = self.context["request"].user
#         user_company = get_user_company(user)
#         obj, _ = model.objects.get_or_create(uf=uf, defaults={
#             "company": user_company
#         })
#         return obj

#     # ----------------------------------------
#     # CLEAN INPUT DATA
#     # ----------------------------------------

#     def validate(self, data):

#         empty_to_none = [
#             'rn', 'mode', 'bt', 'currency',
#             'status', 'date_trip',
#             'date_departure', 'date_arrival'
#         ]

#         for field in empty_to_none:
#             if data.get(field) == "":
#                 data[field] = None

#         if data.get("is_locked") in ["", None]:
#             data["is_locked"] = False

#         return data

#     def create(self, validated_data):
#         trip_load_ufs = validated_data.pop("trip_loads", None)
#         route_sheets_ufs = validated_data.pop("trip_route_sheets", None)
#         drivers = validated_data.pop("drivers", None)
#         comments_data = validated_data.pop("trip_comments", [])

#         with transaction.atomic():
#             # Create main Trip instance
#             instance = Trip.objects.create(**validated_data)

#             # ✅ Update M2M loads
#             if trip_load_ufs is not None:
#                 # Get existing loads
#                 qs = Load.objects.filter(
#                     uf__in=trip_load_ufs,
#                     company=instance.company
#                 )

#                 # Find which UFs are missing
#                 found_ufs = set(qs.values_list('uf', flat=True))
#                 requested_ufs = set(trip_load_ufs)

#                 missing_ufs = list(requested_ufs - found_ufs)

#                 if missing_ufs:
#                     raise serializers.ValidationError({
#                         "trip_loads": [
#                             f"these_load_ufs_not_found: {', '.join(missing_ufs)}"
#                         ]
#                     })
#                 instance.trip_loads.set(qs)

#             # ✅ Update M2M: route sheets by UF
#             if route_sheets_ufs is not None:
#                 rs_qs = RouteSheet.objects.filter(
#                     uf__in=route_sheets_ufs,
#                     company=instance.company
#                 )

#                 # ✅ Extract the UF strings
#                 found_rs_ufs = set(rs_qs.values_list('uf', flat=True))
#                 requested_rs_ufs = set(route_sheets_ufs)
#                 missing_rs_ufs = list(requested_rs_ufs - found_rs_ufs)

#                 # print('6480', found_rs_ufs, found_rs_ufs)

#                 if missing_rs_ufs:
#                     raise serializers.ValidationError({
#                         "trip_route_sheets": [
#                             f"these_route_sheet_ufs_not_found: {', '.join(missing_rs_ufs)}"
#                         ]
#                     })

#                 instance.trip_route_sheets.set(rs_qs)

#             if drivers is not None:
#                 print('DRIVRE IS NOT NONE in CREATE', drivers)
#                 self._update_trip_drivers(instance, drivers)

#             # Create comments
#             for c in comments_data:
#                 Comment.objects.create(trip=instance, **c)

#             return instance

#     def update(self, instance, validated_data):

#         # Extract M2M and nested data
#         trip_load_ufs = validated_data.pop("trip_loads", None)
#         route_sheets_ufs = validated_data.pop("trip_route_sheets", None)
#         drivers = validated_data.pop("drivers", None)
#         comments_data = validated_data.pop('trip_comments', [])

#         print('6780', drivers)

#         # Normal fields update
#         for key, value in validated_data.items():
#             setattr(instance, key, value)

#         with transaction.atomic():
#             instance.save()

#             # ✅ Update M2M loads
#             if trip_load_ufs is not None:
#                 # Get existing loads
#                 qs = Load.objects.filter(
#                     uf__in=trip_load_ufs,
#                     company=instance.company
#                 )

#                 # Find which UFs are missing
#                 found_ufs = set(qs.values_list('uf', flat=True))
#                 requested_ufs = set(trip_load_ufs)

#                 missing_ufs = list(requested_ufs - found_ufs)

#                 if missing_ufs:
#                     raise serializers.ValidationError({
#                         "trip_loads": [
#                             f"these_load_ufs_not_found: {', '.join(missing_ufs)}"
#                         ]
#                     })
#                 instance.trip_loads.set(qs)

#             # ✅ Update M2M: route sheets by UF
#             if route_sheets_ufs is not None:
#                 rs_qs = RouteSheet.objects.filter(
#                     uf__in=route_sheets_ufs,
#                     company=instance.company
#                 )

#                 # ✅ Extract the UF strings
#                 found_rs_ufs = set(rs_qs.values_list('uf', flat=True))
#                 requested_rs_ufs = set(route_sheets_ufs)
#                 missing_rs_ufs = list(requested_rs_ufs - found_rs_ufs)

#                 # print('6480', found_rs_ufs, found_rs_ufs)

#                 if missing_rs_ufs:
#                     raise serializers.ValidationError({
#                         "trip_route_sheets": [
#                             f"these_route_sheet_ufs_not_found: {', '.join(missing_rs_ufs)}"
#                         ]
#                     })

#                 instance.trip_route_sheets.set(rs_qs)

#             if drivers is not None:
#                 print('DRIVRE IS NOT NONE', drivers)
#                 self._update_trip_drivers(instance, drivers)

#             # ✅ Update comments (simple version)
#             if comments_data:
#                 instance.trip_comments.all().delete()
#                 for c in comments_data:
#                     Comment.objects.create(trip=instance, **c)

#         return instance

#     ### OUTPUT ###

#     def to_representation(self, instance):
#         data = super().to_representation(instance)

#         data['assigned_user'] = UserSerializer(
#             instance.assigned_user
#         ).data if instance.assigned_user else None

#         data['currency'] = CurrencySerializer(
#             instance.currency
#         ).data if instance.currency else None
#         data['mode'] = ModeTypeSerializer(
#             instance.mode
#         ).data if instance.mode else None
#         data['bt'] = BodyTypeSerializer(
#             instance.bt
#         ).data if instance.bt else None
#         data['person'] = PersonSerializer(
#             instance.person
#         ).data if instance.person else None

#         data['vehicle_tractor'] = VehicleCompanySerializer(
#             instance.vehicle_tractor
#         ).data if instance.vehicle_tractor else None

#         data['vehicle_trailer'] = VehicleCompanySerializer(
#             instance.vehicle_trailer
#         ).data if instance.vehicle_trailer else None

#         data['trip_route_sheets'] = RouteSheetSerializer(
#             instance.trip_route_sheets.all(), many=True
#         ).data if instance.trip_route_sheets.exists() else None

#         # Route sheet number
#         rs = instance.trip_route_sheets.first()
#         data['rs_number'] = rs.rs_number if rs else None

#         # M2M Loads actual data
#         data['trip_route_sheets'] = RouteSheetSerializer(
#             instance.trip_route_sheets.all(), many=True
#         ).data

#         # # M2M Loads actual data
#         # data['trip_loads'] = LoadTripGetSerializer(
#         #     instance.trip_loads.all(), many=True
#         # ).data

#         return data

#     def _update_trip_drivers(self, instance, drivers):
#         """
#         drivers: list[str] (UFs)
#         """

#         users_qs = User.objects.filter(
#             uf__in=drivers,
#             company=instance.company
#         )

#         found_ufs = set(users_qs.values_list("uf", flat=True))
#         requested_ufs = set(drivers)
#         missing_ufs = requested_ufs - found_ufs

#         if missing_ufs:
#             raise serializers.ValidationError({
#                 "drivers": [
#                     f"drivers_not_in_company_or_not_found: {', '.join(missing_ufs)}"
#                 ]
#             })

#         TripDriver.objects.filter(trip=instance).delete()

#         TripDriver.objects.bulk_create([
#             TripDriver(trip=instance, driver=user)
#             for user in users_qs
#         ])


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
            self.fields['drivers'].queryset = VehicleCompany.objects.filter(
                company=user_company
            )
    # Slug based relations (write) with none()
    drivers = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=User.objects.none())

    # Slug based relations (write) with out none()
    status = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=StatusType.objects.all())

    carrier = ContactTripListSerializer(allow_null=True)
    vehicle_tractor = VehicleCompanyBasicReadSerializer(allow_null=True)
    vehicle_trailer = VehicleCompanyBasicReadSerializer(allow_null=True)
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
        fields = ('rn', 'num_loads', 'load_size', 'date_order', 'uf',
                  'carrier', 'status', 'bt', 'mode', 'vehicle_tractor', 'vehicle_trailer',
                  'trip_loads', 'trip_comments', 'totals_trip',
                  'drivers'
                  )


class TripSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    assigned_user = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all())
    carrier = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    person = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    vehicle_tractor = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=VehicleCompany.objects.all(), write_only=True)
    vehicle_trailer = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=VehicleCompany.objects.all(), write_only=True)

    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Currency.objects.all())
    status = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=StatusType.objects.all())

    trip_loads = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Load.objects.all(), write_only=True)
    trip_route_sheets = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=RouteSheet.objects.all(), write_only=True)

    drivers = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=User.objects.all())

    mode = ModeTypeSerializer(allow_null=True)
    bt = BodyTypeSerializer(allow_null=True)

    trip_comments = CommentSerializer(many=True)
    trip_histories = HistorySerializer(many=True, read_only=True)

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
        response['vehicle_tractor'] = VehicleCompanySerializer(
            instance.vehicle_tractor).data if instance.vehicle_tractor else None
        response['vehicle_trailer'] = VehicleCompanySerializer(
            instance.vehicle_trailer).data if instance.vehicle_trailer else None

        response['trip_loads'] = LoadTripGetSerializer(
            instance.trip_loads, many=True).data if instance.trip_loads else None
        response['trip_route_sheets'] = RouteSheetSerializer(
            instance.trip_route_sheets, many=True).data if instance.trip_route_sheets else None

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

    class Meta:
        model = Trip
        fields = ('rn', 'assigned_user', 'date_order', 'person', 'vehicle_tractor', 'incl_loads_costs', 'doc_lang',
                  'vehicle_trailer', 'carrier', 'load_size', 'load_order', 'mode', 'bt', 'currency', 'status', 'is_locked',
                  'km_departure', 'km_arrival', 'km_exit', 'km_entry', 'trip_number', 'date_trip', 'date_departure', 'date_arrival',
                  'trip_details', 'l_departure', 'l_arrival', 'trip_add_info', 'trip_loads', 'trip_comments', 'trip_histories', 'uf',
                  'trip_route_sheets', 'drivers',
                  )


class TripTruckSerializer(serializers.ModelSerializer):
    tractor = serializers.CharField(
        source='vehicle_tractor.reg_number', read_only=True)
    trailer = serializers.CharField(
        source='vehicle_trailer.reg_number', read_only=True)

    class Meta:
        model = Trip
        fields = (
            'rn',


            'tractor',

            'trailer',
            'uf',
        )
