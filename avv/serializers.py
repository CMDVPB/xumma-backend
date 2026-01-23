from decimal import Decimal
from rest_framework import serializers

from .models import (
    Part, Location, StockBalance,
    PartRequest, PartRequestLine,
    IssueDocument, IssueLine
)


class PartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Part
        fields = [
            "id", "sku", "name", "uom", "barcode",
            "min_level", "reorder_level", "reorder_qty",
        ]


class LocationSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(
        source="warehouse.code", read_only=True)

    class Meta:
        model = Location
        fields = ["id", "warehouse_code", "code", "name"]


class StockBalanceSerializer(serializers.ModelSerializer):
    part = PartSerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    qty_available = serializers.DecimalField(
        max_digits=14, decimal_places=3, read_only=True)

    class Meta:
        model = StockBalance
        fields = [
            "id",
            "part",
            "location",
            "qty_on_hand",
            "qty_reserved",
            "qty_available",
        ]


class PartRequestLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartRequestLine
        fields = ["part", "qty_requested"]


class PartRequestLineReadSerializer(serializers.ModelSerializer):
    part = PartSerializer(read_only=True)

    class Meta:
        model = PartRequestLine
        fields = [
            "id",
            "part",
            "qty_requested",
            "qty_reserved",
            "qty_issued",
        ]


class PartRequestCreateSerializer(serializers.ModelSerializer):
    lines = PartRequestLineWriteSerializer(many=True)

    class Meta:
        model = PartRequest
        fields = [
            "id",
            "mechanic",
            "vehicle",
            "driver",
            "needed_at",
            "note",
            "lines",
        ]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        req = PartRequest.objects.create(
            **validated_data,
            status=PartRequest.Status.SUBMITTED,
            created_by=self.context["request"].user,
        )
        for line in lines_data:
            PartRequestLine.objects.create(request=req, **line)
        return req


class PartRequestReadSerializer(serializers.ModelSerializer):
    lines = PartRequestLineReadSerializer(many=True, read_only=True)

    class Meta:
        model = PartRequest
        fields = [
            "id",
            "status",
            "mechanic",
            "vehicle",
            "driver",
            "needed_at",
            "note",
            "created_at",
            "lines",
            "uf",
        ]


class PartRequestLineSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source='part.name', read_only=True)
    part_sku = serializers.CharField(source='part.sku', read_only=True)

    class Meta:
        model = PartRequestLine
        fields = (
            'id',
            'part',
            'part_name',
            'part_sku',
            'qty_requested',
            'qty_reserved',
            'qty_issued',
            'uf',
        )
        read_only_fields = ('qty_reserved', 'qty_issued')

# Single PartRequestSerializer (LIST + CREATE + DETAIL)


class PartRequestSerializer(serializers.ModelSerializer):
    lines = PartRequestLineSerializer(many=True)

    vehicle_registration = serializers.CharField(
        source='vehicle.registration_number', read_only=True
    )
    mechanic_name = serializers.CharField(
        source='mechanic.get_full_name', read_only=True
    )
    driver_name = serializers.CharField(
        source='driver.get_full_name', read_only=True
    )

    class Meta:
        model = PartRequest
        fields = (
            'id',
            'status',
            'vehicle',
            'vehicle_registration',
            'mechanic',
            'mechanic_name',
            'driver',
            'driver_name',
            'needed_at',
            'note',
            'created_at',
            'lines',
            'uf',)
        read_only_fields = ('status', 'created_at')


###### START READ-ONLY FOR UI ######
class IssueLineSerializer(serializers.ModelSerializer):
    part_sku = serializers.CharField(source="part.sku", read_only=True)
    part_name = serializers.CharField(source="part.name", read_only=True)
    location_code = serializers.CharField(
        source="from_location.code", read_only=True)

    class Meta:
        model = IssueLine
        fields = [
            "id",
            "part_sku",
            "part_name",
            "location_code",
            "qty",
        ]


class IssueDocumentSerializer(serializers.ModelSerializer):
    lines = IssueLineSerializer(many=True, read_only=True)

    class Meta:
        model = IssueDocument
        fields = [
            "id",
            "request",
            "mechanic",
            "vehicle",
            "driver",
            "created_at",
            "lines",
        ]
###### END READ-ONLY FOR UI ######
