from django.db import transaction
from rest_framework import serializers

from abb.utils import get_user_company
from att.models import Contact
from logistic.models import WHLocation, WHOutbound, WHOutboundLine, WHProduct
from logistic.serializers.wms_inbound import WHOwnerSerializer


class WHOutboundLineSerializer(serializers.ModelSerializer):

    uf = serializers.CharField(required=False)

    product = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=WHProduct.objects.all()
    )

    location = serializers.SlugRelatedField(
        slug_field="uf",
        queryset=WHLocation.objects.all()
    )

    class Meta:
        model = WHOutboundLine
        fields = [
            "uf",
            "product",
            "location",
            "quantity",
            "pallets",
            "area_m2",
            "volume_m3",
        ]
        extra_kwargs = {
            "uf": {"validators": []}
        }


class WHOutboundDetailSerializer(serializers.ModelSerializer):

    owner = serializers.SlugRelatedField(
        queryset=Contact.objects.all(),
        slug_field="uf"
    )

    owner_info = WHOwnerSerializer(source="owner", read_only=True)

    outbound_lines = WHOutboundLineSerializer(many=True)

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
        ]

        read_only_fields = [
            "shipped_at",
            "created_at",
        ]

 


    def create(self, validated_data):

        request = self.context["request"]
        company = get_user_company(request.user)

        lines = validated_data.pop("outbound_lines", [])

        outbound = WHOutbound.objects.create(
                company=company,
                **validated_data
            )

        for line in lines:
            WHOutboundLine.objects.create(
                outbound=outbound,
                **line
            )

        return outbound


    @transaction.atomic
    def update(self, instance, validated_data):

        if instance.status == WHOutbound.Status.SHIPPED:
            raise serializers.ValidationError("Shipped outbound cannot be modified.")

        lines_data = validated_data.pop("outbound_lines", [])

        print('7418', lines_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        existing_lines = {line.uf: line for line in instance.outbound_lines.all()}
        incoming_ufs = set()

        for line_data in lines_data:
            uf = line_data.get("uf")

            if uf and uf in existing_lines:
                # update existing line
                line = existing_lines[uf]
                for attr, value in line_data.items():
                    setattr(line, attr, value)
                line.save()

                incoming_ufs.add(uf)

            else:
                # create new line
                new_line = WHOutboundLine.objects.create(
                    outbound=instance,
                    **line_data
                )
                incoming_ufs.add(new_line.uf)

        # delete removed lines
        for uf, line in existing_lines.items():
            if uf not in incoming_ufs:
                line.delete()

        return instance


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