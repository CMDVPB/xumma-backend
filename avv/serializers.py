from django.contrib.auth import get_user_model
from abb.utils import get_user_company
from att.models import Vehicle
from .models import Part, Warehouse, Location
from decimal import Decimal
from rest_framework import serializers

from .models import (
    Part, Location, StockBalance,
    PartRequest, PartRequestLine,
    IssueDocument, IssueLine, StockMovement, Warehouse
)

User = get_user_model()


class PartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Part
        fields = [
            "id", "sku", "name", "uom", "barcode",
            "min_level", "reorder_level", "reorder_qty", "uf"
        ]
        read_only_fields = ["id", "is_active", "uf"]


class PartStockSerializer(serializers.ModelSerializer):
    stock = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        read_only=True
    )
    unit = serializers.CharField(source="uom")
    min_stock = serializers.DecimalField(
        source="min_level",
        max_digits=14,
        decimal_places=3,
    )

    class Meta:
        model = Part
        fields = [
            "id",
            "sku",
            "name",
            "unit",
            "stock",
            "min_stock",
        ]


class LocationSerializer(serializers.ModelSerializer):
    warehouse = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = ["id", "code", "name", "warehouse"]

    def get_warehouse(self, obj):
        return {
            "id": obj.warehouse_id,
            "code": obj.warehouse.code,
            "name": obj.warehouse.name,
        }


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


class PartRequestLineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartRequestLine
        fields = ["part", "qty_requested"]


class PartRequestCreateSerializer(serializers.ModelSerializer):
    mechanic = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    driver = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    vehicle = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.all(), write_only=True)

    lines = PartRequestLineWriteSerializer(many=True, write_only=True)

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
            "uf",
        ]

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        company = get_user_company(user)
        lines_data = validated_data.pop("lines")
        req = PartRequest.objects.create(
            company=company,
            created_by=user,
            status=PartRequest.Status.SUBMITTED,
            **validated_data,
        )

        PartRequestLine.objects.bulk_create(
            [
                PartRequestLine(
                    request=req,
                    company=company,
                    created_by=user,
                    **line,
                )
                for line in lines_data
            ]
        )

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


class PartRequestLineCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartRequestLine
        fields = ["part", "qty_requested"]


class PartRequestSerializer(serializers.ModelSerializer):
    mechanic = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    driver = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    vehicle = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.all(), write_only=True)

    lines = PartRequestLineCreateSerializer(many=True, write_only=True)

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
            "lines",
            "uf",
        ]

    def create(self, validated_data):
        request_user = self.context["request"].user
        company = get_user_company(request_user)

        lines_data = validated_data.pop("lines", [])

        request = PartRequest.objects.create(company=company,
                                             created_by=request_user,
                                             **validated_data)

        PartRequestLine.objects.bulk_create(
            [
                PartRequestLine(
                    company=company,
                    created_by=request_user,
                    request=request,
                    part=line["part"],
                    qty_requested=line["qty_requested"],
                )
                for line in lines_data
            ]
        )

        return request


class PartRequestListSerializer(serializers.ModelSerializer):
    lines = PartRequestLineSerializer(
        many=True,
        source="request_part_request_lines",
        read_only=True,
    )

    vehicle_reg_number = serializers.SerializerMethodField()
    mechanic_name = serializers.SerializerMethodField()
    driver_name = serializers.SerializerMethodField()

    class Meta:
        model = PartRequest
        fields = (
            "id",
            "status",
            "vehicle_reg_number",
            "mechanic_name",
            "driver_name",
            "needed_at",
            "note",
            "created_at",
            "lines",
            "uf",
        )
        read_only_fields = ("status", "created_at")

    # -------------------------
    # Computed fields
    # -------------------------

    def get_vehicle_reg_number(self, obj):
        return obj.vehicle.reg_number if obj.vehicle else None

    def get_mechanic_name(self, obj):
        return obj.mechanic.get_full_name() if obj.mechanic else None

    def get_driver_name(self, obj):
        return obj.driver.get_full_name() if obj.driver else None

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


class StockReceiveSerializer(serializers.Serializer):
    part = serializers.PrimaryKeyRelatedField(
        queryset=Part.objects.all()
    )
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all()
    )
    location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all()
    )
    qty = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0.001")
    )
    unit_cost = serializers.DecimalField(
        max_digits=14, decimal_places=4, required=False, default=Decimal("0")
    )
    currency = serializers.CharField(max_length=8, default="EUR")
    supplier_name = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    received_at = serializers.DateTimeField(required=False)

    def validate(self, data):
        location = data["location"]
        warehouse = data["warehouse"]

        if location.warehouse_id != warehouse.id:
            raise serializers.ValidationError(
                "Location does not belong to selected warehouse."
            )

        return data


class StockMovementSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source="part.name", read_only=True)
    part_sku = serializers.CharField(source="part.sku", read_only=True)

    from_warehouse = serializers.SerializerMethodField()
    to_warehouse = serializers.SerializerMethodField()

    from_location_code = serializers.CharField(
        source="from_location.code", read_only=True
    )
    to_location_code = serializers.CharField(
        source="to_location.code", read_only=True
    )

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "type",
            "qty",
            "currency",
            "unit_cost_snapshot",
            "created_at",

            # part
            "part",
            "part_name",
            "part_sku",

            # locations
            "from_location",
            "from_location_code",
            "from_warehouse",

            "to_location",
            "to_location_code",
            "to_warehouse",

            # reference
            "ref_type",
            "ref_id",
        )

    def get_from_warehouse(self, obj):
        if obj.from_location:
            return obj.from_location.warehouse.name
        return None

    def get_to_warehouse(self, obj):
        if obj.to_location:
            return obj.to_location.warehouse.name
        return None


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "name",
            "uf",
        ]
