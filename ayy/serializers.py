

from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin

from abb.serializers import CurrencySerializer
from abb.serializers_drf_writable import CustomWritableNestedModelSerializer, CustomUniqueFieldsMixin
from abb.utils import get_user_company
from ayy.models import Document, ItemCost, ItemForItemCost, PhoneNumber

User = get_user_model()


class ItemForItemCostSerializer(CustomWritableNestedModelSerializer):

    def to_internal_value(self, data):
        data_copy = data.copy()

        if 'description' in data_copy and data_copy['description'] == '':
            data_copy['description'] = None
        if 'vat' in data_copy and data_copy['vat'] == '':
            data_copy['vat'] = None
        if 'code' in data_copy and data_copy['code'] == '':
            data_copy['code'] = None

        ### Add company if present or not present in the data ###
        if 'company' in data_copy:
            if isinstance(data_copy['company'], int):
                data_copy['company'] = data_copy['company']
            else:
                data_copy['company'] = data_copy['company'].id
        elif 'company' not in data_copy or not data_copy['company']:
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                user = request.user
                user_company = get_user_company(user)
                data_copy['company'] = user_company.id
        return super(ItemForItemCostSerializer, self).to_internal_value(data_copy)

    class Meta:
        model = ItemForItemCost
        lookup_field = 'uf'
        fields = ('description', 'code', 'vat', 'is_fuel', 'company', 'uf')


class ItemCostSerializer(WritableNestedModelSerializer):
    item_for_item_cost = ItemForItemCostSerializer(
        allow_null=True, context={'request': 'request'})
    currency = CurrencySerializer(allow_null=True)

    def to_internal_value(self, data):
        if 'quantity' in data and type(data['quantity']) == str:
            data['quantity'] = float(data['quantity']) if len(
                data['quantity']) > 0 else None
        if 'amount' in data and type(data['amount']) == str:
            data['amount'] = float(data['amount']) if len(
                data['amount']) > 0 else None
        if 'vat' in data and type(data['vat']) == str:
            data['vat'] = int(data['vat']) if len(data['vat']) > 0 else None
        if 'discount' in data and type(data['discount']) == str:
            data['discount'] = float(data['discount']) if len(
                data['discount']) > 0 else None

        if 'currency' in data and data['currency'] == '':
            data['currency'] = None
        if 'item_for_item_inv' in data and data['item_for_item_inv'] == '':
            data['item_for_item_inv'] = None

        return super(ItemCostSerializer, self).to_internal_value(data)

    def save(self, **kwargs):
        ### Initialize _save_kwargs to store additional data ###
        self._save_kwargs = defaultdict(dict, kwargs)

        # List of possible parent keys that may be passed in kwargs
        possible_parents = ['route_sheet']

        # print('4750', kwargs)

        parent_instance = None
        parent_field_name = None

        # Find which parent instance is passed in kwargs
        for parent_key in possible_parents:
            if parent_key in kwargs:
                parent_instance = kwargs.get(parent_key)
                parent_field_name = parent_key
                break  # Exit loop once we find the first match

        if parent_instance and parent_field_name:
            # Attach the found parent instance to the validated data
            self.validated_data[parent_field_name] = parent_instance
        else:
            raise serializers.ValidationError(
                "E681 A valid parent instance is required.")

        # Get company from parent instance and attach to child
        if hasattr(parent_instance, 'company'):
            self.validated_data['company'] = parent_instance.company

        # print('4850', kwargs)

        uf_value = self.validated_data.get('uf')
        if uf_value:  # Fetch instance by 'uf' if exists
            instance = self.Meta.model.objects.filter(uf=uf_value).first()
            if instance:
                return self.update(instance, self.validated_data)
            else:
                return self.create(self.validated_data)
        else:
            return self.create(self.validated_data)

    def create(self, validated_data):
        relations, reverse_relations = self._extract_relations(validated_data)

        self.update_or_create_direct_relations(validated_data, relations)

        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        relations, reverse_relations = self._extract_relations(validated_data)

        self.update_or_create_direct_relations(validated_data, relations)

        with transaction.atomic():
            instance = super(NestedUpdateMixin, self).update(
                instance, validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)
            self.delete_reverse_relations_if_need(instance, reverse_relations)
            instance.refresh_from_db()

        return instance

    class Meta:
        model = ItemCost
        fields = ('quantity', 'amount', 'vat', 'discount', 'uf',
                  'currency', 'item_for_item_cost',
                  )


class PhoneNumberSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):

    class Meta:
        model = PhoneNumber
        lookup_field = 'uf'
        fields = ('number', 'notes', 'uf',
                  )


class DocumentSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):

    class Meta:
        model = Document
        lookup_field = 'uf'
        fields = ('doc_det', 'date_exp', 'uf',
                  )
