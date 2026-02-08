from collections import defaultdict
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers
import mimetypes
from rest_framework.serializers import SlugRelatedField
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin

from abb.models import BodyType, Currency, Incoterm, ModeType, StatusType
from abb.serializers_drf_writable import CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer
from abb.utils import get_request_language, get_user_company
from app.models import CategoryGeneral, TypeGeneral
from att.models import Contact, ContactStatus, EmissionClass, RouteSheetStockBatch, VehicleBrand, Vehicle, VehicleDocument, VehicleKmRate
from ayy.models import DocumentType, UserDocument
from ayy.serializers import DocumentTypeSerializer
from dff.serializers.serializers_bce import ImageUploadOutSerializer


User = get_user_model()


class TypeGeneralSerializer(serializers.ModelSerializer):

    class Meta:
        model = TypeGeneral
        fields = ('serial_number', 'code', 'label', 'is_system', 'uf')
        read_only_fields = ['is_system']


class CategoryGeneralSerializer(serializers.ModelSerializer):

    class Meta:
        model = CategoryGeneral
        fields = ('serial_number', 'code', 'label', 'is_system', 'uf')
        read_only_fields = ['is_system']


class IncotermSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = Incoterm
        fields = ('serial_number',  'code', 'label', 'uf')


class ModeTypeSerializer(WritableNestedModelSerializer):
    serial_number = serializers.CharField(read_only=True)

    class Meta:
        model = ModeType
        fields = ('serial_number', 'code', 'label', 'uf')


class BodyTypeSerializer(serializers.ModelSerializer):
    serial_number = serializers.CharField(read_only=True)

    class Meta:
        model = BodyType
        fields = ('serial_number', 'code', 'label', 'uf')


class EmissionClassSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = EmissionClass
        fields = ('code', 'label', 'description', 'serial_number',
                  'is_active', 'is_system', 'uf')


class VehicleBrandSerializer(UniqueFieldsMixin, WritableNestedModelSerializer):

    class Meta:
        model = VehicleBrand
        fields = ('name', 'serial_number', 'is_active', 'uf')


class StatusTypeSerializer(WritableNestedModelSerializer):
    serial_number = serializers.CharField(read_only=True)
    label = serializers.SerializerMethodField(read_only=True)

    def get_label(self, obj):
        request = self.context.get("request")
        lang = get_request_language(request)

        translation = obj.translations.filter(language=lang).first()

        if translation:
            return translation.label

        # fallback to Romanian
        fallback = obj.translations.filter(language="ro").first()
        return fallback.label if fallback else obj.code

    class Meta:
        model = StatusType
        fields = ('serial_number', 'order_number',
                  'description', 'label', 'uf')


class VehicleContactSerializer(CustomUniqueFieldsMixin, CustomWritableNestedModelSerializer):
    class Meta:
        model = Vehicle
        fields = ('reg_number', 'vehicle_type', 'comment', 'uf',
                  )


class VehicleKmRateSerializer(serializers.ModelSerializer):
    currency = serializers.SlugRelatedField(
        allow_null=True, slug_field='currency_code', queryset=Currency.objects.all())

    class Meta:
        model = VehicleKmRate
        fields = (
            'id',
            'rate_per_km',
            'currency',
            'valid_from',
            'valid_to',
        )


class VehicleDocumentSerializer(serializers.ModelSerializer):
    document_type = DocumentTypeSerializer(read_only=True)
    document_type_id = serializers.PrimaryKeyRelatedField(
        queryset=DocumentType.objects.all(),
        source='document_type',
        write_only=True
    )

    vehicle = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all()
    )

    file_url = serializers.SerializerMethodField(read_only=True)
    content_type = serializers.SerializerMethodField()

    # def update(self, instance, validated_data):
    #     new_file = validated_data.get('file')

    #     if new_file and instance.file:
    #         instance.file.delete(save=False)

    #     return super().update(instance, validated_data)

    class Meta:
        model = VehicleDocument
        fields = [
            'id',
            'uf',
            'vehicle',
            'document_type',
            'document_type_id',
            'document_number',
            'date_issued',
            'date_expiry',

            'notes',
            'file',
            'file_url',            # for download
            'content_type',       # file content_type
        ]
    read_only_fields = ('id', 'created_at')

    def validate(self, attrs):
        date_issued = attrs.get('date_issued')
        date_expiry = attrs.get('date_expiry')

        if date_expiry and date_issued and date_expiry < date_issued:
            raise serializers.ValidationError({
                'date_expiry': 'Expiry date must be after issue date'
            })

        return attrs

    def get_file_url(self, obj):
        if obj.file:
            return f"{settings.BACKEND_URL}/api/documents-files/{obj.uf}/"
        return None

    def get_content_type(self, obj):
        if not obj.file:
            return None

        content_type, _ = mimetypes.guess_type(obj.file.name)
        return content_type


class VehicleSerializer(WritableNestedModelSerializer):

    contact = SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all())
    brand = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=VehicleBrand.objects.all())
    vehicle_category = serializers.SlugRelatedField(
        allow_null=True, slug_field='code', queryset=CategoryGeneral.objects.all())
    vehicle_category_type = serializers.SlugRelatedField(
        allow_null=True, slug_field='code', queryset=TypeGeneral.objects.all())
    vehicle_body = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=BodyType.objects.all())
    emission_class = serializers.SlugRelatedField(
        allow_null=True, slug_field='code', queryset=EmissionClass.objects.all())

    vehicle_km_rates = VehicleKmRateSerializer(many=True)
    vehicle_imageuploads = ImageUploadOutSerializer(many=True, read_only=True)
    vehicle_documents = VehicleDocumentSerializer(many=True)

    def _empty_strings_to_none(self, data, fields):
        for field in fields:
            if data.get(field) == '':
                data[field] = None
        return data

    def to_internal_value(self, data):
        data = data.copy()  # IMPORTANT

        data = self._empty_strings_to_none(data, [
            'buy_price',
            'change_oil_interval',
            'consumption_summer',
            'consumption_winter',
            'height',
            'interval_taho',
            'length',
            'sell_price',
            'tank_volume',
            'volume_capacity',
            'weight_capacity',
            'width',
        ])

        return super().to_internal_value(data)

    class Meta:
        model = Vehicle
        fields = ('id', 'reg_number', 'vin', 'vehicle_type', 'date_registered', 'is_available', 'is_archived', 'is_service', 'uf',
                  'length', 'width', 'height', 'weight_capacity', 'volume_capacity',
                  'tank_volume', 'adblue_tank_volume', 'change_oil_interval', 'consumption_summer', 'consumption_winter',
                  'buy_price', 'sell_price', 'km_initial',
                  'interval_taho', 'last_date_unload_taho', 'comment',
                  'brand', 'vehicle_category', 'vehicle_category_type', 'vehicle_body', 'emission_class',
                  'contact',
                  'vehicle_imageuploads', 'vehicle_km_rates', 'vehicle_documents'
                  )


class UserDocumentSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(
        slug_field='uf',
        queryset=User.objects.all()
    )

    document_type = DocumentTypeSerializer(read_only=True)

    document_type_uf = serializers.SlugRelatedField(
        source='document_type',
        slug_field='uf',
        queryset=DocumentType.objects.all(),
        write_only=True
    )

    class Meta:
        model = UserDocument
        fields = ('user', 'document_number', 'date_issued', 'date_expiry', 'notes', 'uf',
                  'document_type',      # read
                  'document_type_uf',   # write
                  )
        read_only_fields = ('id', 'uf')

    def validate_document_type(self, value):
        if value.target != 'user':
            raise serializers.ValidationError(
                'This document type is not allowed for user documents.'
            )
        return value


class RouteSheetStockBatchSerializer(WritableNestedModelSerializer):
    class Meta:
        model = RouteSheetStockBatch
        fields = ('series', 'received_at', 'number_from', 'number_to', 'total_count', 'uf',
                  'used_count', 'notes', 'available_count',
                  )
        read_only_fields = ("company",)

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        company = get_user_company(user)

        return RouteSheetStockBatch.objects.create(
            company=company,
            **validated_data
        )


class ContactStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactStatus
        fields = (
            "id",
            "code",
            "name",
            "description",
            "is_blocking",
            "severity",
        )


class ContactStatusUpdateSerializer(serializers.Serializer):
    status_id = serializers.PrimaryKeyRelatedField(
        queryset=ContactStatus.objects.filter(is_active=True),
        source="status"
    )
    reason = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True
    )
