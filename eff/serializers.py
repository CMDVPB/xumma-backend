
from django.conf import settings
from rest_framework import serializers

from abb.utils import generate_signed_url
from ayy.models import ImageUpload


class ImageUploadSocialMediaSerializer(serializers.ModelSerializer):
    signed_url = serializers.SerializerMethodField()

    class Meta:
        model = ImageUpload
        fields = ('signed_url',
                  )

    def get_signed_url(self, obj):
        signed_path = generate_signed_url(
            f"/api/image-signed/{obj.token}/"

        )
        return f"{settings.BACKEND_URL}{signed_path}"
