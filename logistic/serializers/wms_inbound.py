from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from att.models import Contact
from logistic.models import WHInbound, WHInboundCharge, WHInboundLine, WHLocation, WHProduct


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

    uf = serializers.CharField(required=False)

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
        extra_kwargs = {
            "uf": {"validators": []},
        }


class WHInboundChargeSerializer(serializers.ModelSerializer):
    uf = serializers.CharField(required=False)

    class Meta:
        model = WHInboundCharge
        fields = [
            "uf",
            "charge_type",
            "label",
            "unit_type",
            "quantity",
            "unit_price",
            "total",
            "fee_type",
            "handling_unit",
            "is_manual_price",
        ]
        read_only_fields = ["total"]
        extra_kwargs = {
            "uf": {"validators": []},
        }


class WHInboundDetailSerializer(serializers.ModelSerializer):

    owner = serializers.SlugRelatedField(queryset=Contact.objects.all(), slug_field="uf", write_only=True)
    owner_info = WHOwnerSerializer(source="owner", read_only=True)
    inbound_lines = WHInboundLineSerializer(many=True)    
    inbound_charges = WHInboundChargeSerializer(many=True, required=False)


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
            "inbound_charges",
        ]
        read_only_fields = [
            "status",
            "received_at",
            "created_at",
        ]
        
    # def create(self, validated_data):

    #     lines = validated_data.pop("inbound_lines", [])

    #     inbound = WHInbound.objects.create(**validated_data)

    #     for line in lines:
    #         WHInboundLine.objects.create(
    #             inbound=inbound,
    #             **line
    #         )

    #     return inbound
    
    # @transaction.atomic
    # def update(self, instance, validated_data):

    #     lines = validated_data.pop("inbound_lines", [])

    #     for attr, value in validated_data.items():
    #         setattr(instance, attr, value)

    #     instance.save()

    #     # remove old lines
    #     instance.inbound_lines.all().delete()

    #     # recreate
    #     for line in lines:
    #         WHInboundLine.objects.create(
    #             inbound=instance,
    #             **line
    #         )

    #     return instance



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

    inbound_lines = WHInboundLineSerializer(many=True, required=False)
    inbound_charges = WHInboundChargeSerializer(many=True, required=False)

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
            
            "inbound_lines",
            "inbound_charges",
        ]
        read_only_fields = [
            "status",
            "received_at",
            "created_at",
        ]

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop("inbound_lines", [])
        charges_data = validated_data.pop("inbound_charges", [])

        inbound = WHInbound.objects.create(**validated_data)

        if lines_data:
            WHInboundLine.objects.bulk_create([
                WHInboundLine(inbound=inbound, **line_data)
                for line_data in lines_data
            ])

        if charges_data:
            WHInboundCharge.objects.bulk_create([
                WHInboundCharge(inbound=inbound, **charge_data)
                for charge_data in charges_data
            ])

        return inbound

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop("inbound_lines", [])
        charges_data = validated_data.pop("inbound_charges", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        self._sync_inbound_lines(instance, lines_data)
        self._sync_inbound_charges(instance, charges_data)

        return instance

    def _sync_inbound_lines(self, inbound, lines_data):
        existing_by_uf = {
            obj.uf: obj
            for obj in inbound.inbound_lines.all()
        }

        incoming_ufs = set()
        to_create = []

        for line_data in lines_data:
            line_data = dict(line_data)
            line_uf = line_data.pop("uf", None)

            if line_uf and line_uf in existing_by_uf:
                obj = existing_by_uf[line_uf]
                incoming_ufs.add(line_uf)

                for attr, value in line_data.items():
                    setattr(obj, attr, value)

                obj.save()
            else:
                to_create.append(WHInboundLine(inbound=inbound, **line_data))

        if to_create:
            WHInboundLine.objects.bulk_create(to_create)

        ufs_to_delete = set(existing_by_uf.keys()) - incoming_ufs
        if ufs_to_delete:
            inbound.inbound_lines.filter(uf__in=ufs_to_delete).delete()

    def _sync_inbound_charges(self, inbound, charges_data):
        existing_by_uf = {
            obj.uf: obj
            for obj in inbound.inbound_charges.all()
        }

        incoming_ufs = set()
        to_create = []

        for charge_data in charges_data:
            charge_data = dict(charge_data)
            charge_uf = charge_data.pop("uf", None)

            if charge_uf and charge_uf in existing_by_uf:
                obj = existing_by_uf[charge_uf]
                incoming_ufs.add(charge_uf)

                for attr, value in charge_data.items():
                    setattr(obj, attr, value)

                obj.save()
            else:
                to_create.append(WHInboundCharge(inbound=inbound, **charge_data))

        if to_create:
            WHInboundCharge.objects.bulk_create(to_create)

        ufs_to_delete = set(existing_by_uf.keys()) - incoming_ufs
        if ufs_to_delete:
            inbound.inbound_charges.filter(uf__in=ufs_to_delete).delete()
    
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
    

class WHInboundChargeOptionSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    charge_type = serializers.CharField()
    unit_type = serializers.CharField()
    default_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    default_unit_price = serializers.DecimalField(max_digits=12, decimal_places=4)
    fee_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    handling_unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)

