from __future__ import annotations

import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError

from abb.models import Currency
from abb.utils import hex_uuid, image_upload_path
from app.models import Company
from att.models import Contact, Vehicle

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

    class ServiceType(models.TextChoices):
        INTERNAL = "INTERNAL", "Internal service"
        THIRD_PARTY = "THIRD_PARTY", "Third-party workshop"

    class Status(models.TextChoices):
        DRAFT = "DRAFT"
        IN_PROGRESS = "IN_PROGRESS"
        ON_HOLD = "ON_HOLD"
        COMPLETED = "COMPLETED"
        CANCELLED = "CANCELLED"

    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        default=ServiceType.INTERNAL,
    )

    third_party = models.ForeignKey(
        Contact, on_delete=models.PROTECT, null=True, blank=True, related_name="third_party_work_orders"
    )

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="vehicle_work_orders")
    mechanic = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="mechaic_work_orders"
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
    signed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="signed_work_orders",
    )
    signed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def work_cost(self):
        return (
            self.work_lines.annotate(
                line_cost=ExpressionWrapper(
                    F("qty") * Coalesce(F("unit_price"), 0),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
            .aggregate(total=Sum("line_cost"))
            .get("total")
            or 0
        )

    @property
    def labor_cost(self):
        return (
            self.work_order_labor_entries.annotate(
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
            self.work_order_issues
            .filter(unit_cost__gt=0)  # ✅ ignore missing/zero costs
            .aggregate(
                total=Sum(
                    F("qty") * F("unit_cost"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )["total"]
            or 0
        )

    @property
    def total_cost(self):
        return self.work_cost + self.labor_cost + self.parts_cost


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


class WorkType(TimeStampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)

    default_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        null=True,
        blank=True, related_name="default_unit_work_types",
    )

    def __str__(self):
        return self.name


class WorkOrderWorkLine(TimeStampedModel):
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="work_lines",
    )

    work_type = models.ForeignKey(
        WorkType,
        on_delete=models.PROTECT,
        related_name="work_type_lines",
    )

    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name="work_line_units",
    )

    qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1,
    )

    # only used for THIRD_PARTY
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True, related_name="currency_work_types",
    )

    note = models.CharField(max_length=255, blank=True)

    def clean(self):
        wo = self.work_order

        if wo.service_type == WorkOrder.ServiceType.INTERNAL:
            if self.unit_price is not None:
                raise ValidationError("Internal work cannot have a price.")

        if wo.service_type == WorkOrder.ServiceType.THIRD_PARTY:
            if self.unit_price is None:
                raise ValidationError(
                    "Third-party work requires a unit price.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def cost(self):
        if self.unit_price:
            return self.qty * self.unit_price
        return None


class WorkOrderAttachment(TimeStampedModel):
    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="work_order_attachments"
    )

    file = models.FileField(upload_to=image_upload_path)

    file_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)

    def save(self, *args, **kwargs):
        if self.file:
            self.file_name = self.file.name
            self.content_type = getattr(self.file.file, "content_type", "")
        super().save(*args, **kwargs)


class DriverReport(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT"
        SENT = "SENT"          # driver submitted
        REVIEWED = "REVIEWED"  # manager looked at it
        IN_EXECUTION = "IN_EXECUTION"  # work order created
        REJECTED = "REJECTED"
        CLOSED = "CLOSED"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    driver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="driver_reports",
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="vehicle_reports",
    )

    related_work_order = models.ForeignKey(
        WorkOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_reports",
    )

    title = models.CharField(max_length=255)
    description = models.TextField()

    odometer = models.PositiveIntegerField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_reports",
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)


class DriverReportImage(TimeStampedModel):
    report = models.ForeignKey(
        DriverReport,
        on_delete=models.CASCADE,
        related_name="report_driver_report_images",
    )

    image = models.ImageField(upload_to=image_upload_path)
