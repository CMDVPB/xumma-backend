from decimal import Decimal
from django.db.models import Sum
from rest_framework import serializers

from avv.models import IssueDocument
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


class IssueDocumentWSSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(
        source="mechanic.get_full_name", read_only=True
    )
    driver_name = serializers.CharField(
        source="driver.get_full_name", read_only=True
    )
    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number", read_only=True
    )

    total_qty = serializers.SerializerMethodField()

    class Meta:
        model = IssueDocument
        fields = [
            "id",
            "uf",
            "created_at",
            "mechanic_name",
            "driver_name",
            "vehicle_reg_number",
            "total_qty",
            "status",
            "uf",
        ]

    def get_total_qty(self, obj):
        total = (
            obj.doc_issue_lines
            .aggregate(total=Sum("qty"))
            .get("total")
        )
        return str(total or Decimal("0"))
