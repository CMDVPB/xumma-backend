
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import NestedCreateMixin, NestedUpdateMixin, UniqueFieldsMixin

import logging

from abb.serializers import CountrySerializer, CurrencySerializer
from abb.utils import company_latest_exp_date_subscription, get_company_manager, get_company_users, get_user_company
from app.models import Company, UserSettings
from dff.serializers.serializers_bce import ImageUploadOutSerializer

logger = logging.getLogger(__name__)

User = get_user_model()


class CompanyUserSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    country_code_legal = CountrySerializer(allow_null=True)
    country_code_post = CountrySerializer(allow_null=True)

    class Meta:
        model = Company
        fields = ('id', 'logo', 'stamp', 'company_name', 'fiscal_code', 'vat_code', 'email', 'phone',
                  'country_code_legal', 'zip_code_legal', 'city_legal', 'address_legal',
                  'country_code_post',  'zip_code_post', 'city_post', 'address_post', 'comment')


class UserBasicSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    ''' As basic serializer for for other serializers '''

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name',
                  'phone', 'messanger', 'uf')


class UserBasicPlusSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    from ayy.serializers import PhoneNumberSerializer, DocumentSerializer

    user_documents = DocumentSerializer(
        many=True, context={'request': 'request'})
    user_phone_numbers = PhoneNumberSerializer(
        many=True, context={'request': 'request'})

    user_imageuploads = ImageUploadOutSerializer(
        many=True, context={'request': 'request'}, read_only=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        try:
            level = instance.groups.filter(name__startswith='level_').first()
            response['level'] = level.name
        except Exception as e:
            print('ES475', e)
            response['level'] = ''
            pass

        return response

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'personal_id', 'uf',
                  'comment', 'date_registered', 'date_of_birth', 'date_termination', 'is_archived',
                  'image', 'phone', 'messanger',
                  'user_documents', 'user_phone_numbers', 'user_imageuploads',
                  )


class UserSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):
    from ayy.serializers import PhoneNumberSerializer, DocumentSerializer

    company = CompanyUserSerializer(read_only=True)

    user_documents = DocumentSerializer(
        many=True, context={'request': 'request'})
    user_phone_numbers = PhoneNumberSerializer(
        many=True, context={'request': 'request'})
    user_imageuploads = ImageUploadOutSerializer(
        many=True, context={'request': 'request'}, read_only=True)

    def to_representation(self, instance):
        response = super().to_representation(instance)

        try:
            company_users = get_company_users(instance)
            response['company_users'] = UserBasicPlusSerializer(
                company_users, many=True).data

        except Exception as e:
            logger.error(f'ES275 Error UserSerializer: {e}')
            response['company_users'] = []
            pass

        try:
            level = instance.groups.filter(name__startswith='level_').first()
            response['level'] = level.name
        except Exception as e:
            logger.error(f'ES277 Error UserSerializer: {e}')
            response['level'] = 'level_dispatcher'
            pass

        try:
            user_company = get_user_company(instance)
            company_manager = get_company_manager(user_company)
            # print('5060 company manager:', company_manager.email)
            type_company = company_manager.groups.filter(
                name__startswith='type_').first()
            response['type_account'] = type_company.name

            base_country = company_manager.base_country or 'ro'
            response['base_country'] = base_country

        except Exception as e:
            logger.error(f'ES279 Error UserSerializer: {e}')
            pass

        try:
            user_company = get_user_company(instance)
            response['type_subscription'] = company_latest_exp_date_subscription(
                user_company)

        except Exception as e:
            logger.error(f'ES281 Error UserSerializer: {e}')

        return response

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'personal_id', 'phone', 'messanger', 'comment', 'image', 'lang', 'uf',
                  'date_registered', 'date_of_birth', 'date_termination', 'is_archived',
                  'company',
                  'user_documents', 'user_phone_numbers', 'user_imageuploads',
                  )


class UserSettingsSerializer(serializers.ModelSerializer):
    currency_default = CurrencySerializer(allow_null=True)

    class Meta:
        model = UserSettings
        fields = ('theme', 'notifications_enabled', 'simplified_load', 'uf',
                  'base_doc_lang', 'rows_per_page', 'myitems_all', 'order_by',
                  'currency_default',
                  'load_columns', 'load_2_columns', 'load_3_columns', 'load_4_columns', 'load_due_columns',
                  'trip_loads_columns', 'trip_columns', 'tor_columns', 'ctr_columns', 'quote_columns', 'inv_columns', 'exp_columns',
                  'default_document_tab',
                  )
