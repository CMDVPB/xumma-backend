from rest_framework import serializers

from logistic.models import WHInbound


class WHInboundSerializer(serializers.ModelSerializer):

    owner_name = serializers.CharField(
        source="owner.company_name",
        read_only=True
    )

    class Meta:
        model = WHInbound
        fields = [
            "uf",
            "owner",
            "owner_name",
            "reference",
            "status",
            "received_at",
            "created_at",
        ]
        read_only_fields = [
            "status",
            "received_at",
            "created_at",
        ]