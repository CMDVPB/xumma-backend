from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.conf import settings
from rest_framework import serializers


from abb.utils import get_user_company
from att.models import Vehicle
from avv.models import DriverReport, DriverReportImage


User = get_user_model()


class DriverReportImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverReportImage
        fields = ["id", "image", "report"]

    def validate_image(self, img):
        if img.size > 1024*1024*10:
            raise serializers.ValidationError("Max 10MB")
        return img


class DriverReportImageReadSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = DriverReportImage
        fields = ["id", "image_url"]

    def get_image_url(self, obj):
        return f"{settings.BACKEND_URL}/api/image/{obj.uf}/"


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
    images = DriverReportImageReadSerializer(
        source="report_driver_report_images",
        many=True,
        read_only=True
    )

    class Meta:
        model = DriverReport
        fields = [
            "id",
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
            "work_order_id",
            "reviewed_by_name",
            "uf",
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


# class DriverReportDetailSerializer(serializers.ModelSerializer):
#     images = DriverReportImageSerializer(
#         source="report_driver_report_images",
#         many=True,
#         read_only=True
#     )

#     class Meta:
#         model = DriverReport
#         fields = "__all__"
