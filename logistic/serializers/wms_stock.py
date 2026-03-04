from rest_framework import serializers
from logistic.models import WHStock


class WHStockSerializer(serializers.ModelSerializer):

    product = serializers.CharField(source="product.uf", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    owner = serializers.CharField(source="product.owner.uf", read_only=True)
    owner_name = serializers.CharField(
        source="product.owner.company_name",
        read_only=True
    )

    location = serializers.CharField(source="location.uf", read_only=True)
    location_code = serializers.CharField(source="location.code", read_only=True)

    class Meta:
        model = WHStock
        fields = [
            "uf",
            "product",
            "product_name",
            "owner",
            "owner_name",
            "location",
            "location_code",
            "quantity",
        ]