from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.serializers import CurrencySerializer
from app.serializers import UserSerializer
from att.models import Contact, PaymentTerm, Person, Term
from att.serializers import BodyTypeSerializer, IncotermSerializer, ModeTypeSerializer, StatusTypeSerializer
from axx.models import Ctr, Load
from dff.serializers.serializers_entry_detail import EntrySerializer
from dff.serializers.serializers_item_inv import ItemInvSerializer
from dff.serializers.serializers_other import CommentSerializer, ContactSerializer, HistorySerializer, PaymentTermSerializer, PersonSerializer, TermSerializer


User = get_user_model()


class CtrSerializer(WritableNestedModelSerializer):
    ''' main CTR serializer '''

    assigned_user = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    bill_to = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    person = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)
    payment_term = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=PaymentTerm.objects.all(), write_only=True)
    contract_terms = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Term.objects.all(), write_only=True)
    load = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Load.objects.all(), write_only=True)

    mode = ModeTypeSerializer(allow_null=True)
    status = StatusTypeSerializer(allow_null=True)
    bt = BodyTypeSerializer(allow_null=True)
    incoterm = IncotermSerializer(allow_null=True)
    currency = CurrencySerializer(allow_null=True)

    entry_ctrs = EntrySerializer(many=True)
    ctr_comments = CommentSerializer(many=True)
    ctr_iteminvs = ItemInvSerializer(many=True)
    ctr_histories = HistorySerializer(many=True, read_only=True)

    def to_internal_value(self, data):
        for idx, item in enumerate(data['entry_ctrs']):
            data['entry_ctrs'][idx]['order'] = idx

        try:
            data['bill_to'] = data['bill_to'].get('uf', None)
        except:
            pass
        try:
            data['person'] = data['person'].get('uf', None)
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

        if 'cn' in data and data['cn'] == '':
            data['cn'] = None
        if 'bt' in data and data['bt'] == '':
            data['bt'] = None
        if 'date_order' in data and data['date_order'] == '':
            data['date_order'] = None
        if 'customer_ref' in data and data['customer_ref'] == '':
            data['customer_ref'] = None
        if 'customer_notes' in data and data['customer_notes'] == '':
            data['customer_notes'] = None
        if 'mode' in data and data['mode'] == '':
            data['mode'] = None
        if 'incoterm' in data and data['incoterm'] == '':
            data['incoterm'] = None
        if 'is_locked' in data and (data['is_locked'] == '' or data['is_locked'] == None):
            data['is_locked'] = False

        if 'note_terms' in data and data['note_terms'] == '':
            data['note_terms'] = None

        return super(CtrSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        from dff.serializers.serializers_load import LoadBasicReadSerializer

        response = super().to_representation(instance)

        response['assigned_user'] = UserSerializer(
            instance.assigned_user).data if instance.assigned_user else None
        response['load'] = instance.load.uf if instance.load else None
        response['load_sn'] = instance.load.sn if instance.load else None
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
        # print('7319', validated_data)
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
        # print('5494', validated_data)
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
        model = Ctr
        fields = ('assigned_user', 'cn', 'date_order', 'person', 'rate', 'customer_ref', 'customer_notes', 'load_size', 'uf',
                  'doc_lang', 'load_add_ons', 'bill_to', 'currency', 'mode', 'status', 'bt', 'incoterm', 'is_locked', 'entry_ctrs', 'load',
                  'payment_term', 'contract_terms', 'ctr_comments', 'ctr_iteminvs', 'assigned_user',
                  'ctr_histories',
                  )
