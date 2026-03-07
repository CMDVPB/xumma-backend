from rest_framework import serializers

from lync.models import LoadSecret



class LoadSecretSerializer(serializers.ModelSerializer):

    class Meta:
        model = LoadSecret
        fields = [
            "payload",
            "date_created",
            "date_modified"
        ]

    def validate_payload(self, value):

        allowed = {
            "internal_note",
            "real_margin_target",
            "manager_comment",
            "flags"
        }

        clean = {}

        for k, v in value.items():
            if k in allowed:
                clean[k] = v

        return clean