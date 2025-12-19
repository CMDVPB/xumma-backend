from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.models import StatusType
from abb.serializers import CurrencySerializer
from app.serializers import UserSerializer
from att.models import Contact, Person
from att.serializers import StatusTypeSerializer
from axx.models import Exp, Load, Tor
from dff.serializers.serializers_item_inv import ItemInvSerializer
from dff.serializers.serializers_other import ContactSerializer, HistorySerializer, PersonSerializer
from dff.serializers.serializers_tor import TorBasicSerializer


User = get_user_model()


class ExpSerializer(WritableNestedModelSerializer):

    assigned_user = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    supplier = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)
    person = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)

    status = serializers.PrimaryKeyRelatedField(
        allow_null=True, queryset=StatusType.objects.all(), write_only=True)

    load = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Load.objects.all(), write_only=True)
    tor = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Tor.objects.all(), write_only=True)

    currency = CurrencySerializer(allow_null=True)
    exp_iteminvs = ItemInvSerializer(many=True)
    exp_histories = HistorySerializer(many=True, read_only=True)

    def to_internal_value(self, data):
        try:
            data['supplier'] = data['supplier'].get('uf', None)
        except:
            pass
        try:
            data['person'] = data['person'].get('uf', None)
        except:
            pass

        if 'xn' in data and data['xn'] == '':
            data['xn'] = None
        if 'is_locked' in data and data['is_locked'] == '':
            data['is_locked'] = None
        if 'person' in data and data['person'] == '':
            data['person'] = None
        if 'status' in data and data['status'] == '':
            data['status'] = None
        if 'is_locked' in data and (data['is_locked'] == '' or data['is_locked'] == None):
            data['is_locked'] = False

        if 'load' in data and data['load'] == '':
            data['load'] = None
        if 'tor' in data and data['tor'] == '':
            data['tor'] = None

        return super(ExpSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        from dff.serializers.serializers_load import LoadBasicSerializer

        response = super().to_representation(instance)

        response['assigned_user'] = UserSerializer(
            instance.assigned_user).data if instance.assigned_user else None
        response['load'] = LoadBasicSerializer(
            instance.load).data if instance.load else None
        response['tor'] = TorBasicSerializer(
            instance.tor).data if instance.tor else None

        response['supplier'] = ContactSerializer(
            instance.supplier).data if instance.supplier else None
        response['person'] = PersonSerializer(
            instance.person).data if instance.person else None
        response['status'] = StatusTypeSerializer(
            instance.status).data if instance.status else None

        # print('6545', instance.tor)

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
        model = Exp
        fields = ('assigned_user', 'supplier', 'person', 'xn', 'date_record', 'doc_number', 'load', 'tor', 'doc_lang', 'uf',
                  'date_issue', 'date_due', 'currency', 'status', 'is_locked', 'exp_iteminvs', 'exp_histories', 'comment',
                  )
