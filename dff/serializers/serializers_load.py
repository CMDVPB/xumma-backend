

from django.utils import timezone
from collections import defaultdict
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers
from rest_framework.serializers import SlugRelatedField
from django.db import IntegrityError

from abb.custom_serializers import SlugRelatedGetOrCreateField
from abb.models import BodyType, Currency, Incoterm, ModeType, StatusType
from abb.serializers import CurrencySerializer
from abb.utils import get_user_company
from app.models import CategoryGeneral
from app.serializers import UserBasicSerializer, UserSerializer
from att.models import Contact, PaymentTerm, Person, Vehicle, VehicleUnit
from att.serializers import BodyTypeSerializer, IncotermSerializer, ModeTypeSerializer, StatusTypeSerializer, VehicleSerializer
from axx.models import Ctr, Exp, Inv, Load, LoadEvent, Tor, Trip
from ayy.models import CMR, CMRStockMovement
from dff.serializers.serializers_bce import ImageUploadOutSerializer, ImageUploadUFOnlySerializer
from dff.serializers.serializers_ctr import CtrSerializer
from dff.serializers.serializers_entry_detail import EntryBasicReadListSerializer, EntrySerializer
from dff.serializers.serializers_exp import ExpSerializer
from dff.serializers.serializers_inv import InvSerializer
from dff.serializers.serializers_item_inv import ItemInvSerializer
from dff.serializers.serializers_other import CMRSerializer, CommentSerializer, ContactBasicReadSerializer, ContactSerializer, HistorySerializer, \
    PaymentTermSerializer, PersonSerializer, VehicleUnitSerializer
from dff.serializers.serializers_tor import TorSerializer


User = get_user_model()

LOAD_EVENT_FLAG_MAP = {
    "shipper_confirmed": "SHIPPER_CONFIRMED",
    "shipper_email_sent": "SHIPPER_EMAIL_SENT",
    "docs_sent_cnee_broker": "DOCS_SENT_CNEE_BROKER",
}


class LoadEventOutSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.uf", read_only=True)

    class Meta:
        model = LoadEvent
        fields = (
            "uf",
            "event_type",
            "created_at",
            "created_by",
        )


class LoadEventSerializer(WritableNestedModelSerializer):

    class Meta:
        model = LoadEvent
        fields = ('event_type', 'created_at', 'created_by', 'uf')


class LoadTripListSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    currency_code = serializers.CharField(
        source='currency.currency_code',
        read_only=True
    )

    class Meta:
        model = Load
        fields = ('freight_price', 'currency_code', 'date_order', 'uf')


class TorLoadListSerializer(WritableNestedModelSerializer):

    carrier = ContactSerializer(allow_null=True)
    vehicle_tractor = VehicleSerializer(allow_null=True)
    vehicle_trailer = VehicleSerializer(allow_null=True)

    class Meta:
        model = Tor
        fields = ('is_tor', 'uf',
                  'carrier', 'vehicle_tractor',
                  'vehicle_trailer'
                  )


class LoadBasicReadSerializer(WritableNestedModelSerializer):
    bill_to = ContactBasicReadSerializer(allow_null=True)
    status = StatusTypeSerializer(allow_null=True)
    currency = CurrencySerializer(allow_null=True)
    load_iteminvs = ItemInvSerializer(many=True)

    class Meta:
        model = Load
        fields = ('sn', 'uf'
                  'bill_to', 'currency', 'status',
                  'load_iteminvs',
                  )


class LoadTripGetSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    ''' used only for list view GET requests '''

    assigned_user = UserBasicSerializer(allow_null=True)
    bill_to = ContactBasicReadSerializer(allow_null=True)
    mode = ModeTypeSerializer(allow_null=True)
    bt = BodyTypeSerializer(allow_null=True)
    currency = CurrencySerializer(allow_null=True)
    status = StatusTypeSerializer(allow_null=True)
    incoterm = IncotermSerializer(allow_null=True)

    carrier = ContactBasicReadSerializer(allow_null=True)
    entry_loads = EntryBasicReadListSerializer(many=True)
    load_iteminvs = ItemInvSerializer(many=True)
    load_comments = CommentSerializer(many=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        # print('3748', instance)

        response['trip'] = instance.trip.uf if instance.trip else None
        response['trip_num'] = instance.trip.rn if instance.trip else None

        response['load_tors'] = TorSerializer(
            instance.load_tors, many=True).data if instance.load_tors else None
        response['load_exps'] = ExpSerializer(
            instance.load_exps, many=True).data if instance.load_exps else None

        return response

    class Meta:
        model = Load
        fields = ('sn', 'date_order', 'customer_ref', 'customer_notes', 'load_detail', 'load_size', 'load_add_ons', 'load_address',
                  'unload_address', 'hb', 'mb', 'booking_number', 'comment1', 'uf',
                  'assigned_user', 'bill_to', 'mode', 'bt', 'currency', 'status', 'incoterm', 'carrier',
                  'load_comments', 'load_tors', 'entry_loads', 'load_iteminvs',
                  )


class LoadListSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    ''' used only for list view GET requests '''

    assigned_user = UserBasicSerializer(allow_null=True)
    bill_to = ContactBasicReadSerializer(allow_null=True)
    mode = ModeTypeSerializer(allow_null=True)
    bt = BodyTypeSerializer(allow_null=True)
    currency = CurrencySerializer(allow_null=True)
    status = StatusTypeSerializer(allow_null=True)
    incoterm = IncotermSerializer(allow_null=True)
    vehicle_tractor = VehicleSerializer(allow_null=True)
    vehicle_trailer = VehicleSerializer(allow_null=True)

    carrier = ContactBasicReadSerializer(allow_null=True)
    entry_loads = EntryBasicReadListSerializer(many=True)
    load_iteminvs = ItemInvSerializer(many=True)
    load_comments = CommentSerializer(many=True)
    load_tors = TorLoadListSerializer(many=True)
    load_events = LoadEventOutSerializer(many=True)
    load_imageuploads = ImageUploadUFOnlySerializer(many=True, read_only=True)

    payment_term_days = serializers.IntegerField(
        source='payment_term.payment_term_days',
        read_only=True
    )

    def to_representation(self, instance):
        from dff.serializers.serializers_trip import TripTruckSerializer

        response = super().to_representation(instance)

        # print('3748', instance)

        response['trip'] = TripTruckSerializer(
            instance.trip).data if instance.trip else None

        return response

    class Meta:
        model = Load
        fields = ('sn', 'date_order', 'customer_ref', 'customer_notes', 'load_detail', 'load_size', 'freight_price', 'uf',
                  'date_due', 'load_type', 'load_add_ons',
                  'is_active', 'is_loaded', 'is_cleared', 'is_unloaded', 'is_invoiced', 'is_signed', 'is_paid',
                  'date_loaded', 'date_cleared', 'date_unloaded', 'date_invoiced', 'date_signed',
                  'load_address', 'unload_address', 'hb', 'mb', 'booking_number', 'comment1',
                  'assigned_user', 'bill_to', 'mode', 'bt', 'currency', 'status', 'incoterm', 'carrier', 'vehicle_tractor', 'vehicle_trailer',
                  'load_comments', 'load_tors', 'entry_loads', 'load_iteminvs', 'load_events',
                  'load_imageuploads',

                  'payment_term_days',


                  )
        read_only_fields = ['load_events', 'is_invoiced', 'date_invoiced']


class LoadSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get('request')
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            user_company = get_user_company(user)
        else:
            user_company = None

        if user_company:
            self.fields['trip'].queryset = Trip.objects.filter(
                company=user_company)
            self.fields['category'].queryset = CategoryGeneral.objects.filter(
                Q(is_system=True) |
                Q(company_id=user_company.id)
            )
            self.fields['payment_term'].queryset = PaymentTerm.objects.filter(
                company=user_company)

    assigned_user = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all())
    bill_to = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    person = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    payment_term = SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=PaymentTerm.objects.none(), write_only=True)

    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Currency.objects.all())
    status = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=StatusType.objects.all())
    mode = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=ModeType.objects.all())
    bt = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=BodyType.objects.all())
    incoterm = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Incoterm.objects.all())

    category = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=CategoryGeneral.objects.none())
    carrier = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    person_carrier = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    driver = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    vehicle_tractor = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.all(), write_only=True)
    vehicle_trailer = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.all(), write_only=True)
    trip = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.none(), write_only=True)

    load_tors = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Tor.objects.all(), write_only=True)
    load_ctrs = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Ctr.objects.all(), write_only=True)
    load_invs = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Inv.objects.all(), write_only=True)
    load_exps = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Exp.objects.all(), write_only=True)

    cmr = CMRSerializer(allow_null=True)

    cmr_consumed = serializers.SerializerMethodField(read_only=True)

    entry_loads = EntrySerializer(many=True)
    load_iteminvs = ItemInvSerializer(many=True)
    load_comments = CommentSerializer(many=True)
    load_histories = HistorySerializer(many=True, read_only=True)
    load_imageuploads = ImageUploadOutSerializer(many=True, read_only=True)
    load_events = LoadEventOutSerializer(many=True, read_only=True)

    def to_internal_value(self, data):
        # print('6080', data)

        for idx, item in enumerate(data['entry_loads']):
            data['entry_loads'][idx]['order'] = idx

        try:
            data['bill_to'] = data['bill_to'].get('uf', None)
        except:
            pass
        try:
            data['person'] = data['person'].get('uf', None)
        except:
            pass
        try:
            data['status'] = data['status'].get('uf', None)
        except:
            pass

        try:
            data['payment_term'] = data['payment_term'].get('uf', None)
        except:
            pass
        try:
            tor_uf_list = []
            for tor in data['load_tors']:
                tor_uf = tor.get('uf', None)
                if tor_uf:
                    tor_uf_list.append(tor_uf)
            data['load_tors'] = tor_uf_list
        except:
            pass
        try:
            tor_uf_list = []
            for tor in data['load_ctrs']:
                tor_uf = tor.get('uf', None)
                if tor_uf:
                    tor_uf_list.append(tor_uf)
            data['load_ctrs'] = tor_uf_list
        except:
            pass
        try:
            inv_uf_list = []
            for inv in data['load_invs']:
                inv_uf = inv.get('uf', None)
                if inv_uf:
                    inv_uf_list.append(inv_uf)

            data['load_invs'] = inv_uf_list
        except:
            pass
        try:
            item_uf_list = []
            for item in data['load_exps']:
                item_uf = item.get('uf', None)
                if item_uf:
                    item_uf_list.append(item_uf)

            data['load_exps'] = item_uf_list
        except:
            pass
        try:
            data['carrier'] = data['carrier'].get('uf', None)
        except:
            pass
        try:
            data['person'] = data['person'].get('uf', None)
        except:
            pass
        try:
            data['person_carrier'] = data['person_carrier'].get('uf', None)
        except:
            pass
        try:
            data['driver'] = data['driver'].get('uf', None)
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

        if 'sn' in data and data['sn'] == '':
            data['sn'] = None
        if 'freight_price_received' in data and data['freight_price_received'] == '':
            data['freight_price_received'] = None
        if 'freight_cost' in data and data['freight_cost'] == '':
            data['freight_cost'] = None
        if 'freight_cost_paid' in data and data['freight_cost_paid'] == '':
            data['freight_cost_paid'] = None
        if 'mode' in data and data['mode'] == '':
            data['mode'] = None
        if 'incoterm' in data and data['incoterm'] == '':
            data['incoterm'] = None
        if 'bt' in data and data['bt'] == '':
            data['bt'] = None
        if 'status' in data and data['status'] == '':
            data['status'] = None
        if 'currency' in data and data['currency'] == '':
            data['currency'] = None
        if 'cmr' in data and (data['cmr'] == '' or data['cmr'] == None):
            data['cmr'] = None
        if 'assigned_user' in data and data['assigned_user'] == '':
            data['assigned_user'] = None
        if 'is_locked' in data and (data['is_locked'] == '' or data['is_locked'] == None):
            data['is_locked'] = False

        if 'customer' in data and data['customer'] == '':
            data['customer'] = None
        if 'invs' in data and data['invs'] == '':
            data['invs'] = None
        if 'payment_term' in data and data['payment_term'] == '':
            data['payment_term'] = None
        if 'load_ctrs' in data and data['load_ctrs'] == '':
            data['load_ctrs'] = None

        return super(LoadSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        from dff.serializers.serializers_trip import TripTruckSerializer

        response = super().to_representation(instance)

        # print('8787', instance)
        # response['assigned_user'] = UserSerializer(
        #     instance.assigned_user).data if instance.assigned_user else None
        response['bill_to'] = ContactSerializer(
            instance.bill_to).data if instance.bill_to else None
        response['person'] = PersonSerializer(
            instance.person).data if instance.person else None
        response['payment_term'] = PaymentTermSerializer(
            instance.payment_term).data if instance.payment_term else None
        response['trip'] = instance.trip.uf if instance.trip else None
        response['trip_num'] = instance.trip.rn if instance.trip else None

        response['carrier'] = ContactSerializer(
            instance.carrier).data if instance.carrier else None
        response['person_carrier'] = PersonSerializer(
            instance.person_carrier).data if instance.person_carrier else None
        response['driver'] = PersonSerializer(
            instance.driver).data if instance.driver else None
        response['vehicle_tractor'] = VehicleSerializer(
            instance.vehicle_tractor).data if instance.vehicle_tractor else None
        response['vehicle_trailer'] = VehicleSerializer(
            instance.vehicle_trailer).data if instance.vehicle_trailer else None

        response['load_tors'] = TorSerializer(
            instance.load_tors, many=True).data if instance.load_tors else None
        response['load_ctrs'] = CtrSerializer(
            instance.load_ctrs, many=True).data if instance.load_ctrs else None
        response['load_invs'] = InvSerializer(
            instance.load_invs, many=True).data if instance.load_invs else None
        response['load_exps'] = ExpSerializer(
            instance.load_exps, many=True).data if instance.load_exps else None
        response['trip'] = TripTruckSerializer(
            instance.trip).data if instance.trip else None

        return response

    def create(self, validated_data):
        # print('1614:', validated_data)

        # Extract nested CMR data before relations pop it
        cmr_data = validated_data.pop('cmr', None)

        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin, self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

            # ✅ Handle CMR update/create automatically
            if cmr_data:

                CMR.objects.update_or_create(
                    load=instance,
                    defaults={**cmr_data, "company": instance.company},
                )

        return instance

    def update(self, instance, validated_data):
        # print('3347', validated_data)

        # # Extract nested CMR data before relations pop it
        # cmr_data = validated_data.pop('cmr', None)

        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(validated_data, relations)

        # Update instance with atomic
        with transaction.atomic():
            instance = super(NestedUpdateMixin, self).update(
                instance,
                validated_data,
            )
            self.update_or_create_reverse_relations(
                instance, reverse_relations)
            self.delete_reverse_relations_if_need(instance, reverse_relations)

            # # ✅ Handle CMR update/create automatically
            # if cmr_data:

            #     CMR.objects.update_or_create(
            #         load=instance,
            #         defaults={**cmr_data, "company": instance.company},
            #     )

            instance.refresh_from_db()
            return instance

    class Meta:
        model = Load
        fields = ('assigned_user', 'sn', 'date_order', 'customer_ref', 'customer_notes', 'is_locked', 'uf',
                  'load_detail', 'load_size', 'freight_price', 'load_type', 'load_add_ons', 'ins_details', 'dgg_details', 'tmc_details',
                  'date_due', 'doc_lang', 'load_address', 'unload_address',
                  'is_active', 'is_loaded', 'is_cleared', 'is_unloaded', 'is_invoiced', 'is_signed', 'is_paid',
                  'date_loaded', 'date_cleared', 'date_unloaded', 'date_invoiced', 'date_signed',
                  'hb', 'mb', 'booking_number', 'comment1',
                  'category', 'bill_to', 'person', 'currency', 'mode', 'bt', 'status', 'incoterm', 'cmr',
                  'load_comments', 'payment_term', 'entry_loads', 'load_iteminvs', 'load_tors', 'load_ctrs', 'load_imageuploads', 'load_invs',
                  'load_histories', 'load_exps',
                  'trip', 'carrier', 'person_carrier', 'driver', 'vehicle_tractor', 'vehicle_trailer',
                  'load_events',

                  'cmr_consumed',

                  )
        read_only_fields = ['load_events', 'is_invoiced', 'date_invoiced']

    def get_cmr_consumed(self, instance):
        movement = (
            instance.cmr_movements
            .filter(movement_type=CMRStockMovement.CONSUMED)
            .order_by("-created_at")
            .first()
        )

        if not movement:
            return None

        return {
            "batch_uf": movement.batch.uf,
            "series": movement.series,
            "number": movement.number_from,
            "consumed_at": movement.created_at,
            "consumed_by": (
                f"{movement.created_by.first_name} {movement.created_by.last_name}".strip()
                if movement.created_by and (movement.created_by.first_name or movement.created_by.last_name)
                else movement.created_by.email if movement.created_by else None
            ),
        }


class LoadPatchSerializer(WritableNestedModelSerializer):
    AUTO_DATE_FIELDS = {
        'is_loaded': 'date_loaded',
        'is_cleared': 'date_cleared',
        'is_unloaded': 'date_unloaded',
        'is_signed': 'date_signed',
    }

    load_events = LoadEventOutSerializer(
        many=True,
        read_only=True
    )
    shipper_confirmed = serializers.BooleanField(
        write_only=True, required=False)
    shipper_email_sent = serializers.BooleanField(
        write_only=True, required=False)
    docs_sent_cnee_broker = serializers.BooleanField(
        write_only=True, required=False)

    def validate(self, attrs):
        instance = self.instance

        # Merge instance + incoming PATCH data
        date_loaded = attrs.get(
            'date_loaded', instance.date_loaded if instance else None)
        date_cleared = attrs.get(
            'date_cleared', instance.date_cleared if instance else None)
        date_unloaded = attrs.get(
            'date_unloaded', instance.date_unloaded if instance else None)

        # 🔒 Business rules
        if date_loaded and date_cleared and date_cleared < date_loaded:
            raise serializers.ValidationError({
                'date_cleared': 'date_cleared cannot be before date_loaded.'
            })

        if date_cleared and date_unloaded and date_unloaded < date_cleared:
            raise serializers.ValidationError({
                'date_unloaded': 'date_unloaded cannot be before date_cleared.'
            })

        return attrs

    def update(self, instance, validated_data):
        now = timezone.now()

        if validated_data.get("date_loaded") is not None:
            validated_data["is_loaded"] = True

        if validated_data.get("date_cleared") is not None:
            validated_data["is_cleared"] = True

        if validated_data.get("date_unloaded") is not None:
            validated_data["is_unloaded"] = True

        # 🔹 extract event flags
        event_type = None
        for flag, mapped_event in LOAD_EVENT_FLAG_MAP.items():
            if validated_data.pop(flag, False) is True:
                event_type = mapped_event
                break  # ✅ exactly ONE event per request

        # 🔹 auto-date logic (unchanged)
        for flag_field, date_field in self.AUTO_DATE_FIELDS.items():
            if (
                validated_data.get(flag_field) is True
                and date_field not in validated_data
                and getattr(instance, date_field) is None
            ):
                validated_data[date_field] = now
            elif (
                validated_data.get(flag_field) is False
                and date_field not in validated_data
            ):
                validated_data[date_field] = None

        relations, reverse_relations = self._extract_relations(validated_data)

        print('5608', event_type)

        with transaction.atomic():
            instance = super(NestedUpdateMixin, self).update(
                instance,
                validated_data,
            )

            self.update_or_create_reverse_relations(
                instance, reverse_relations)
            self.delete_reverse_relations_if_need(instance, reverse_relations)

            # create OR delete LoadEvent (retry-safe)
            if event_type:
                event = (
                    LoadEvent.objects
                    .select_for_update()
                    .filter(load=instance, event_type=event_type)
                    .first()
                )

                if event:
                    event.delete()
                else:
                    LoadEvent.objects.create(
                        load=instance,
                        event_type=event_type,
                        created_by=self.context["request"].user,
                    )

            instance.refresh_from_db()
            return instance

    class Meta:
        model = Load
        # Only include the fields to allow patching
        fields = ('is_active', 'is_loaded', 'is_cleared', 'is_unloaded', 'is_invoiced', 'is_signed', 'is_paid',
                  'date_loaded', 'date_cleared', 'date_unloaded', 'date_invoiced', 'date_signed',
                  # write-only flags
                  'shipper_confirmed',
                  'shipper_email_sent',
                  'docs_sent_cnee_broker',
                  # read-only output
                  'load_events',
                  )

        # Should never be updated
        read_only_fields = ["id", "company",
                            "assigned_user", "load_events", "uf"]


class LoadBasicSerializer(WritableNestedModelSerializer):
    currency = CurrencySerializer(allow_null=True)
    load_iteminvs = ItemInvSerializer(many=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        response['bill_to'] = ContactSerializer(
            instance.bill_to).data if instance.bill_to else None

        return response

    class Meta:
        model = Load
        fields = ('sn', 'bill_to', 'currency', 'load_iteminvs', 'uf')

        depth = 2


###### Load list for Trip ######
class LoadListForTripSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    ''' Get only the loads for a particular 1 trip '''

    bill_to = ContactBasicReadSerializer(allow_null=True)
    mode = ModeTypeSerializer(allow_null=True)
    bt = BodyTypeSerializer(allow_null=True)
    # currency = CurrencySerializer(allow_null=True)

    entry_loads = EntryBasicReadListSerializer(many=True)
    load_iteminvs = ItemInvSerializer(many=True)
    load_comments = CommentSerializer(many=True)
    load_events = LoadEventOutSerializer(many=True)

    class Meta:
        model = Load
        fields = ('sn', 'customer_ref', 'customer_notes', 'load_detail', 'load_size', 'freight_price', 'load_add_ons', 'uf',
                  'is_loaded', 'is_cleared', 'is_unloaded', 'is_invoiced',
                  'date_loaded', 'date_cleared', 'date_unloaded', 'date_invoiced',
                  'load_address', 'unload_address', 'hb', 'mb', 'booking_number', 'comment1',
                  'bill_to', 'mode', 'bt',
                  'load_comments', 'entry_loads', 'load_iteminvs', 'load_events',
                  )
        read_only_fields = ['load_events']


class IssueInvoiceSerializer(serializers.Serializer):
    invoice_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=4
    )
    exchange_rate = serializers.DecimalField(
        max_digits=12,
        decimal_places=6
    )
    rate_date = serializers.DateField()
    is_overridden = serializers.BooleanField(default=False)
