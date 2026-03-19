from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHLocation, WHOutbound, WHOutboundCharge, WHOutboundLine, WHProduct
from logistic.serializers.wms_inbound import WHOwnerSerializer



class WHOutboundChargeOptionSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    charge_type = serializers.CharField()
    unit_type = serializers.CharField()
    default_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    default_unit_price = serializers.DecimalField(max_digits=12, decimal_places=4)
    fee_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    handling_unit = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class WHOutboundLineSerializer(serializers.ModelSerializer):
    uf = serializers.CharField(required=False)

    product = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=WHProduct.objects.all()
    )

    location = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=WHLocation.objects.all(),
        allow_null=True,
        required=False,
    )


    class Meta:
        model = WHOutboundLine
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


class WHOutboundChargeSerializer(serializers.ModelSerializer):
    uf = serializers.CharField(required=False)

    class Meta:
        model = WHOutboundCharge
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


class WHOutboundDetailSerializer(serializers.ModelSerializer):

    owner = serializers.SlugRelatedField(
        queryset=Contact.objects.all(),
        slug_field="uf"
    )

    owner_info = WHOwnerSerializer(source="owner", read_only=True)

    outbound_lines = WHOutboundLineSerializer(many=True)
    outbound_charges = WHOutboundChargeSerializer(many=True, required=False)
    
    total_pallets = serializers.SerializerMethodField()
    total_m2 = serializers.SerializerMethodField()
    total_m3 = serializers.SerializerMethodField()
    total_units = serializers.SerializerMethodField()

    class Meta:
        model = WHOutbound
        fields = [
            "uf",
            "owner",
            "owner_info",
            "reference",
            "status",
            "planned_pickup_at",
            "shipped_at",
            "created_at",

            "outbound_lines",
            "outbound_charges",

            "total_pallets",
            "total_m2",
            "total_m3",
            "total_units",

        ]

        read_only_fields = [
            "shipped_at",
            "created_at",
        ]


    def create(self, validated_data):
        request = self.context["request"]
        company = get_user_company(request.user)

        lines_data = validated_data.pop("outbound_lines", [])
        charges_data = validated_data.pop("outbound_charges", [])

        outbound = WHOutbound.objects.create(
            company=company,
            **validated_data
        )

        if lines_data:
            WHOutboundLine.objects.bulk_create([
                WHOutboundLine(outbound=outbound, **line_data)
                for line_data in lines_data
            ])

        if charges_data:
            WHOutboundCharge.objects.bulk_create([
                WHOutboundCharge(outbound=outbound, **charge_data)
                for charge_data in charges_data
            ])

        return outbound

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.status == WHOutbound.Status.SHIPPED:
            raise serializers.ValidationError("Shipped outbound cannot be modified.")

        lines_data = validated_data.pop("outbound_lines", [])
        charges_data = validated_data.pop("outbound_charges", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        self._sync_outbound_lines(instance, lines_data)
        self._sync_outbound_charges(instance, charges_data)

        return instance

    def _sync_outbound_lines(self, outbound, lines_data):
        existing_by_uf = {
            obj.uf: obj
            for obj in outbound.outbound_lines.all()
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
                to_create.append(WHOutboundLine(outbound=outbound, **line_data))

        if to_create:
            WHOutboundLine.objects.bulk_create(to_create)

        ufs_to_delete = set(existing_by_uf.keys()) - incoming_ufs
        if ufs_to_delete:
            outbound.outbound_lines.filter(uf__in=ufs_to_delete).delete()

    def _sync_outbound_charges(self, outbound, charges_data):
        existing_by_uf = {
            obj.uf: obj
            for obj in outbound.outbound_charges.all()
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
                to_create.append(WHOutboundCharge(outbound=outbound, **charge_data))

        if to_create:
            WHOutboundCharge.objects.bulk_create(to_create)

        ufs_to_delete = set(existing_by_uf.keys()) - incoming_ufs
        if ufs_to_delete:
            outbound.outbound_charges.filter(uf__in=ufs_to_delete).delete()

    def get_total_pallets(self, obj):
        return obj.outbound_lines.aggregate(v=Sum("pallets"))["v"] or 0

    def get_total_m2(self, obj):
        return obj.outbound_lines.aggregate(v=Sum("area_m2"))["v"] or 0

    def get_total_m3(self, obj):
        return obj.outbound_lines.aggregate(v=Sum("volume_m3"))["v"] or 0

    def get_total_units(self, obj):
        return obj.outbound_lines.aggregate(v=Sum("quantity"))["v"] or 0
    
    
class WHOutboundListSerializer(serializers.ModelSerializer):    

    owner_name = serializers.CharField(
        source="owner.company_name",
        read_only=True
    )

    total_primary = serializers.DecimalField(
        max_digits=18,
        decimal_places=3,
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

            # annotated
            "total_primary",
           
        ]


