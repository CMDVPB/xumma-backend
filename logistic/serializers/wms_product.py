from rest_framework import serializers
from logistic.models import WHProduct


class WHProductSerializer(serializers.ModelSerializer):

    owner_name = serializers.CharField(
        source="owner.company_name",
        read_only=True
    )

    class Meta:
        model = WHProduct
        fields = [
            "uf",
            "owner",
            "owner_name",
            "sku",
            "name",
            "description",
            "uom",
            "weight_kg",
            "volume_m3",
            "is_active",
            "created_at",
        ]

        read_only_fields = [
            "uf",
            "created_at",
        ]