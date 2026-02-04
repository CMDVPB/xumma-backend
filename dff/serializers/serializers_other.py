from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers
from rest_framework.serializers import SlugRelatedField
from django.core.exceptions import ValidationError
from rest_framework.validators import UniqueTogetherValidator

from abb.custom_exceptions import CustomApiException
from abb.models import Country
from abb.serializers import CountrySerializer, CurrencySerializer
from abb.serializers_drf_writable import CustomWritableNestedModelSerializer, CustomUniqueFieldsMixin
from abb.utils import get_user_company
from app.serializers import UserBasicSerializer
from att.models import Contact, ContactSite, Contract, ContractReferenceDate, PaymentTerm, Person, TargetGroup, Term, Vehicle, VehicleUnit
from att.serializers import ContactStatusSerializer, VehicleContactSerializer, VehicleSerializer
from axx.models import Load
from ayy.models import CMR, Comment, Document, History, ImageUpload
from dff.serializers.serializers_bce import BankAccountSerializer
from dtt.serializers import ContractReferenceDateSerializer


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


class VehicleBasicReadSerializer(WritableNestedModelSerializer):

    class Meta:
        model = Vehicle
        fields = ('reg_number', 'uf')


class VehicleUnitBasicReadSerializer(WritableNestedModelSerializer):

    class Meta:
        model = VehicleUnit
        fields = ('reg_number', 'uf')


class VehicleUnitSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):

    class Meta:
        model = VehicleUnit
        fields = ('reg_number', 'vehicle_type', 'payload', 'uf',
                  'volume', 'comment',
                  'contact',

                  )
        lookup_field = 'uf'

    def get_validators(self):
        validators = super().get_validators()
        # remove DRF auto validator that produces:
        # "The fields contact, reg_number must make a unique set."
        return [v for v in validators if not isinstance(v, UniqueTogetherValidator)]

    def validate(self, attrs):
        instance = self.instance

        contact = attrs.get("contact") if "contact" in attrs else (
            instance.contact if instance else None)
        reg_number = attrs.get("reg_number") or (
            instance.reg_number if instance else None)

        if contact and reg_number:
            qs = VehicleUnit.objects.filter(
                contact=contact, reg_number=reg_number)

            if instance:
                qs = qs.exclude(pk=instance.pk)

            # Fallback: nested update without instance
            elif 'uf' in attrs:
                qs = qs.exclude(uf=attrs['uf'])

            if qs.exists():
                raise CustomApiException(409, 'unique_together')

        return attrs


class PersonBasicReadSerializer(WritableNestedModelSerializer):
    class Meta:
        model = Person
        fields = ('last_name', 'first_name', 'is_driver',
                  'is_private', 'default', 'uf')


class PersonSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['company_name'] = instance.contact.company_name if instance.contact else None

        return response

    class Meta:
        model = Person
        lookup_field = 'uf'
        fields = ('last_name', 'first_name', 'email', 'phone', 'default',
                  'comment', 'is_driver', "is_private", 'uf')


class ContactFKSerializer(WritableNestedModelSerializer):

    class Meta:
        model = Contact
        fields = ('company_name', 'uf',
                  )


class ContractListSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):

    contact = ContactFKSerializer()

    reference_date = SlugRelatedField(
        allow_null=True, slug_field='code', queryset=ContractReferenceDate.objects.all())

    class Meta:
        model = Contract
        lookup_field = 'uf'
        fields = ("title", 'content', "is_active", "is_signed", "signed_at", "days_to_pay",  "created_at", 'uf',
                  'contact',
                  "reference_date",
                  )


class ContractFKSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):

    reference_date = SlugRelatedField(
        allow_null=True, slug_field='code', queryset=ContractReferenceDate.objects.all(), required=True)

    def create(self, validated_data):
        # print('5618:', validated_data)

        relations, reverse_relations = self._extract_relations(validated_data)

        # Create or update direct relations (foreign key, one-to-one)
        self.update_or_create_direct_relations(
            validated_data,
            relations,
        )

        ### Assign the company here ###
        request = self.context["request"]
        user = request.user
        validated_data["company"] = get_user_company(user)

        # Create instance with atomic
        with transaction.atomic():
            instance = super().create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    class Meta:
        model = Contract
        lookup_field = 'uf'
        fields = ("title", "is_active", "is_signed", "signed_at", "days_to_pay", 'number', 'date', 'title', 'content', "created_at", 'uf',
                  "reference_date",
                  )


class ContactSiteForContactSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):
    '''
    To be used as child serializer for ContactSerializer
    '''

    country_code_site = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Country.objects.all(), required=False)

    class Meta:
        model = ContactSite
        lookup_field = 'uf'
        fields = ('name_site', 'address_site', 'city_site', 'zip_code_site', 'country_code_site', 'lat', 'lon', 'uf',
                  )


class ContactTripListSerializer(WritableNestedModelSerializer):
    contact_vehicles = VehicleBasicReadSerializer(many=True)

    class Meta:
        model = Contact
        fields = ('company_name', 'uf',
                  'contact_vehicles'
                  )


class ContactBasicReadSerializer(WritableNestedModelSerializer):
    status = ContactStatusSerializer(read_only=True)
    country_code_post = CountrySerializer(allow_null=True)

    class Meta:
        model = Contact
        fields = ('fiscal_code', 'company_name', 'zip_code_post', 'city_post', 'address_post', 'lat', 'lon', 'uf',
                  'country_code_post', 'status',
                  )


class ContactSerializer(WritableNestedModelSerializer):
    status = ContactStatusSerializer(read_only=True)

    country_code_legal = serializers.SlugRelatedField(
        slug_field='uf', queryset=Country.objects.all(), write_only=True, required=True)

    contract_reference_date = SlugRelatedField(
        slug_field='uf', queryset=ContractReferenceDate.objects.all(), allow_null=True, required=False)

    contact_sites = ContactSiteForContactSerializer(many=True)
    contact_persons = PersonSerializer(many=True)
    contact_bank_accounts = BankAccountSerializer(many=True)
    contact_vehicles = VehicleContactSerializer(many=True)

    contact_contracts = ContractFKSerializer(many=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response['contact_type'] = instance.contact_type if instance.contact_type else None

        response['country_code_legal'] = CountrySerializer(
            instance.country_code_legal).data if instance.country_code_legal else None
        response['country_code_post'] = CountrySerializer(
            instance.country_code_post).data if instance.country_code_post else None

        return response

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
        model = Contact
        fields = ('company_name', 'alias_company_name', 'is_same_address', 'contact_type', 'uf',
                  'fiscal_code', 'vat_code', 'reg_com', 'subscribed_capital',
                  'is_vat_payer', 'email', 'phone', 'messanger',
                  'contract_reference_date',
                  'country_code_legal', 'zip_code_legal', 'city_legal', 'address_legal', 'county_legal', 'sect_legal',
                  'comment1', 'comment2',
                  'lat', 'lon',
                  'status',
                  'contact_persons', 'contact_vehicles', 'contact_bank_accounts', 'contact_sites',
                  'contact_contracts',
                  )

###### Start Contact Site Serializers ######


class ContactSiteBasicReadSerializer(WritableNestedModelSerializer):
    country_code_site = CountrySerializer(allow_null=True)

    class Meta:
        model = ContactSite
        fields = ('name_site', 'address_site', 'city_site', 'zip_code_site', 'lat', 'lon', 'uf',
                  'phone', 'email', 'comment1', 'comment2',
                  'country_code_site',
                  )


class ContactSiteListSerializer(WritableNestedModelSerializer):
    country_code_site = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Country.objects.all(), required=False)

    class Meta:
        model = ContactSite
        lookup_field = 'uf'
        fields = ('name_site', 'address_site', 'city_site', 'zip_code_site', 'lat', 'lon', 'uf',
                  'phone', 'email', 'comment1', 'comment2', 'language',
                  'country_code_site',
                  )


class ContactSiteSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get('request')
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            user_company = get_user_company(user)
        else:
            user_company = None

        if user_company:
            self.fields['contact'].queryset = Contact.objects.filter(
                company=user_company)

    contact = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.none(), write_only=True)

    country_code_site = SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Country.objects.all(), write_only=True)
    site_persons = PersonSerializer(many=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        response['country_code_site'] = CountrySerializer(
            instance.country_code_site).data if instance.country_code_site else None

        response['contact'] = ContactBasicReadSerializer(
            instance.contact).data if instance.contact else None

        return response

    class Meta:
        model = ContactSite
        lookup_field = 'uf'
        fields = ('name_site', 'address_site', 'city_site', 'zip_code_site', 'lat', 'lon', 'uf',
                  'phone', 'email', 'comment1', 'comment2', 'language',
                  'country_code_site', 'contact',
                  'site_persons',
                  )

###### End Contact Site Serializers ######


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

        ###### Assign the company here ######
        request = self.context["request"]
        user = request.user
        validated_data["company"] = get_user_company(user)

        # Create instance with atomic
        with transaction.atomic():
            instance = super(NestedCreateMixin,
                             self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    # def update(self, instance, validated_data):
    #     # print('3347', validated_data, instance)
    #     relations, reverse_relations = self._extract_relations(validated_data)

    #     # Create or update direct relations (foreign key, one-to-one)
    #     self.update_or_create_direct_relations(
    #         validated_data,
    #         relations,
    #     )

    #     # Update instance with atomic
    #     with transaction.atomic():
    #         instance = super(NestedUpdateMixin, self).update(
    #             instance,
    #             validated_data,
    #         )
    #         self.update_or_create_reverse_relations(
    #             instance, reverse_relations)
    #         self.delete_reverse_relations_if_need(instance, reverse_relations)
    #         instance.refresh_from_db()
    #         return instance

    class Meta:
        model = PaymentTerm
        fields = ('payment_term_short', 'payment_term_description',
                  'payment_term_days', 'uf')


class TermSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = Term
        fields = ('term_short', 'term_description', 'uf')


class CommentSerializer(WritableNestedModelSerializer):
    class Meta:
        model = Comment
        fields = ('comment', 'uf')


class CMRSerializer(serializers.ModelSerializer):

    def save(self, **kwargs):
        self._save_kwargs = defaultdict(dict, kwargs)

        # Extract parent load from kwargs
        parent_load = kwargs.get("load")
        if not parent_load:
            raise serializers.ValidationError(
                "E683 A valid parent instance is required.")

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
