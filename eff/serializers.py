
from django.conf import settings
from rest_framework import serializers

from abb.utils import generate_signed_url
from app.models import TypeCost
from ayy.models import ImageUpload


class ImageUploadSocialMediaSerializer(serializers.ModelSerializer):
    signed_url = serializers.SerializerMethodField()

    class Meta:
        model = ImageUpload
        fields = ('signed_url',
                  )

    def get_signed_url(self, obj):
        signed_path = generate_signed_url(
            f"/api/image-signed/{obj.uf}/"

        )
        return f"{settings.BACKEND_URL}{signed_path}"


class TypeCostListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeCost
        fields = (
            'serial_number',
            'code',
            'label',
            'is_system',
            'uf',
        )
