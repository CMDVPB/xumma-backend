from rest_framework import serializers


class WHTariffHandlingTierSerializer(serializers.Serializer):
    fee_type = serializers.CharField()
    unit = serializers.CharField()
    min_quantity = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    max_quantity = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=4)
    order = serializers.IntegerField()


class WHTariffSerializer(serializers.Serializer):

    contact = serializers.CharField()
    contact_name = serializers.CharField()

    period_start = serializers.DateField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)
    is_active = serializers.BooleanField()

    storage_mode = serializers.ChoiceField(choices=["pallet", "unit", "m2", "m3",])

    storage_per_euro_pallet_per_day = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    storage_per_iso2_pallet_per_day = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    storage_per_block_pallet_per_day = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)

    storage_per_m2_per_day = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    storage_per_m3_per_day = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)    
    storage_per_unit_per_day = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)

    storage_min_days = serializers.IntegerField(required=False, default=1)
    # inbound_per_line = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    # outbound_per_order = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    # outbound_per_line = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)

    handling_tier_mode = serializers.CharField(required=False, allow_null=True)
    handling_tiers = WHTariffHandlingTierSerializer(many=True, required=False)

    is_override = serializers.BooleanField()

