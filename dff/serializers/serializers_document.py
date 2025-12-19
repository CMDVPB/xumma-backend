import logging
from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.models import Country
from abb.utils import get_user_company
from app.models import CategoryGeneral, TypeGeneral
from att.models import VehicleCompany
from ayy.models import AuthorizationStockBatch, CMRStockBatch

logger = logging.getLogger(__name__)


User = get_user_model()


class CMRStockBatchSerializer(WritableNestedModelSerializer):
    class Meta:
        model = CMRStockBatch
        fields = ('series', 'received_at', 'number_from', 'number_to', 'total_count', 'uf',
                  'used_count', 'notes', 'available_count',
                  )
        read_only_fields = ("company",)

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        company = get_user_company(user)

        return CMRStockBatch.objects.create(
            company=company,
            **validated_data
        )


class AuthorizationStockBatchSerializer(WritableNestedModelSerializer):
    type_authorization = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=TypeGeneral.objects.all())
    category_authorization = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=CategoryGeneral.objects.all())
    vehicle_authorization = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=VehicleCompany.objects.all())

    countries = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Country.objects.all())

    class Meta:
        model = CMRStockBatch
        fields = ('series', 'number', 'received_at', 'price', 'notes', 'uf',
                  'type_authorization', 'category_authorization', 'vehicle_authorization', 'countries'
                  )
        read_only_fields = ("company",)

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        company = get_user_company(user)

        return AuthorizationStockBatch.objects.create(
            company=company,
            **validated_data
        )
