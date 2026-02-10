

from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from django.forms import SlugField
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin

from abb.models import Country, Currency
from abb.serializers import CurrencySerializer
from abb.serializers_drf_writable import CustomWritableNestedModelSerializer, CustomUniqueFieldsMixin
from abb.utils import get_user_company
from app.models import TypeCost
from ayy.models import CompanyCard, UserDocument, DocumentType, ItemCost, ItemForItemCost, PhoneNumber
from ayy.services.fuel_sync import sync_fueling_from_item_cost


User = get_user_model()


class TypeCostFKSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if not validated_data.get('is_system'):
                user_company = getattr(request.user, 'company', None)
                if user_company:
                    validated_data['company'] = user_company
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if instance.is_system:
            raise serializers.ValidationError(
                "System TypeCost entries cannot be modified."
            )
        return super().update(instance, validated_data)

    class Meta:
        model = TypeCost
        fields = ('serial_number', 'code', 'label', 'is_system', 'uf',
                  'company',
                  )
        read_only_fields = (
            'uf',
            'is_system',
        )


class ItemForItemCostSerializer(CustomWritableNestedModelSerializer):

    def to_internal_value(self, data):
        data_copy = data.copy()

        if data_copy.get('description') == '':
            data_copy['description'] = None

        if data_copy.get('vat') == '':
            data_copy['vat'] = None

        if data_copy.get('code') == '':
            data_copy['code'] = None

        # Handle company safely
        if 'company' in data_copy and data_copy['company']:
            if not isinstance(data_copy['company'], int):
                data_copy['company'] = data_copy['company'].id

        else:
            # ⛔ do NOT assign company for system items
            if not data_copy.get('is_system'):
                request = self.context.get('request')
                if request and request.user.is_authenticated:
                    user_company = get_user_company(request.user)
                    if user_company:
                        data_copy['company'] = user_company.id

        return super().to_internal_value(data_copy)

    class Meta:
        model = ItemForItemCost
        lookup_field = 'uf'
        fields = ('description', 'code', 'vat', 'uf',
                  'is_card', 'is_fuel', 'is_system',
                  'company',
                  )
        read_only_fields = ['is_system']


class ItemCostSerializer(WritableNestedModelSerializer):
    item_for_item_cost = ItemForItemCostSerializer(
        allow_null=True, context={'request': 'request'})

    country = serializers.SlugRelatedField(
        allow_null=True, slug_field='label', queryset=Country.objects.all())

    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())

    created_by = serializers.SlugRelatedField(
        slug_field='uf',
        read_only=True)

    type = serializers.SlugRelatedField(
        slug_field='uf',
        queryset=TypeCost.objects.all(),
        allow_null=True
    )

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
        possible_parents = ['trip']

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
                "E679 A valid parent instance is required.")

        # Get company from parent instance and attach to child
        if hasattr(parent_instance, 'company'):
            self.validated_data['company'] = parent_instance.company

        # print('4850', kwargs)

        uf_value = self.validated_data.get('uf')
        if uf_value:
            instance = self.Meta.model.objects.filter(uf=uf_value).first()

            if instance:
                # 🔒 UPDATE — do NOT touch created_by
                self.validated_data.pop('created_by', None)
                return self.update(instance, self.validated_data)

            else:
                # 🆕 CREATE
                request = self.context.get('request')
                if request and request.user.is_authenticated:
                    self.validated_data['created_by'] = request.user

                return self.create(self.validated_data)

        else:
            # 🆕 CREATE (no uf)
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                self.validated_data['created_by'] = request.user

            return self.create(self.validated_data)

    def create(self, validated_data):
        relations, reverse_relations = self._extract_relations(validated_data)

        self.update_or_create_direct_relations(validated_data, relations)

        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        sync_fueling_from_item_cost(instance)

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

            sync_fueling_from_item_cost(instance)

        return instance

    class Meta:
        model = ItemCost
        fields = ('date', 'type', 'quantity', 'amount', 'vat', 'discount', 'uf',
                  'country', 'currency', 'item_for_item_cost', 'created_by',
                  )


class PhoneNumberSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):

    class Meta:
        model = PhoneNumber
        lookup_field = 'uf'
        fields = ('number', 'notes', 'uf',
                  )


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = [
            'code',
            'name',
            'description',

            'expiry_alert_days',
            'target',

            'is_system',
            'uf',
        ]


class UserDocumentSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):
    # READ (expanded)
    document_type = DocumentTypeSerializer(read_only=True)

    document_type_uf = serializers.SlugRelatedField(
        source='document_type',
        slug_field='uf',
        queryset=DocumentType.objects.all(),
        write_only=True
    )

    class Meta:
        model = UserDocument
        lookup_field = 'uf'
        fields = ('document_number', 'date_issued', 'date_expiry', 'notes', 'uf',
                  'document_type',      # read
                  'document_type_uf',   # write
                  )

    def validate_document_type(self, value):
        if value.target != 'user':
            raise serializers.ValidationError(
                'Invalid document type for user documents'
            )
        return value


###### START DOCUMENT TYPE SERIALIZERS ######


class DocumentTypeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = ['id', 'code', 'name', 'description', 'target', 'uf']
        read_only_fields = ['id', 'uf']

    def validate_target(self, value):
        if value not in dict(DocumentType.TARGET_CHOICES):
            raise serializers.ValidationError('Invalid target')
        return value

    def create(self, validated_data):
        user = self.context['request'].user

        user_company = get_user_company(user)

        return DocumentType.objects.create(
            company=user_company,
            created_by=user,
            is_system=False,
            **validated_data
        )


###### END DOCUMENT TYPE SERIALIZERS ######


###### START CARD SERIALIZERS ######


class CompanyCardSerializer(serializers.ModelSerializer):
    current_employee = serializers.SerializerMethodField()
    current_vehicle = serializers.SerializerMethodField()

    class Meta:
        model = CompanyCard
        fields = [
            "id",
            "uf",
            "card_type",
            "provider",
            "card_number",
            "expires_at",
            "is_active",
            "current_employee",
            "current_vehicle",
        ]
        read_only_fields = ["uf"]

    def get_current_employee(self, obj):
        if not obj.current_employee:
            return None
        return {
            "id": obj.current_employee.id,
            "name": obj.current_employee.get_full_name(),
        }

    def get_current_vehicle(self, obj):
        if not obj.current_vehicle:
            return None
        return {
            "id": obj.current_vehicle.id,
            "name": str(obj.current_vehicle),
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # mask card number
        data["card_number"] = f"**** {instance.card_number[-4:]}"
        return data

###### END CARD SERIALIZERS ######
