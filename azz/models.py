from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Max
from django.core.validators import MinValueValidator
from django.db.models import Sum
from django.core.exceptions import ValidationError
from decimal import Decimal

from abb.utils import hex_uuid
from app.models import Company
from att.models import Contact, Person, Vehicle
from ayy.models import ItemCost

User = get_user_model()

###### START SUPPLIERS (ROMPETROL, HUGO, EUROWAG, ETC) ######


class SupplierFormat(models.Model):
    """
    Defines how a supplier file is structured.
    One supplier = one active format (can be versioned later).
    """
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_supplier_formats"
    )

    supplier = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="supplier_supplier_formats"
    )

    # Example mapping:
    # {
    #   "truck_number": "Vehicle",
    #   "cost_type": "Charge",
    #   "amount": "Amount",
    #   "currency": "Currency",
    #   "date_from": "From",
    #   "date_to": "To"
    # }
    column_mapping = models.JSONField(null=True, blank=True)

    currency = models.CharField(default='MDL')
    country = models.CharField(default='MD')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "supplier"],
                condition=models.Q(is_active=True),
                name="one_active_supplier_format_per_company",
            )
        ]

    def __str__(self):
        return f"{self.supplier.company_name}"


class ImportBatch(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_DONE, "Done"),
        (STATUS_FAILED, "Failed"),
    ]

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_import_batches"
    )
    year = models.PositiveIntegerField(blank=True, null=True, editable=False)
    sequence = models.PositiveIntegerField(null=True, blank=True, unique=True)

    supplier = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="supplier_import_batches"
    )

    period_from = models.DateField()
    period_to = models.DateField()

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    totals = models.JSONField(default=dict)  # rows_total, imported, skipped

    class Meta:
        indexes = [
            models.Index(fields=["company", "supplier"]),
            models.Index(fields=["company", "period_from", "period_to"]),
            models.Index(fields=["status"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk is None and self.sequence is None:
            with transaction.atomic():
                current_year = timezone.now().year
                self.year = current_year

                last_seq = (
                    ImportBatch.objects
                    .filter(company=self.company, year=current_year)
                    .aggregate(max_seq=Max("sequence"))
                    .get("max_seq") or 0
                )
                self.sequence = last_seq + 1

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.supplier} ({self.period_from} → {self.period_to})"


class ImportRow(models.Model):
    STATUS_IMPORTED = "imported"
    STATUS_SKIPPED = "skipped"
    STATUS_ERROR = "error"
    STATUS_MATCHED = "matched"
    STATUS_UNMATCHED = "unmatched"

    batch = models.ForeignKey(
        ImportBatch,  on_delete=models.CASCADE, related_name="rows")

    source_file = models.CharField(max_length=255)
    row_number = models.PositiveIntegerField()

    supplier_row_id = models.CharField(
        max_length=100,
        db_index=True,
        null=True,
        blank=True
    )

    raw_data = models.JSONField()

    status = models.CharField(max_length=20)

    error_message = models.TextField(blank=True)

    matched_trip_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["batch", "status"]),
        ]

###### END SUPPLIERS (ROMPETROL, HUGO, EUROWAG, ETC) ######

###### START FUEL & ADBLUE ######


class FuelTank(models.Model):
    FUEL_DIESEL = "diesel"
    FUEL_ADBLUE = "adblue"

    FUEL_TYPE_CHOICES = (
        (FUEL_DIESEL, "Diesel"),
        (FUEL_ADBLUE, "AdBlue"),
    )

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_fuel_tanks"
    )

    fuel_type = models.CharField(
        max_length=10,
        choices=FUEL_TYPE_CHOICES
    )

    capacity_l = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        unique_together = ("company", "fuel_type")

    def get_current_fuel_stock(self, *, using_actual=True):
        refill_field = "actual_quantity_l" if using_actual else "quantity_l"

        refilled = self.tank_refills.aggregate(
            total=Sum(refill_field)
        )["total"] or Decimal("0")

        fueled = self.tank_truck_fuelings.aggregate(
            total=Sum("quantity_l")
        )["total"] or Decimal("0")

        return refilled - fueled


class TankRefill(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    tank = models.ForeignKey(
        FuelTank, on_delete=models.CASCADE, related_name="tank_refills")

    supplier = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, blank=True, null=True, related_name='supplier_tank_refills')
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicle_tank_refills')
    person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, blank=True, null=True, related_name='person_tank_refills')

    date = models.DateTimeField()

    quantity_l = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    actual_quantity_l = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    price_l = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(0)]
    )

    comments = models.TextField(
        max_length=100,
        blank=True
    )

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["tank", "-date"])]

    def clean(self):
        current_stock = self.tank.get_current_fuel_stock()
        if current_stock + self.actual_quantity_l > self.tank.capacity_l:
            raise ValidationError("Tank capacity exceeded")


class TruckFueling(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    tank = models.ForeignKey(
        FuelTank, on_delete=models.PROTECT, related_name="tank_truck_fuelings")

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="vehicle_truck_fuelings")

    item_cost = models.OneToOneField(
        ItemCost,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fueling_event"
    )

    driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_truck_fuelings"
    )

    quantity_l = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    fueled_at = models.DateTimeField()

    class Meta:
        ordering = ["-fueled_at"]
        indexes = [models.Index(fields=["tank", "-fueled_at"])]

    def clean(self):
        current_stock = self.tank.get_current_fuel_stock()
        if self.quantity_l > current_stock:
            raise ValidationError("Not enough fuel in tank")


###### END FUEL & ADBLUE ######


###### START WAREHOUSE & SPARE PARTS ######


###### END WAREHOUSE & SPARE PARTS ######
