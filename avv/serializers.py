from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db.models import Sum
from rest_framework import serializers
from django.conf import settings

from abb.utils import get_user_company
from att.models import Contact, Vehicle
from .models import (
    Part, Location, StockBalance,
    PartRequest, PartRequestLine,
    IssueDocument, IssueLine, StockMovement, Warehouse, UnitOfMeasure, WorkOrder, WorkOrderAttachment, WorkOrderIssue,
    WorkOrderLaborEntry, WorkOrderWorkLine, WorkType
)


User = get_user_model()


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ("id", "serial_number", "code", "name", "uf",
                  )


class PartSerializer(serializers.ModelSerializer):
    uom_uf = serializers.SlugRelatedField(
        allow_null=True,
        source="uom",  # important
        slug_field='uf',
        queryset=UnitOfMeasure.objects.all(),
        write_only=True
    )
    uom = UnitOfMeasureSerializer(read_only=True)

    class Meta:
        model = Part
        fields = [
            "id", "sku", "name", "uom_uf", "uom", "barcode",
            "min_level", "reorder_level", "reorder_qty", "note", "uf"
        ]
        read_only_fields = ["id", "is_active", "uf"]


class PartStockSerializer(serializers.ModelSerializer):
    stock = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        read_only=True
    )
    unit = serializers.CharField(
        source="uom.name",
        read_only=True
    )
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
            "is_active",
        ]
        read_only_fields = ["is_active"]


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
    lines = PartRequestLineReadSerializer(
        many=True,
        read_only=True,
        source="request_part_request_lines",
    )

    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number",
        read_only=True,
    )

    mechanic_name = serializers.CharField(
        source="mechanic.get_full_name",
        read_only=True,
    )

    driver_name = serializers.CharField(
        source="driver.get_full_name",
        read_only=True,
    )

    issue_document_id = serializers.SerializerMethodField()

    class Meta:
        model = PartRequest
        fields = [
            "id",
            "status",
            "vehicle",
            "vehicle_reg_number",
            "mechanic",
            "mechanic_name",
            "driver",
            "driver_name",
            "needed_at",
            "note",
            "created_at",
            "lines",
            "issue_document_id",
            "uf",
        ]

    def get_issue_document_id(self, obj):
        doc = obj.request_issue_documents.first()
        return doc.id if doc else None


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

    # ------- Computed fields -------

    def get_vehicle_reg_number(self, obj):
        return obj.vehicle.reg_number if obj.vehicle else None

    def get_mechanic_name(self, obj):
        return obj.mechanic.get_full_name() if obj.mechanic else None

    def get_driver_name(self, obj):
        return obj.driver.get_full_name() if obj.driver else None


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

    from_location = serializers.SerializerMethodField()
    to_location = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "type",
            "qty",
            "part_name",
            "part_sku",
            "from_location",
            "to_location",
            "created_at",
        ]

    def _loc(self, loc):
        if not loc:
            return None
        return {
            "id": loc.id,
            "code": loc.code,
            "warehouse": loc.warehouse.name,
        }

    def get_from_location(self, obj):
        return self._loc(obj.from_location)

    def get_to_location(self, obj):
        return self._loc(obj.to_location)


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "name",
            "uf",
        ]


class IssueDocumentListSerializer(serializers.ModelSerializer):
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
        return (
            obj.doc_issue_lines
            .aggregate(total=Sum("qty"))
            .get("total") or 0
        )


class IssueLineSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source="part.name", read_only=True)
    part_sku = serializers.CharField(source="part.sku", read_only=True)
    location_name = serializers.CharField(
        source="from_location.name", read_only=True
    )
    warehouse_name = serializers.CharField(
        source="from_location.warehouse.name", read_only=True
    )

    class Meta:
        model = IssueLine
        fields = [
            "id",
            "part",
            "part_name",
            "part_sku",
            "lot",
            "warehouse_name",
            "location_name",
            "qty",
        ]


class IssueDocumentDetailSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(
        source="mechanic.get_full_name", read_only=True
    )
    mechanic_uf = serializers.CharField(
        source="mechanic.uf", read_only=True
    )
    driver_name = serializers.CharField(
        source="driver.get_full_name", read_only=True
    )
    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number", read_only=True
    )

    # request_status = serializers.CharField(
    #     source="request.status", read_only=True
    # )

    lines = IssueLineSerializer(
        source="doc_issue_lines",
        many=True,
        read_only=True,
    )

    confirmed_at = serializers.DateTimeField(read_only=True)
    confirmed_by_name = serializers.CharField(
        source="confirmed_by.get_full_name",
        read_only=True,
    )

    class Meta:
        model = IssueDocument
        fields = [
            "id",
            "uf",
            "created_at",
            "note",
            "mechanic_name",
            "mechanic_uf",
            "driver_name",
            "vehicle_reg_number",
            "status",
            "lines",
            "confirmed_at",
            "confirmed_by_name",
            "uf",
        ]


class WorkOrderCreateSerializer(serializers.ModelSerializer):
    mechanic = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    driver = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=User.objects.all(), write_only=True)
    vehicle = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Vehicle.objects.all(), write_only=True)
    third_party = serializers.SlugRelatedField(
        allow_null=True, slug_field='uf', queryset=Contact.objects.all(), write_only=True)

    class Meta:
        model = WorkOrder
        fields = [
            "vehicle",
            "third_party",
            "mechanic",
            "driver",
            "scheduled_at",
            "problem_description",
            "service_type",
        ]


class WorkOrderListSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(
        source="mechanic.get_full_name", read_only=True
    )
    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number", read_only=True
    )
    third_party_name = serializers.CharField(
        source="third_party.company_name", read_only=True
    )

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "service_type",
            "status",
            "vehicle_reg_number",
            "mechanic_name",
            "third_party_name",
            "created_at",
            "uf",
        ]


class WorkOrderLaborEntrySerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(
        source="mechanic.get_full_name",
        read_only=True,
    )

    cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = WorkOrderLaborEntry
        fields = [
            "id",
            "mechanic",
            "mechanic_name",
            "description",
            "hours",
            "hourly_rate",
            "cost",
            "created_at",
            "uf",
        ]
        read_only_fields = [
            "id",
            "mechanic",
            "mechanic_name",
            "cost",
            "created_at",
            "uf",
        ]


class WorkOrderWorkLineSerializer(serializers.ModelSerializer):
    work_type_name = serializers.CharField(
        source="work_type.name",
        read_only=True,
    )
    unit_name = serializers.CharField(
        source="unit.name",
        read_only=True,
    )

    class Meta:
        model = WorkOrderWorkLine
        fields = [
            "id",
            "work_type",
            "work_type_name",
            "unit",
            "unit_name",
            "qty",
            "unit_price",
            "currency",
            "note",
            "uf",
        ]


class WorkOrderAttachmentReadSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderAttachment
        fields = ["id", "uf", "file_url", "content_type"]

    def get_file_url(self, obj):
        return f"{settings.BACKEND_URL}/api/work-order-files/{obj.uf}/"


class WorkOrderDetailSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(
        source="mechanic.get_full_name", read_only=True
    )
    mechanic_uf = serializers.CharField(
        source="mechanic.uf", read_only=True
    )
    vehicle_reg_number = serializers.CharField(
        source="vehicle.reg_number", read_only=True
    )
    third_party_name = serializers.CharField(
        source="third_party.company_name", read_only=True
    )
    work_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    labor_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    parts_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    total_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    work_lines = WorkOrderWorkLineSerializer(many=True, read_only=True)
    work_order_attachments = WorkOrderAttachmentReadSerializer(
        many=True, read_only=True)

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "service_type",
            "status",
            "vehicle",
            "vehicle_reg_number",
            "mechanic_name",
            "mechanic_uf",
            "driver",
            "third_party_name",
            "problem_description",
            "created_at",
            "work_cost",
            "parts_cost",
            "labor_cost",
            "total_cost",
            "uf",

            "work_lines",
            "work_order_attachments",
        ]


class WorkOrderIssueSerializer(serializers.ModelSerializer):
    part_name = serializers.CharField(source="part.name", read_only=True)
    location_name = serializers.CharField(
        source="location.name", read_only=True)

    class Meta:
        model = WorkOrderIssue
        fields = [
            "id",
            "part_name",
            "location_name",
            "qty",
            "created_at",
            "uf",
        ]


class LocationByPartSerializer(serializers.Serializer):
    balance_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    location_name = serializers.CharField()
    lot_id = serializers.IntegerField(allow_null=True)
    lot_code = serializers.CharField(allow_null=True)
    qty_on_hand = serializers.DecimalField(max_digits=12, decimal_places=3)
    qty_reserved = serializers.DecimalField(max_digits=12, decimal_places=3)
    qty_available = serializers.DecimalField(max_digits=12, decimal_places=3)


class WorkOrderStartSerializer(serializers.Serializer):
    pass


class LocationByPartSerializer(serializers.Serializer):
    location_id = serializers.IntegerField()
    location_name = serializers.CharField()
    qty_on_hand = serializers.DecimalField(max_digits=12, decimal_places=3)
    qty_available = serializers.DecimalField(max_digits=12, decimal_places=3)


class WorkTypeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkType
        fields = ["id", "code", "name", "default_unit"]

    def validate_code(self, value):
        if WorkType.objects.filter(code=value).exists():
            raise serializers.ValidationError("Work type code already exists")
        return value


class WorkTypeSerializer(serializers.ModelSerializer):
    default_unit = UnitOfMeasureSerializer(read_only=True)
    default_unit_code = serializers.CharField(
        source="default_unit.code",
        read_only=True,
    )

    class Meta:
        model = WorkType
        fields = [
            "id",
            "code",
            "name",
            "default_unit",
            "default_unit_code",
            "uf",
        ]


class WorkOrderWorkLineCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = WorkOrderWorkLine
        fields = [
            "work_type",
            "unit",
            "qty",
            "unit_price",
            "currency",
            "note",

        ]

    def validate(self, data):
        wo = self.context["work_order"]

        if wo.service_type == WorkOrder.ServiceType.INTERNAL:
            data["unit_price"] = None
            data["currency"] = None

        return data


class WorkOrderWorkLineSerializer(serializers.ModelSerializer):
    cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    unit_name = serializers.CharField(
        source="unit.name",
        read_only=True,
    )

    class Meta:
        model = WorkOrderWorkLine
        fields = [
            "id",
            "work_type",
            "unit",
            "qty",
            "unit_price",
            "cost",
            "note",
            "created_at",
            'unit_name',
            "uf",
        ]

    def validate(self, data):
        work_order = self.context["work_order"]

        if work_order.service_type == WorkOrder.ServiceType.INTERNAL:
            data["unit_price"] = None

        if work_order.service_type == WorkOrder.ServiceType.THIRD_PARTY:
            if data.get("unit_price") is None:
                raise serializers.ValidationError({
                    "unit_price": "Unit price is required for third-party work"
                })

        return data


class WorkOrderPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkOrder
        fields = "__all__"
        read_only_fields = [
            "status",
            "created_at",
            "mechanic_signed_at",
            "completed_at",
        ]


class WorkOrderAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderAttachment
        fields = ["id", "uf", "file", "file_url", "file_name", "content_type"]

    def get_file_url(self, obj):
        return f"{settings.BACKEND_URL}/api/work-order-files/{obj.uf}/"
