from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.custom_serializers import SlugRelatedGetOrCreateField
from abb.serializers import CurrencySerializer
from app.serializers import UserSerializer
from att.models import Contact, PaymentTerm, Person, Term, VehicleUnit
from att.serializers import BodyTypeSerializer, IncotermSerializer, ModeTypeSerializer, StatusTypeSerializer
from axx.models import Exp, Load, Tor
from dff.serializers.serializers_entry_detail import EntrySerializer
from dff.serializers.serializers_item_inv import ItemInvSerializer
from dff.serializers.serializers_other import CommentSerializer, ContactSerializer, HistorySerializer, PaymentTermSerializer, PersonSerializer, TermSerializer, VehicleUnitSerializer

User = get_user_model()


class TorBasicSerializer(WritableNestedModelSerializer):
    currency = CurrencySerializer(allow_null=True)
    tor_iteminvs = ItemInvSerializer(many=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        response['carrier'] = ContactSerializer(
            instance.carrier).data if instance.carrier else None

        return response

    class Meta:
        model = Tor
        fields = ('tn', 'carrier', 'currency', 'tor_iteminvs', 'uf')


class TorSerializer(WritableNestedModelSerializer):

    assigned_user = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    carrier = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    person = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    driver = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    vehicle_tractor = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=VehicleUnit.objects.all(), write_only=True)
    vehicle_trailer = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=VehicleUnit.objects.all(), write_only=True)
    payment_term = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=PaymentTerm.objects.all(), write_only=True)
    contract_terms = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Term.objects.all(), write_only=True)
    load = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Load.objects.all(), write_only=True)
    tor_exps = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Exp.objects.all(), write_only=True)

    mode = ModeTypeSerializer(allow_null=True)
    incoterm = IncotermSerializer(allow_null=True)
    status = StatusTypeSerializer(allow_null=True)
    bt = BodyTypeSerializer(allow_null=True)
    currency = CurrencySerializer(allow_null=True)

    tor_histories = HistorySerializer(many=True, read_only=True)
    entry_tors = EntrySerializer(many=True)
    tor_iteminvs = ItemInvSerializer(many=True)
    tor_comments = CommentSerializer(many=True)

    def to_internal_value(self, data):
        for idx, item in enumerate(data['entry_tors']):
            data['entry_tors'][idx]['order'] = idx

        try:
            data['load'] = data['load'].get('uf', None)
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
        try:
            data['payment_term'] = data['payment_term'].get('uf', None)
        except:
            pass
        try:
            data['contract_terms'] = data['contract_terms'].get('uf', None)
        except:
            pass

        try:
            item_uf_list = []
            for item in data['tor_exps']:
                item_uf = item.get('uf', None)
                if item_uf:
                    item_uf_list.append(item_uf)

            data['tor_exps'] = item_uf_list

        except:
            pass

        if 'tn' in data and data['tn'] == '':
            data['tn'] = None
        if 'doc_number' in data and data['doc_number'] == '':
            data['doc_number'] = None
        if 'date_order' in data and data['date_order'] == '':
            data['date_order'] = None
        if 'load' in data and data['load'] == '':
            data['load'] = None
        if 'date_unload' in data and data['date_unload'] == '':
            data['date_unload'] = None
        if 'payment_term' in data and data['payment_term'] == '':
            data['payment_term'] = None
        if 'contract_terms' in data and data['contract_terms'] == '':
            data['contract_terms'] = None
        if 'vehicle_tractor' in data and data['vehicle_tractor'] == '':
            data['vehicle_tractor'] = None
        if 'vehicle_trailer' in data and data['vehicle_trailer'] == '':
            data['vehicle_trailer'] = None
        if 'mode' in data and data['mode'] == '':
            data['mode'] = None
        if 'bt' in data and data['bt'] == '':
            data['bt'] = None
        if 'is_locked' in data and (data['is_locked'] == '' or data['is_locked'] == None):
            data['is_locked'] = False

        if 'incoterm' in data and data['incoterm'] == '':
            data['incoterm'] = None
        if 'status' in data and data['status'] == '':
            data['status'] = None
        if 'tor_iteminvs' in data and data['tor_iteminvs'] == '':
            data['tor_iteminvs'] = None
        if 'tor_histories' in data and data['tor_histories'] == '':
            data['tor_histories'] = None
        if 'carrier' in data and data['carrier'] == '':
            data['carrier'] = None
        if 'person' in data and data['person'] == '':
            data['person'] = None
        if 'tor_comments' in data and data['tor_comments'] == '':
            data['tor_comments'] = None

        return super(TorSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        from dff.serializers.serializers_load import LoadBasicReadSerializer
        from dff.serializers.serializers_exp import ExpSerializer

        response = super().to_representation(instance)

        response['assigned_user'] = UserSerializer(
            instance.assigned_user).data if instance.assigned_user else None
        response['load'] = instance.load.uf if instance.load and instance.load.uf else None
        response['load_sn'] = instance.load.sn if instance.load else None
        response['load'] = LoadBasicReadSerializer(
            instance.load).data if instance.load else None
        response['tor_exps'] = ExpSerializer(
            instance.tor_exps, many=True).data if instance.tor_exps else None

        response['carrier'] = ContactSerializer(
            instance.carrier).data if instance.carrier else None
        response['person'] = PersonSerializer(
            instance.person).data if instance.person else None
        response['driver'] = PersonSerializer(
            instance.driver).data if instance.driver else None
        response['vehicle_tractor'] = VehicleUnitSerializer(
            instance.vehicle_tractor).data if instance.vehicle_tractor else None
        response['vehicle_trailer'] = VehicleUnitSerializer(
            instance.vehicle_trailer).data if instance.vehicle_trailer else None
        response['payment_term'] = PaymentTermSerializer(
            instance.payment_term).data if instance.payment_term else None
        response['contract_terms'] = TermSerializer(
            instance.contract_terms).data if instance.contract_terms else None

        # print('6996', instance.tor_exps)
        return response

    def create(self, validated_data):
        # print('9483', validated_data)
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
        # print('1190', validated_data)
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
        model = Tor
        fields = ('assigned_user', 'tn', 'doc_number', 'date_order', 'person', 'driver', 'vehicle_tractor', 'doc_lang', 'uf',
                  'vehicle_trailer', 'load', 'mode', 'incoterm', 'status', 'tor_details', 'load_size', 'load_add_ons',
                  'is_locked', 'bt', 'rate', 'is_tor', 'carrier', 'currency', 'tor_histories', 'tor_exps', 'entry_tors',
                  'payment_term', 'tor_iteminvs', 'contract_terms', 'tor_comments',
                  )
