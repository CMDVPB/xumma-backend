from rest_framework import serializers
from .models import ImportBatch, ImportRow


class ImportCreateSerializer(serializers.Serializer):
    supplier_uf = serializers.CharField()
    period_from = serializers.DateField()
    period_to = serializers.DateField()

    def validate(self, data):
        if data["period_from"] > data["period_to"]:
            raise serializers.ValidationError("Invalid period range")
        return data


class ImportBatchListSerializer(serializers.ModelSerializer):
    supplier_company_name = serializers.CharField(
        source="supplier.company_name", read_only=True)

    class Meta:
        model = ImportBatch
        fields = (
            "supplier_company_name",
            'year',
            'sequence',
            "period_from",
            "period_to",
            "status",
            "created_at",
            "finished_at",
            "totals",
            "uf",
        )


class ImportRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRow
        fields = (
            "row_number",
            "status",
            "error_message",
            "matched_trip_id",
            "raw_data",
        )


class ImportBatchDetailSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source="supplier.company_name", read_only=True)
    rows = ImportRowSerializer(many=True, read_only=True)

    class Meta:
        model = ImportBatch
        fields = "__all__"
