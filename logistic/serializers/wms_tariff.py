from rest_framework import serializers


class WHTariffSerializer(serializers.Serializer):

    contact = serializers.CharField()
    contact_name = serializers.CharField()

    storage_per_unit_per_day = serializers.DecimalField(
        max_digits=12,
        decimal_places=4
    )

    inbound_per_line = serializers.DecimalField(
        max_digits=12,
        decimal_places=4
    )

    outbound_per_order = serializers.DecimalField(
        max_digits=12,
        decimal_places=4
    )

    outbound_per_line = serializers.DecimalField(
        max_digits=12,
        decimal_places=4
    )

    is_override = serializers.BooleanField()