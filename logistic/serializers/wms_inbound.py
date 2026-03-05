from rest_framework import serializers

from att.models import Contact
from logistic.models import WHInbound, WHInboundLine


class WHInboundLineSerializer(serializers.ModelSerializer):

    class Meta:
        model = WHInboundLine
        fields = [
            "id",
            "product",
            "quantity_expected",
            "quantity_received",
            "uf",
        ]

class WHInboundDetailSerializer(serializers.ModelSerializer):

    owner = serializers.SlugRelatedField(
        queryset=Contact.objects.all(),
        slug_field="uf",
        write_only=True,
    )

    owner_name = serializers.CharField(
        source="owner.company_name",
        read_only=True
    )

    lines = WHInboundLineSerializer(many=True, read_only=True)

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
            "lines",
        ]
        read_only_fields = [
            "status",
            "received_at",
            "created_at",
        ]
        

class WHInboundSerializer(serializers.ModelSerializer):
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
        model = WHInbound
        fields = [
            "owner",
            "owner_name",
            "reference",
            "status",
            "received_at",
            "created_at",
            "uf",
        ]
        read_only_fields = [
            "status",
            "received_at",
            "created_at",
        ]
