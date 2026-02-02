from rest_framework import serializers

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
        read_only_fields = ["id", "uf", "created_at"]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class VehicleChecklistAnswerSerializer(serializers.ModelSerializer):
    answer_photos = VehicleChecklistPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = VehicleChecklistAnswer
        fields = [
            "id",
            "item",
            "is_ok",
            "comment",
            "answer_photos",
        ]


class VehicleChecklistSerializer(serializers.ModelSerializer):
    checklist_answers = VehicleChecklistAnswerSerializer(
        many=True, read_only=True)

    class Meta:
        model = VehicleChecklist
        fields = [
            "id",
            "uf",
            "company",
            "vehicle",
            "driver",
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
