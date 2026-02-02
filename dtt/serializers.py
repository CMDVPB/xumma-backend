from collections import defaultdict
from click import group
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.utils import get_request_language, get_user_company
from att.models import ContractReferenceDate, Vehicle
from att.serializers import VehicleSerializer
from ayy.models import DamageReport, VehicleDamage
from dff.serializers.serializers_bce import ImageUploadOutSerializer

User = get_user_model()


class VehicleDamageSerializer(WritableNestedModelSerializer):

    def create(self, validated_data):
        # print('5882:', validated_data)

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
            instance = super(NestedCreateMixin, self).create(validated_data)
            self.update_or_create_reverse_relations(
                instance, reverse_relations)

        return instance

    class Meta:
        model = VehicleDamage
        fields = ('damage_type', 'severity', 'part', 'description', 'amount', 'uf',

                  )


class DamageReportSerializer(WritableNestedModelSerializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get('request')
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            user_company = get_user_company(user)
        else:
            user_company = None

        if user_company:
            self.fields['reported_by'].queryset = user_company.user.all()
            self.fields['driver'].queryset = user_company.user.filter(
                groups__name='level_driver'
            )
            self.fields['vehicle'].queryset = Vehicle.objects.filter(
                company=user_company)

    vehicle = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.none())
    reported_by = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.none())
    driver = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.none())

    report_vehicle_damages = VehicleDamageSerializer(many=True)
    damage_imageuploads = ImageUploadOutSerializer(many=True, read_only=True)

    def create(self, validated_data):
        # print('5882:', validated_data)

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
            instance = super(NestedCreateMixin, self).create(validated_data)
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
        model = DamageReport
        fields = ('damage_report_type', 'reported_at', 'location', 'notes', 'route_sheet', 'is_insured', 'insurance_deductible', 'uf',
                  'vehicle', 'driver', 'reported_by',
                  'report_vehicle_damages', 'damage_imageuploads',
                  )
        read_only_fields = ("company",)


class ContractReferenceDateSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    def get_label(self, obj):
        request = self.context.get("request")
        lang = get_request_language(request)

        translation = obj.reference_date_translations.filter(
            language=lang).first()

        if translation:
            return translation.label

        # fallback to Romanian
        fallback = obj.reference_date_translations.filter(
            language="ro").first()
        return fallback.label if fallback else obj.code

    class Meta:
        model = ContractReferenceDate
        fields = ("id", "code", "label", "is_active", "order", 'uf',
                  'company',
                  )
