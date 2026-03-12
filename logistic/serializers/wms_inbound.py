from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from att.models import Contact
from logistic.models import WHInbound, WHInboundLine, WHLocation, WHProduct


class WHOwnerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Contact
        fields = [
            "uf",
            "company_name",
        ]

class WHInboundLineSerializer(serializers.ModelSerializer):

    product = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=WHProduct.objects.all()
    )

    location = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=WHLocation.objects.all()
    )


    class Meta:
        model = WHInboundLine
        fields = [
            "uf",
            "product",
            "location",
            "quantity",
            "pallets",
            "pallet_type",
            "area_m2",
            "volume_m3",
        ]


class WHInboundDetailSerializer(serializers.ModelSerializer):

    owner = serializers.SlugRelatedField(
        queryset=Contact.objects.all(),
        slug_field="uf",
        write_only=True,
    )

    owner_info = WHOwnerSerializer(source="owner", read_only=True)

    inbound_lines = WHInboundLineSerializer(many=True)

    class Meta:
        model = WHInbound
        fields = [
            "uf",
            "owner",
            "owner_info",
            "reference",
            "status",
            "received_at",
            "created_at",
            "inbound_lines",
        ]
        read_only_fields = [
            "status",
            "received_at",
            "created_at",
        ]
        
    def create(self, validated_data):

        lines = validated_data.pop("inbound_lines", [])

        inbound = WHInbound.objects.create(**validated_data)

        for line in lines:
            WHInboundLine.objects.create(
                inbound=inbound,
                **line
            )

        return inbound
    
    @transaction.atomic
    def update(self, instance, validated_data):

        lines = validated_data.pop("inbound_lines", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # remove old lines
        instance.inbound_lines.all().delete()

        # recreate
        for line in lines:
            WHInboundLine.objects.create(
                inbound=instance,
                **line
            )

        return instance

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

    total_pallets = serializers.SerializerMethodField()
    total_m2 = serializers.SerializerMethodField()
    total_m3 = serializers.SerializerMethodField()
    total_units = serializers.SerializerMethodField()

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

            "total_pallets",
            "total_m2",
            "total_m3",
            "total_units",
        ]
        read_only_fields = [
            "status",
            "received_at",
            "created_at",
        ]


    def get_total_pallets(self, obj):
        return (
            obj.inbound_lines.aggregate(v=Sum("pallets"))["v"] or 0
        )

    def get_total_m2(self, obj):
        return (
            obj.inbound_lines.aggregate(v=Sum("area_m2"))["v"] or 0
        )

    def get_total_m3(self, obj):
        return (
            obj.inbound_lines.aggregate(v=Sum("volume_m3"))["v"] or 0
        )

    def get_total_units(self, obj):
        return (
            obj.inbound_lines.aggregate(v=Sum("quantity"))["v"] or 0
        )