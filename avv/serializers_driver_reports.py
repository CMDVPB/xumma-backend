from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db.models import Sum
from rest_framework import serializers

from abb.utils import get_user_company
from att.models import Vehicle
from avv.models import DriverReport, DriverReportImage


User = get_user_model()


class DriverReportImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverReportImage
        fields = ["id", "image"]

    def create(self, validated_data):
        request = self.context["request"]
        report = self.context["report"]

        return DriverReportImage.objects.create(
            company=report.company,
            created_by=request.user,
            report=report,
            **validated_data,
        )


class DriverReportCreateSerializer(serializers.ModelSerializer):
    # driver is always request.user, so we don't expose it in payload
    vehicle = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=Vehicle.objects.all(),
    )

    class Meta:
        model = DriverReport
        fields = [
            "id",
            "uf",
            "vehicle",
            "title",
            "description",
            "odometer",
        ]
        read_only_fields = ["id", "uf"]

    def validate_vehicle(self, vehicle):
        company = get_user_company(self.context["request"].user)
        if vehicle.company_id != company.id:
            raise serializers.ValidationError(
                "Vehicle does not belong to your company.")
        return vehicle

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        company = get_user_company(user)

        return DriverReport.objects.create(
            company=company,
            created_by=user,
            driver=user,
            status=DriverReport.Status.DRAFT,
            **validated_data,
        )


class DriverReportDetailsSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(
        source="driver.get_full_name",
        read_only=True,
    )

    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number",
        read_only=True,
    )
    work_order_id = serializers.IntegerField(
        source="related_work_order_id", read_only=True)
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.get_full_name", read_only=True)
    images = serializers.SerializerMethodField()

    class Meta:
        model = DriverReport
        fields = [
            "id",
            "uf",
            "created_at",
            "status",
            "vehicle",
            "vehicle_reg_number",
            "driver_name",
            "title",
            "description",
            "odometer",
            "reviewed_at",
            "related_work_order",
            "images",
        ]

    def get_images(self, obj):
        return [
            img.image.url
            for img in obj.report_driver_report_images.all()
        ]


class DriverReportListSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(
        source="driver.get_full_name", read_only=True)
    driver_uf = serializers.CharField(source="driver.uf", read_only=True)
    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number", read_only=True)
    work_order_id = serializers.IntegerField(
        source="related_work_order_id", read_only=True)
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.get_full_name",
        read_only=True
    )

    images_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DriverReport
        fields = [
            "id",
            "uf",
            "created_at",
            "status",
            "driver_uf",
            "driver_name",
            "vehicle",
            "vehicle_reg_number",
            "title",
            "odometer",
            "work_order_id",
            "images_count",
            "reviewed_by_name",
            "work_order_id",
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name()
        return None
