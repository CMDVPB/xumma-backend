from rest_framework import serializers
from django.conf import settings

from baa.models import VehicleChecklist, VehicleChecklistAnswer, VehicleChecklistItem, VehicleChecklistPhoto, VehicleEquipment


class VehicleChecklistItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = VehicleChecklistItem
        fields = [
            "id",
            "uf",
            "code",
            "title",
            "description",
            "order",
            "is_active",
            "is_system",
        ]


class VehicleChecklistPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VehicleChecklistPhoto
        fields = [
            "id",
            "uf",
            "answer",
            "image",
            "image_url",
            "created_at",
        ]
        read_only_fields = ["id", "uf",  "answer", "created_at"]

    def get_image_url(self, obj):
        return f"{settings.BACKEND_URL}/api/inspection-files/{obj.uf}/"


class VehicleChecklistAnswerSerializer(serializers.ModelSerializer):
    answer_photos = VehicleChecklistPhotoSerializer(many=True, read_only=True)
    item = VehicleChecklistItemSerializer(read_only=True)

    class Meta:
        model = VehicleChecklistAnswer
        fields = [
            "id",
            "item",
            "is_ok",
            "comment",
            "answer_photos",
        ]


class VehicleChecklistListSerializer(serializers.ModelSerializer):
    checklist_answers = VehicleChecklistAnswerSerializer(
        many=True, read_only=True)

    driver_name = serializers.SerializerMethodField()
    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number", read_only=True
    )

    class Meta:
        model = VehicleChecklist
        fields = [
            "id",
            "company",
            "vehicle",
            "driver",
            "started_at",
            "finished_at",
            "mileage",
            "general_comment",
            "is_completed",
            "checklist_answers",
            "uf",

            # computed display fields
            "driver_name",
            "vehicle_reg_number",
        ]

    def get_driver_name(self, obj):
        return obj.driver.get_full_name() if obj.driver else None


class VehicleChecklistSerializer(serializers.ModelSerializer):
    checklist_answers = VehicleChecklistAnswerSerializer(
        many=True, read_only=True)
    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number", read_only=True
    )

    class Meta:
        model = VehicleChecklist
        fields = [
            "id",
            "uf",
            "company",
            "vehicle",
            "vehicle_reg_number",
            "driver",
            "inspection_type",
            "started_at",
            "finished_at",
            "mileage",
            "general_comment",
            "is_completed",
            "checklist_answers",
        ]


class VehicleEquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleEquipment
        fields = [
            "id",
            "uf",
            "vehicle",
            "name",
            "quantity",
            "updated_at",
        ]
        read_only_fields = ["id", "uf", "updated_at"]
