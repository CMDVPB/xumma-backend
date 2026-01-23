from __future__ import annotations

import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

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


class Part(TimeStampedModel):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=240)
    uom = models.CharField(max_length=24, default="pcs")
    barcode = models.CharField(max_length=64, blank=True, default="")
    min_level = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))
    reorder_level = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))
    reorder_qty = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"))

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"


class StockLot(TimeStampedModel):
    part = models.ForeignKey(
        Part, on_delete=models.PROTECT, related_name="part_stock_lots")
    supplier_name = models.CharField(max_length=120, blank=True, default="")
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal("0"))
    currency = models.CharField(max_length=8, default="EUR")
    received_at = models.DateTimeField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"LOT#{self.id} {self.part.sku}"


class StockBalance(TimeStampedModel):
    """
    Fast read model; source of truth remains StockMovement ledger.
    We lock rows here for reserve/issue.
    """
    part = models.ForeignKey(Part, on_delete=models.PROTECT)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT)

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
    request = models.ForeignKey(
        PartRequest, on_delete=models.PROTECT, related_name="request_issue_documents")
    mechanic = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="mecanic_issue_documents")
    vehicle = models.ForeignKey(
        Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicle_issue_documents")
    driver = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="driver_issue_documents")
    note = models.TextField(blank=True, default="")


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
    currency = models.CharField(max_length=8, default="EUR")

    # generic reference (request / issue / receipt / count)
    ref_type = models.CharField(max_length=40, blank=True, default="")
    ref_id = models.CharField(max_length=40, blank=True, default="")
