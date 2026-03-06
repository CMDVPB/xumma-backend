from rest_framework import serializers


class WHTariffSerializer(serializers.Serializer):

    contact = serializers.CharField()
    contact_name = serializers.CharField()

    storage_mode = serializers.ChoiceField(
        choices=[
            "pallet",
            "unit",
            "m2",
            "volume",
        ]
    )

    storage_per_pallet_per_day = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        required=False,
        allow_null=True
    )

    storage_per_unit_per_day = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        required=False,
        allow_null=True
    )

    storage_per_m2_per_day = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        required=False,
        allow_null=True
    )

    storage_per_m3_per_day = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        required=False,
        allow_null=True
    )

    storage_min_days = serializers.IntegerField(
        required=False,
        default=1
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