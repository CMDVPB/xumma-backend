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
from ayy.models import AuthorizationStockBatch, CMRStockBatch, CTIRStockBatch

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

    countries_authorization = serializers.SlugRelatedField(
        many=True, slug_field='uf', queryset=Country.objects.all())

    class Meta:
        model = AuthorizationStockBatch
        fields = ('series', 'number', 'received_at', 'date_expire', 'price', 'notes', 'uf',
                  'type_authorization', 'category_authorization', 'vehicle_authorization',
                  'countries_authorization',
                  )
        read_only_fields = ("company",)

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
            instance = super(NestedCreateMixin, self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    # def update(self, instance, validated_data):
    #     # print('3347', validated_data)

    #     # # Extract nested CMR data before relations pop it
    #     # cmr_data = validated_data.pop('cmr', None)

    #     relations, reverse_relations = self._extract_relations(validated_data)

    #     # Create or update direct relations (foreign key, one-to-one)
    #     self.update_or_create_direct_relations(validated_data, relations)

    #     # Update instance with atomic
    #     with transaction.atomic():
    #         instance = super(NestedUpdateMixin, self).update(
    #             instance,
    #             validated_data,
    #         )
    #         self.update_or_create_reverse_relations(
    #             instance, reverse_relations)
    #         self.delete_reverse_relations_if_need(instance, reverse_relations)

    #         # # ✅ Handle CMR update/create automatically
    #         # if cmr_data:

    #         #     CMR.objects.update_or_create(
    #         #         load=instance,
    #         #         defaults={**cmr_data, "company": instance.company},
    #         #     )

    #         instance.refresh_from_db()
    #         return instance


class CTIRStockBatchSerializer(WritableNestedModelSerializer):

    class Meta:
        model = CTIRStockBatch
        fields = ('series', 'number', 'received_at', 'date_expire', 'price', 'notes', 'uf',
                  )
        read_only_fields = ("company",)

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        company = get_user_company(user)

        return CTIRStockBatch.objects.create(
            company=company,
            **validated_data
        )
