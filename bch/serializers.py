from rest_framework import serializers

from azz.models import FuelTank


class FuelTankWSSerializer(serializers.ModelSerializer):
    current_stock_l = serializers.SerializerMethodField()

    class Meta:
        model = FuelTank
        fields = (
            "uf",
            "fuel_type",
            "capacity_l",
            "current_stock_l",
        )

    def get_current_stock_l(self, obj):
        return str(obj.get_current_fuel_stock())  # ✅ str, not Decimal

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Convert DecimalFields explicitly
        data["capacity_l"] = str(data["capacity_l"])

        return data
