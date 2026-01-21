from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models import Max

from abb.utils import hex_uuid
from app.models import Company
from att.models import Contact

User = get_user_model()


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
