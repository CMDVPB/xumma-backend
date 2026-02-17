import logging
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.db import transaction
from django.conf import settings
from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import NestedCreateMixin, NestedUpdateMixin, UniqueFieldsMixin

from abb.models import Currency
from abb.utils import get_company_manager, get_company_users, get_user_company
from app.models import UserCompensationSettings, UserProfile
from app.serializers import CompanyUserSerializer, UserBasicPlusSerializer
from att.models import UserBaseSalary, UserDailyAllowance, UserLoadingPointRate, UserUnloadingPointRate, UserVehicleKmRateOverride, Vehicle
from ayy.serializers import PhoneNumberSerializer, UserDocumentSerializer
from dff.serializers.serializers_bce import ImageUploadOutSerializer

logger = logging.getLogger(__name__)

User = get_user_model()


class UserBaseSalarySerializer(serializers.ModelSerializer):
    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())

    class Meta:
        model = UserBaseSalary
        fields = (
            'id',
            'amount',
            'currency',
            'valid_from',
            'valid_to',
        )


class UserDailyAllowanceSerializer(serializers.ModelSerializer):
    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())

    class Meta:
        model = UserDailyAllowance
        fields = (
            'id',
            'amount_per_day',
            'currency',
            'applies_only_during_trip',
            'valid_from',
            'valid_to',
        )


class UserVehicleKmRateOverrideSerializer(serializers.ModelSerializer):

    vehicle = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.all())
    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())

    class Meta:
        model = UserVehicleKmRateOverride
        fields = (
            'id',
            'vehicle',
            'rate_per_km',
            'currency',
            'valid_from',
            'valid_to',
        )


class UserLoadingPointRateSerializer(serializers.ModelSerializer):
    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())

    class Meta:
        model = UserLoadingPointRate
        fields = (
            'id',
            'amount_per_point',
            'currency',
            'valid_from',
            'valid_to',
        )


class UserUnloadingPointRateSerializer(serializers.ModelSerializer):
    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())

    class Meta:
        model = UserUnloadingPointRate
        fields = (
            'id',
            'amount_per_point',
            'currency',
            'valid_from',
            'valid_to',
        )


class UserCompensationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCompensationSettings
        fields = (
            "has_per_km_income",
            "paid_by_loading_points",
            "paid_by_unloading_points",
        )


class UserCompleteSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    company = CompanyUserSerializer(read_only=True)

    avatar = serializers.SerializerMethodField()  # read

    user_documents = UserDocumentSerializer(
        many=True, context={'request': 'request'})
    user_phone_numbers = PhoneNumberSerializer(
        many=True, context={'request': 'request'})
    user_imageuploads = ImageUploadOutSerializer(
        many=True, context={'request': 'request'}, read_only=True)

    user_base_salaries = UserBaseSalarySerializer(many=True,)

    user_daily_allowances = UserDailyAllowanceSerializer(many=True,)

    user_vehicle_km_rate_overrides = UserVehicleKmRateOverrideSerializer(
        many=True,)

    user_loading_point_rates = UserLoadingPointRateSerializer(many=True,)
    user_unloading_point_rates = UserUnloadingPointRateSerializer(many=True)

    compensation_settings = UserCompensationSettingsSerializer(allow_null=True)

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

        return response

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'personal_id', 'phone', 'messanger', 'comment', 'lang', 'uf',
                  'date_registered', 'date_of_birth', 'date_termination', 'is_archived',
                  'company',

                  'user_documents', 'user_phone_numbers', 'user_imageuploads',

                  ### compensation ###
                  'user_base_salaries',
                  'user_daily_allowances',
                  'user_vehicle_km_rate_overrides',
                  'user_loading_point_rates',
                  'user_unloading_point_rates',
                  "compensation_settings",

                  'avatar',
                  )

    def get_avatar(self, obj):
        try:
            profile = obj.user_profile
        except UserProfile.DoesNotExist:
            return None

        if profile.avatar:
            return f"{settings.BACKEND_URL}/api/users-avatar/{profile.uf}/"

        return None
