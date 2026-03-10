from rest_framework import serializers
from att.models import Contact
from logistic.models import WHProduct

class WHProductOwnerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Contact
        fields = [
            "uf",
            "company_name",
        ]


class WHProductSerializer(serializers.ModelSerializer):
    owner = serializers.SlugRelatedField(
        queryset=Contact.objects.all(),
        slug_field="uf",
        write_only=True,
    )
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




class WHProductDetailsSerializer(serializers.ModelSerializer):
    owner = serializers.SlugRelatedField(
        queryset=Contact.objects.all(),
        slug_field="uf",
        write_only=True,
    )

    owner_info = WHProductOwnerSerializer(source="owner", read_only=True)
   
    class Meta:
        model = WHProduct
        fields = [
            "uf",
            "owner",          
            "owner_info",
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