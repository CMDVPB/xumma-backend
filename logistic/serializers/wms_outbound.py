from rest_framework import serializers

from logistic.models import WHOutbound



class WHOutboundSerializer(serializers.ModelSerializer):

    owner_name = serializers.CharField(
        source="owner.company_name",
        read_only=True
    )

    class Meta:
        model = WHOutbound
        fields = [
            "uf",
            "reference",
            "owner",
            "owner_name",
            "status",
            "planned_pickup_at",
            "shipped_at",
            "created_at",
        ]