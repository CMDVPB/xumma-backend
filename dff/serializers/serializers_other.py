from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.serializers import CountrySerializer, CurrencySerializer
from app.serializers import UserBasicSerializer
from att.models import Contact, BankAccount, PaymentTerm, Person, TargetGroup, Term, VehicleUnit
from axx.models import Load
from ayy.models import CMR, Comment, Document, History, ImageUpload


class DocumentSerializer(WritableNestedModelSerializer):
    def to_internal_value(self, data):
        if 'doc_type' in data and data['doc_type'] == '':
            data['doc_type'] = None
        if 'doc_num' in data and data['doc_num'] == '':
            data['doc_num'] = None
        if 'date_doc' in data and data['date_doc'] == '':
            data['date_doc'] = None
        if 'doc_det' in data and data['doc_det'] == '':
            data['doc_det'] = None

        return super(DocumentSerializer, self).to_internal_value(data)

    class Meta:
        model = Document
        fields = ('doc_num', 'date_doc', 'date_exp',
                  'doc_det', 'doc_type', 'uf')


class BankAccountSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    currency_code = CurrencySerializer(allow_null=True)

    def create(self, validated_data):
        # print('0604', validated_data)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        # print('3190', validated_data, instance)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance with atomic
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
        model = BankAccount
        fields = ('currency_code', 'iban_number', 'bank_name', 'bank_address', 'bank_code', 'add_instructions', 'include_in_inv', 'uf',
                  'contact',
                  )


class VehicleUnitBasicReadSerializer(WritableNestedModelSerializer):

    class Meta:
        model = VehicleUnit
        fields = ('reg_number', 'uf')


class VehicleUnitSerializer(WritableNestedModelSerializer):

    vehicle_gendocs = DocumentSerializer(many=True)

    def to_internal_value(self, data):
        if 'uf' in data and data['uf'] == '':
            data['uf'] = None
        if 'payload' in data and data['payload'] == '':
            data['payload'] = None
        if 'volume' in data and data['volume'] == '':
            data['volume'] = None

        return super(VehicleUnitSerializer, self).to_internal_value(data)

    def create(self, validated_data):
        # print('1614:', validated_data)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        # print('3347', validated_data, instance)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance with atomic
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
        model = VehicleUnit
        fields = ('id', 'reg_number', 'vehicle_type', 'payload',
                  'volume', 'comment', 'contact', 'vehicle_gendocs', 'uf')


class PersonBasicReadSerializer(WritableNestedModelSerializer):
    class Meta:
        model = Person
        fields = ('last_name', 'first_name', 'is_driver', 'uf')


class PersonSerializer(WritableNestedModelSerializer):

    def save(self, **kwargs):
        ### Initialize _save_kwargs to store additional data ###
        self._save_kwargs = defaultdict(dict, kwargs)

        # List of possible parent keys that may be passed in kwargs
        possible_parents = ['contact']

        # print('4450', kwargs)

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

    def to_internal_value(self, data):
        if 'uf' in data and data['uf'] == '':
            data['uf'] = None

        return super(PersonSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['company_name'] = instance.contact.company_name if instance.contact else None

        return response

    def create(self, validated_data):
        # print('1614:', validated_data)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        # print('3347', validated_data, instance)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance with atomic
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
        model = Person
        fields = ('last_name', 'first_name', 'email',
                  'phone', 'comment', 'is_driver', "archived", 'uf')


class ContactTripListSerializer(WritableNestedModelSerializer):
    contact_vehicle_units = VehicleUnitBasicReadSerializer(many=True)

    class Meta:
        model = Contact
        fields = ('company_name', 'uf',
                  'contact_vehicle_units'
                  )


class ContactBasicReadSerializer(WritableNestedModelSerializer):

    country_code_post = CountrySerializer(allow_null=True)

    class Meta:
        model = Contact
        fields = ('fiscal_code', 'company_name', 'zip_code_post', 'city_post', 'address_post', 'lat', 'lon', 'uf',
                  'country_code_post',
                  )


class ContactSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    contact_persons = PersonSerializer(many=True)

    country_code_legal = CountrySerializer(allow_null=True)
    country_code_post = CountrySerializer(allow_null=True)

    contact_vehicle_units = VehicleUnitSerializer(many=True)
    contact_bank_accounts = BankAccountSerializer(many=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['contact_type'] = instance.contact_type if instance.contact_type else None

        return response

    def create(self, validated_data):
        # print('6543', self.fields)
        relations, reverse_relations = self._extract_relations(validated_data)

        # print('3591', self.serializer_related_field,
        #       self.serializer_related_to_field)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        # print('6827', validated_data, "\n", instance)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance with atomic
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
        model = Contact
        fields = ('company_name', 'alias_company_name', 'is_same_address', 'contact_type', 'uf',
                  'fiscal_code', 'vat_code', 'reg_com', 'subscribed_capital',
                  'is_vat_payer', 'is_vat_on_receipt', 'email', 'phone', 'messanger',
                  'country_code_legal', 'zip_code_legal', 'city_legal', 'address_legal', 'county_legal', 'sect_legal',
                  'country_code_post', 'zip_code_post', 'city_post', 'address_post', 'comment1', 'comment2',
                  'lat', 'lon',
                  'contact_persons', 'contact_vehicle_units', 'contact_bank_accounts')


class TargetGroupSerializer(WritableNestedModelSerializer):

    target_group_persons = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Person.objects.all(), write_only=True)

    def to_internal_value(self, data):
        # print('8271', data.get('trip_loads', None))

        if 'group_name' in data and data['group_name'] == '':
            data['group_name'] = None
        if 'description' in data and data['description'] == '':
            data['description'] = None

        return super(TargetGroupSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        response['target_group_persons'] = PersonSerializer(
            instance.target_group_persons, many=True).data if instance.target_group_persons else None

        return response

    def create(self, validated_data):
        # print('5970:', validated_data)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        # print('8947', validated_data, instance)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance with atomic
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
        model = TargetGroup
        fields = ('group_name', 'description', 'target_group_persons', 'uf')


class PaymentTermSerializer(WritableNestedModelSerializer):

    def create(self, validated_data):
        # print('1614:', validated_data)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    def update(self, instance, validated_data):
        # print('3347', validated_data, instance)
        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        # Update instance with atomic
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
        model = PaymentTerm
        fields = ('note_short', 'note_description', 'uf')


class TermSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = Term
        fields = ('term_short', 'term_description', 'uf')


class CommentSerializer(WritableNestedModelSerializer):
    class Meta:
        model = Comment
        fields = ('comment', 'uf')


class ImageSerializer(WritableNestedModelSerializer):

    load = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Load.objects.all(), write_only=True)

    def to_internal_value(self, data):
        # print('4574',)

        if 'load' in data and data['load'] == '':
            data['load'] = None

        return super(ImageSerializer, self).to_internal_value(data)

    class Meta:
        model = ImageUpload
        fields = ('load', 'unique_field', 'company',
                  'file_name', 'file_obj', 's3_url')


class CMRSerializer(serializers.ModelSerializer):

    def save(self, **kwargs):
        self._save_kwargs = defaultdict(dict, kwargs)

        # Extract parent load from kwargs
        parent_load = kwargs.get("load")
        if not parent_load:
            raise serializers.ValidationError(
                "E681 A valid parent instance is required.")

        # Attach load to validated data
        self.validated_data["load"] = parent_load

        # 1. If uf exists, update by uf
        uf_value = self.validated_data.get('uf')
        if uf_value:
            instance = CMR.objects.filter(uf=uf_value).first()
            if instance:
                return self.update(instance, self.validated_data)

        # 2. Otherwise check if this load already has a CMR (OneToOne rule)
        existing = CMR.objects.filter(load=parent_load).first()
        if existing:
            return self.update(existing, self.validated_data)

        # 3. New CMR: copy company from Load
        if parent_load.company:
            self.validated_data["company"] = parent_load.company

        # Create new CMR
        return self.create(self.validated_data)

    class Meta:
        model = CMR
        fields = [
            "number",
            "list_of_documents",
            "special_agreement",
            "payment",
            "cod",
            "cod_amount",
            "place_load",
            "place_unload",
            "place_issue",
            "date_issue",
            "uf",
        ]
        read_only_fields = ["uf"]  # generated fields


class HistorySerializer(WritableNestedModelSerializer):
    changed_by = UserBasicSerializer(allow_null=True)

    class Meta:
        model = History
        fields = ('date_registered', 'action', 'status', 'changed_by', 'uf')
