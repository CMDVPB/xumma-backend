from django.conf import settings
from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers
from rest_framework.serializers import SlugRelatedField

from abb.models import Currency
from abb.serializers import CurrencySerializer
from abb.serializers_drf_writable import CustomWritableNestedModelSerializer, CustomUniqueFieldsMixin
from att.models import BankAccount, Note, Vehicle
from axx.models import Load
from ayy.models import DamageReport, ImageUpload


User = get_user_model()


class BankAccountSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):

    currency_code = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())

    # currency_code = CurrencySerializer(allow_null=True)

    # def create(self, validated_data):
    #     # print('0604', validated_data)
    #     relations, reverse_relations = self._extract_relations(validated_data)

    #     # Create or update direct relations (foreign key, one-to-one)
    #     self.update_or_create_direct_relations(
    #         validated_data,
    #         relations,
    #     )

    #     # Create instance with atomic
    #     with transaction.atomic():
    #         instance = super(NestedCreateMixin,
    #                          self).create(validated_data)
    #         self.update_or_create_reverse_relations(
    #             instance, reverse_relations)

    #     return instance

    # def update(self, instance, validated_data):
    #     # print('3190', validated_data, instance)
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
        model = BankAccount
        fields = ('iban_number', 'bank_name', 'bank_address', 'bank_code', 'add_instructions', 'include_in_inv', 'uf',
                  'currency_code', 'contact',
                  )


class NoteSerializer(WritableNestedModelSerializer):

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
        model = Note
        fields = ('note_short', 'note_description', 'uf')


class ImageUploadInSerializer(WritableNestedModelSerializer):

    load = SlugRelatedField(
        allow_null=True,
        slug_field='uf',
        queryset=Load.objects.all(),
        required=False,
        write_only=True
    )

    user = SlugRelatedField(
        allow_null=True,
        slug_field='uf',
        queryset=User.objects.all(),
        required=False,
        write_only=True,
    )

    vehicle = SlugRelatedField(
        allow_null=True,
        slug_field='uf',
        queryset=Vehicle.objects.all(),
        required=False,
        write_only=True,
    )

    damage = SlugRelatedField(
        allow_null=True,
        slug_field='uf',
        queryset=DamageReport.objects.all(),
        required=False,
        write_only=True,
    )

    def to_internal_value(self, data):
        # normalize empty strings → None
        for field in ("load", "user", "vehicle", "damage"):
            if data.get(field) == "":
                data[field] = None

        return super().to_internal_value(data)

    def validate(self, attrs):
        """
        Exactly ONE of load / user / vehicle must be set
        """
        relations = [
            attrs.get("load"),
            attrs.get("user"),
            attrs.get("vehicle"),
            attrs.get("damage"),
        ]

        if sum(bool(rel) for rel in relations) != 1:
            raise serializers.ValidationError(
                "Exactly one of 'load', 'user', 'vehicle', 'damage' must be provided."
            )

        return attrs

    class Meta:
        model = ImageUpload
        fields = ('file_name', 'file_obj', 'uf',
                  'company', 'load', 'user', 'vehicle', 'damage',
                  )


class ImageUploadOutSerializer(WritableNestedModelSerializer):

    # load = serializers.SlugRelatedField(
    #     allow_null=True, slug_field='uf', queryset=Load.objects.all(), write_only=True, required=False)
    # user = serializers.SlugRelatedField(
    #     allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True, required=False)

    file_obj = serializers.SerializerMethodField(read_only=True)

    # def to_internal_value(self, data):
    #     # print('4574',)

    #     if 'load' in data and data['load'] == '':
    #         data['load'] = None

    #     return super(ImageUploadOutSerializer, self).to_internal_value(data)

    def validate(self, attrs):
        relations = [
            attrs.get('company'),
            attrs.get('load'),
            attrs.get('user'),
            attrs.get('vehicle'),
            attrs.get('damaage'),
        ]

        # print('3972', attrs)

        if sum(bool(r) for r in relations) != 1:
            raise serializers.ValidationError(
                'Exactly one relation (load, user, vehicle, company, damage) must be provided.'
            )

        return attrs

    class Meta:
        model = ImageUpload
        fields = ('uf', 'company',
                  'file_name', 'file_obj',
                  'load', 'user', 'damage',
                  )

    def get_file_obj(self, obj):
        # ✅ ALWAYS return backend proxy URL
        return f"{settings.BACKEND_URL}/api/image/{obj.uf}/"
