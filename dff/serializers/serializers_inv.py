from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.custom_serializers import SlugRelatedGetOrCreateField
from abb.serializers import CurrencySerializer
from app.serializers import UserSerializer
from att.models import Contact, PaymentTerm, Person, Term
from att.serializers import BodyTypeSerializer, IncotermSerializer, ModeTypeSerializer, StatusTypeSerializer
from axx.models import Inv, Load, Series
from dff.serializers.serializers_entry_detail import EntrySerializer
from dff.serializers.serializers_item_inv import ItemInvSerializer
from dff.serializers.serializers_other import CommentSerializer, ContactBasicReadSerializer, ContactSerializer, HistorySerializer, PaymentTermSerializer, PersonSerializer, TermSerializer

import logging
logger = logging.getLogger(__name__)

User = get_user_model()


class InvListSerializer(WritableNestedModelSerializer):
    ''' GET List only Invoice serializer '''

    series = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Series.objects.all())
    bill_to = ContactBasicReadSerializer(allow_null=True)
    status = StatusTypeSerializer(allow_null=True)
    currency = CurrencySerializer(allow_null=True)
    iteminv_invs = ItemInvSerializer(many=True)
    inv_comments = CommentSerializer(many=True)

    class Meta:
        model = Inv
        fields = ('series', 'qn', 'vn', 'date_inv', 'date_due', 'load_detail', 'load_address', 'unload_address', 'is_quote', 'uf',
                  'spv_sent_status', 'spv_ind_upload', 'spv_ind_upload_status', 'spv_error_code',
                  'status', 'bill_to', 'currency',
                  'iteminv_invs', 'inv_comments',
                  )
        read_only_fields = ['spv_ind_upload',
                            'spv_ind_upload_status', 'spv_error_code']


class InvSerializer(WritableNestedModelSerializer):
    ''' main Invoice serializer '''

    assigned_user = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    series = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Series.objects.all())
    bill_to = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    person = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    payment_term = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=PaymentTerm.objects.all(), write_only=True)
    contract_terms = SlugRelatedGetOrCreateField(
        allow_null=True, slug_field='uf', queryset=Term.objects.all(), write_only=True)
    load = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Load.objects.all(), write_only=True)

    mode = ModeTypeSerializer(allow_null=True,)
    bt = BodyTypeSerializer(allow_null=True)
    incoterm = IncotermSerializer(allow_null=True)
    currency = CurrencySerializer(allow_null=True)
    status = StatusTypeSerializer(allow_null=True)

    inv_histories = HistorySerializer(many=True, read_only=True)
    iteminv_invs = ItemInvSerializer(many=True)
    inv_comments = CommentSerializer(many=True)
    entry_invs = EntrySerializer(many=True)

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)

        if instance:
            sent = bool(instance.spv_ind_upload)
            error = bool(instance.spv_error_code)
            accepted = bool(instance.spv_ind_id_download)

            if sent and (accepted or not error):
                allowed = ['status']
                disallowed = [field for field in attrs if field not in allowed]

                if disallowed:
                    raise serializers.ValidationError(
                        f"Only status change is allowed after sending to ANAF SPV."
                    )
        return attrs

    def to_internal_value(self, data):
        data_copy = data.copy()

        if 'status' in data_copy and data_copy['status'] == '':
            data_copy['status'] = None

        # If instance is SPV locked than allow only status change and skip the rest of the code
        instance = getattr(self, 'instance', None)
        if instance:
            sent = bool(instance.spv_ind_upload)
            error = bool(instance.spv_error_code)
            accepted = bool(instance.spv_ind_id_download)
            is_locked = sent and (accepted or not error)

            # print('SR2244', is_locked, sent, error, accepted)

            if is_locked:
                # Only keep status field and skip all other normalization
                return super(InvSerializer, self).to_internal_value({'status': data_copy.get('status', None)})

        for idx, item in enumerate(data_copy['entry_invs']):
            data_copy['entry_invs'][idx]['order'] = idx

        try:
            data_copy['bill_to'] = data_copy['bill_to'].get('uf', None)
        except:
            pass
        try:
            data_copy['person'] = data_copy['person'].get('uf', None)
        except:
            pass
        try:
            data_copy['payment_term'] = data_copy['payment_term'].get(
                'uf', None)
        except:
            pass
        try:
            data_copy['contract_terms'] = data_copy['contract_terms'].get(
                'uf', None)
        except:
            pass

        if 'uf' in data_copy and data_copy['uf'] == '':
            data_copy['uf'] = None
        if 'qn' in data_copy and data_copy['qn'] == '':
            data_copy['qn'] = None
        if 'vn' in data_copy and data_copy['vn'] == '':
            data_copy['vn'] = None
        if 'an' in data_copy and data_copy['an'] == '':
            data_copy['an'] = None
        if 'bt' in data_copy and data_copy['bt'] == '':
            data_copy['bt'] = None
        if 'date_due' in data_copy and data_copy['date_due'] == '':
            data_copy['date_due'] = None
        if 'date_act' in data_copy and data_copy['date_act'] == '':
            data_copy['date_act'] = None
        if 'date_load' in data_copy and data_copy['date_load'] == '':
            data_copy['date_load'] = None
        if 'date_unload' in data_copy and data_copy['date_unload'] == '':
            data_copy['date_unload'] = None
        if 'customer_ref' in data_copy and data_copy['customer_ref'] == '':
            data_copy['customer_ref'] = None
        if 'customer_notes' in data_copy and data_copy['customer_notes'] == '':
            data_copy['customer_notes'] = None
        if 'note_act' in data_copy and data_copy['note_act'] == '':
            data_copy['note_act'] = None
        if 'payment_term' in data_copy and data_copy['payment_term'] == '':
            data_copy['payment_term'] = None
        if 'contract_terms' in data_copy and data_copy['contract_terms'] == '':
            data_copy['contract_terms'] = None
        if 'load' in data_copy and data_copy['load'] == '':
            data_copy['load'] = None
        if 'entry_invs' in data_copy and data_copy['entry_invs'] == '':
            data_copy['entry_invs'] = None
        if 'mode' in data_copy and data_copy['mode'] == '':
            data_copy['mode'] = None
        if 'incoterm' in data_copy and data_copy['incoterm'] == '':
            data_copy['incoterm'] = None
        if 'is_locked' in data_copy and (data_copy['is_locked'] == '' or data_copy['is_locked'] == None):
            data_copy['is_locked'] = False
        if 'inv_histories' in data_copy and data_copy['inv_histories'] == '':
            data_copy['inv_histories'] = None
        if 'is_quote' in data_copy and data_copy['is_quote'] == '':
            data_copy['is_quote'] = None

        return super(InvSerializer, self).to_internal_value(data_copy)

    def to_representation(self, instance):
        from dff.serializers.serializers_load import LoadBasicReadSerializer

        response = super().to_representation(instance)

        response['assigned_user'] = UserSerializer(
            instance.assigned_user).data if instance.assigned_user else None
        response['load'] = LoadBasicReadSerializer(
            instance.load).data if instance.load else None
        response['bill_to'] = ContactSerializer(
            instance.bill_to).data if instance.bill_to else None
        response['person'] = PersonSerializer(
            instance.person).data if instance.person else None
        response['payment_term'] = PaymentTermSerializer(
            instance.payment_term).data if instance.payment_term else None
        response['contract_terms'] = TermSerializer(
            instance.contract_terms).data if instance.contract_terms else None

        return response

    def create(self, validated_data):

        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance as atomic
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

        # Update instance as atomic
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
        model = Inv
        fields = ('assigned_user', 'qn', 'vn', 'date_inv', 'date_due', 'an', 'date_act', 'bill_to',
                  'payment_term', 'currency', 'is_locked', 'iteminv_invs', 'load_size', 'load_add_ons', 'doc_lang', 'is_quote', 'uf',
                  'series', 'load',
                  'inv_comments', 'entry_invs', 'contract_terms', 'load_detail', 'load_address', 'unload_address',
                  'date_load', 'customer_ref', 'note_act', 'customer_notes', 'date_unload', 'person', 'mode', 'bt', 'incoterm',
                  'status', 'inv_histories')
        read_only_fields = ['inv_histories',
                            'spv_sent_status', 'spv_ind_upload', 'spv_ind_upload_date',
                            'spv_ind_upload_status', 'spv_error_code', 'spv_error_message', 'spv_error_message_array']
