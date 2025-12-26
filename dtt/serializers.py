from collections import defaultdict
from click import group
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.utils import get_user_company
from att.models import VehicleCompany
from att.serializers import VehicleCompanySerializer
from ayy.models import DamageReport, VehicleDamage

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
            self.fields['vehicle'].queryset = VehicleCompany.objects.filter(
                company=user_company)

    vehicle = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=VehicleCompany.objects.none())
    reported_by = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.none())
    driver = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.none())

    report_vehicle_damages = VehicleDamageSerializer(many=True)

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
        fields = ('damage_report_type', 'reported_at', 'location', 'notes', 'uf',
                  'vehicle', 'driver', 'reported_by',
                  'report_vehicle_damages',
                  )
        read_only_fields = ("company",)
