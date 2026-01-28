from __future__ import annotations

import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, F, DecimalField, ExpressionWrapper

from abb.models import Currency
from abb.utils import hex_uuid
from app.models import Company
from att.models import Vehicle

User = get_user_model()


class TimeStampedModel(models.Model):
    uf = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="%(class)s_owned"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="%(class)s_created"
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class Warehouse(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Location(TimeStampedModel):
    """
    Bin / shelf / area inside a warehouse. Keep it flat with a coded path.
    Example code: WH1-A01-S03-B02
    """
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="warehouse_locations")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        unique_together = [("warehouse", "code")]

    def __str__(self) -> str:
        return f"{self.warehouse.code}:{self.code}"


class UnitOfMeasure(models.Model):
    uf = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, blank=True, null=True, related_name="company_units_of_measure"
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="%(class)s_created"
    )

    code = models.CharField(max_length=16, unique=True)  # pcs, kg, l, m, etc.
    name = models.CharField(max_length=64)  # Pieces, Kilograms, Liters
    serial_number = models.PositiveSmallIntegerField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["is_system", "serial_number", "code"]

    def __str__(self) -> str:
        return f"{self.code} – {self.name}"


class Part(TimeStampedModel):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=240)

    uom = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="uom_parts",
    )

    barcode = models.CharField(max_length=64, blank=True, default="")
    min_level = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))
    reorder_level = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))
    reorder_qty = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))

    note = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"


class StockLot(TimeStampedModel):
    part = models.ForeignKey(
        Part, on_delete=models.PROTECT, related_name="part_stock_lots")
    supplier_name = models.CharField(max_length=120, blank=True, default="")
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal("0"))
    currency = models.ForeignKey(Currency, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='currency_stock_lot')
    received_at = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"LOT#{self.id} {self.part.sku}"


class StockBalance(TimeStampedModel):
    """
    Fast read model; source of truth remains StockMovement ledger.
    We lock rows here for reserve/issue.
    """
    part = models.ForeignKey(
        Part, on_delete=models.PROTECT, related_name="part_stock_balances")
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="location_stock_balances")
    lot = models.ForeignKey(
        StockLot, on_delete=models.PROTECT, related_name="lot_stock_balances")

    qty_on_hand = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))
    qty_reserved = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))

    class Meta:
        unique_together = [("part", "location", "lot")]
        indexes = [
            models.Index(fields=["part", "location"]),
            models.Index(fields=["part", "lot"]),
        ]

    @property
    def qty_available(self) -> Decimal:
        return self.qty_on_hand - self.qty_reserved


class PartRequest(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT"
        SUBMITTED = "SUBMITTED"
        APPROVED = "APPROVED"
        RESERVED = "RESERVED"
        PARTIAL = "PARTIAL"
        ISSUED = "ISSUED"
        CANCELLED = "CANCELLED"
        CLOSED = "CLOSED"

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT)

    # link to your domain models; keep generic for skeleton
    mechanic = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='mecanic_part_requests')
    vehicle = models.ForeignKey(
        Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name='vehicle_part_requests')
    driver = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='driver_part_requests')

    needed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"REQ#{self.id} {self.status}"


class PartRequestLine(TimeStampedModel):
    request = models.ForeignKey(
        PartRequest, on_delete=models.CASCADE, related_name="request_part_request_lines")
    part = models.ForeignKey(
        Part, on_delete=models.PROTECT, related_name='part_part_request_lines')
    qty_requested = models.DecimalField(max_digits=14, decimal_places=3)
    qty_reserved = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))
    qty_issued = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))

    class Meta:
        unique_together = [("request", "part")]


class Reservation(TimeStampedModel):
    """
    Optional but strongly recommended: stores bin/lot allocations per request line.
    """
    line = models.ForeignKey(
        PartRequestLine, on_delete=models.CASCADE, related_name="line_reservations")
    balance = models.ForeignKey(
        StockBalance, on_delete=models.PROTECT, related_name="balance_reservations")
    qty = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        indexes = [models.Index(fields=["line"]),
                   models.Index(fields=["balance"])]


class IssueDocument(TimeStampedModel):
    class Status(models.TextChoices):
        ISSUED = "ISSUED"
        CONFIRMED = "CONFIRMED"

    request = models.ForeignKey(
        PartRequest, on_delete=models.PROTECT, related_name="request_issue_documents")
    mechanic = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="mecanic_issue_documents")
    vehicle = models.ForeignKey(
        Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicle_issue_documents")
    driver = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="driver_issue_documents")
    note = models.TextField(blank=True, default="")

    # confirmation
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_issue_documents",
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ISSUED,
    )


class IssueLine(TimeStampedModel):
    doc = models.ForeignKey(
        IssueDocument, on_delete=models.CASCADE, related_name="doc_issue_lines")
    part = models.ForeignKey(
        Part, on_delete=models.PROTECT, related_name="part_issue_lines")
    lot = models.ForeignKey(
        StockLot, on_delete=models.PROTECT, related_name="lot_issue_lines")
    from_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="from_location_issue_lines")
    qty = models.DecimalField(max_digits=14, decimal_places=3)


class StockMovement(TimeStampedModel):
    class Type(models.TextChoices):
        RECEIPT = "RECEIPT"
        TRANSFER = "TRANSFER"
        ISSUE = "ISSUE"
        RETURN = "RETURN"
        ADJUSTMENT = "ADJUSTMENT"

    type = models.CharField(max_length=16, choices=Type.choices)
    part = models.ForeignKey(
        Part, on_delete=models.PROTECT, related_name="part_stock_movements")
    lot = models.ForeignKey(
        StockLot, on_delete=models.PROTECT, related_name="lot_stock_movements")

    from_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="from_location_stock_movements")
    to_location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, related_name="to_location_stock_movements")

    qty = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost_snapshot = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal("0"))
    currency = models.ForeignKey(Currency, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='currency_stock_movements')

    # generic reference (request / issue / receipt / count)
    ref_type = models.CharField(max_length=40, blank=True, default="")
    ref_id = models.CharField(max_length=40, blank=True, default="")


class WorkOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="vehicle_work_orders")
    mechanic = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="mechaic_work_orders"
    )

    driver = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="driver_work_orders"
    )

    problem_description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )

    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    parts_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    labor_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    class Meta:
        ordering = ["-created_at"]

    @property
    def labor_cost(self):
        return (
            self.labor_entries.annotate(
                line_cost=ExpressionWrapper(
                    F("hours") * F("hourly_rate"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
            .aggregate(total=Sum("line_cost"))
            .get("total")
            or 0
        )

    @property
    def parts_cost(self):
        return (
            self.issued_parts.aggregate(total=Sum("qty" * "unit_cost"))
            .get("total")
            or 0
        )

    @property
    def total_cost(self):
        return self.labor_cost + self.parts_cost


class WorkOrderIssue(TimeStampedModel):

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="work_order_issues",
    )

    part = models.ForeignKey(
        Part,
        on_delete=models.PROTECT,
        related_name="part_work_order_issues",
    )

    lot = models.ForeignKey(
        StockLot, on_delete=models.PROTECT, blank=True, null=True, related_name="lot_work_order_issues")

    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="location_work_order_issues",
    )

    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    currency = models.ForeignKey(Currency, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='currency_work_order_issue')

    qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["work_order"]),
            models.Index(fields=["part"]),
        ]

    def __str__(self):
        return f"WO#{self.work_order_id} – {self.part} x {self.qty}"


class WorkOrderLabor(TimeStampedModel):
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="work_order_labors",
    )

    mechanic = models.ForeignKey(
        User,
        on_delete=models.PROTECT,  related_name="mechanic_order_labor_entries",
    )

    hours = models.DecimalField(max_digits=6, decimal_places=2)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total_cost(self):
        return self.hours * self.hourly_rate


class WorkOrderLaborEntry(TimeStampedModel):
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="work_order_labor_entries",
    )

    mechanic = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="mechanic_labor_entries",
    )

    description = models.CharField(max_length=255, blank=True)

    hours = models.DecimalField(max_digits=6, decimal_places=2)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def cost(self):
        return self.hours * self.hourly_rate
