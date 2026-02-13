# notifications/serializers.py

from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):

    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "severity",
            "due_date",
            "related_object_type",
            "related_object_id",
            "is_read",

            "payload",
        ]

    def get_is_read(self, obj):
        user = self.context["request"].user

        return obj.read_states.filter(user=user).exists()
