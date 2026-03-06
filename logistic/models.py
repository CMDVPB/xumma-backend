import logging
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth import get_user_model
from django.utils import timezone

from abb.utils import hex_uuid

logger = logging.getLogger(__name__)

User = get_user_model()


class WHStorageBillingMode(models.TextChoices):
    UNIT = "unit"
    PALLET = "pallet"
    M2 = "m2"
    VOLUME = "volume"


class WHPortalAccount(models.Model):
    """
    Login for a Contact employee (Person) to use the client portal.
    V1: local auth only (email+password hash).
    """
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_portal_accounts")
    contact = models.ForeignKey("att.Contact", on_delete=models.CASCADE, related_name="contact_portal_accounts")
    person = models.OneToOneField("att.Person", on_delete=models.CASCADE, related_name="person_portal_accounts")

    email = models.EmailField(max_length=255, db_index=True)
    password = models.CharField(max_length=128)  # store Django hashed password
    is_active = models.BooleanField(default=True)

    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint("company", Lower("email"), name="uniq_portal_company_email_ci"),
           
           
        ]
        indexes = [
            models.Index(fields=["company", "contact"]),
            models.Index(fields=["company", "is_active"]),
        ]

    def __str__(self):
        return self.email
    
    
class WHLocation(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_locations")

    code = models.CharField(max_length=40)  # A-01-01
    name = models.CharField(max_length=120, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint("company", Lower("code"), name="uniq_location_company_code_ci"),
        ]
        indexes = [
            models.Index(fields=["company", "is_active"]),
        ]

    def __str__(self):
        return self.code
    

class WHProduct(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_products")

    owner = models.ForeignKey("att.Contact", on_delete=models.CASCADE, related_name="owner_wh_products")

    sku = models.CharField(max_length=80)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    uom = models.CharField(max_length=20, default="pcs")
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    volume_m3 = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint("company", "owner", Lower("sku"), name="uniq_product_owner_sku_ci"),
            
        ]
        indexes = [
            models.Index(fields=["company", "owner"]),
            models.Index(fields=["company", "sku"]),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"
    

class WHStock(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_stocks")

    owner = models.ForeignKey("att.Contact", on_delete=models.CASCADE, null=True, blank=True, related_name="owner_wh_stocks")
    product = models.ForeignKey("WHProduct", on_delete=models.CASCADE, related_name="product_stock_rows")
    location = models.ForeignKey("WHLocation", on_delete=models.PROTECT, related_name="location_stock_rows")

    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    pallets = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    area_m2 = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    volume_m3 = models.DecimalField(max_digits=18, decimal_places=3, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                    fields=["company", "owner", "product", "location"],
                    name="uniq_stock_company_owner_product_location"
                ),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="chk_stock_non_negative"),           
           
        ]
        indexes = [
            models.Index(fields=["company", "product"]),
            models.Index(fields=["company", "location"]),
        ]

    def __str__(self):
        return f"{self.product_id}@{self.location_id}: {self.quantity}"
    

class WHStockLedger(models.Model):
    class SourceType(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"
        ADJUSTMENT = "adjustment", "Adjustment"
        TRANSFER = "transfer", "Transfer"

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_stock_ledger")

    owner = models.ForeignKey("att.Contact",  on_delete=models.CASCADE)

    product = models.ForeignKey("WHProduct", on_delete=models.CASCADE, related_name="product_ledger_rows")
    location = models.ForeignKey("WHLocation", on_delete=models.PROTECT, related_name="location_ledger_rows")

    delta_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    delta_pallets = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    delta_area_m2 = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    delta_volume_m3 = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    source_uf = models.CharField(max_length=36, db_index=True)  # inbound.uf / outbound.uf / adjustment.uf

    actor_user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="actor_user_stock_ledgers"
    )
    actor_portal = models.ForeignKey(
        "WHPortalAccount", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="actor_portal_stock_ledgers"
    )

    note = models.CharField(max_length=250, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_reversed = models.BooleanField(default=False)

    movement_direction = models.CharField(
                                max_length=10,
                                choices=[
                                    ("in", "Inbound"),
                                    ("out", "Outbound"),        
                                ],
                                blank=True,
                                null=True

                            )

    class Meta:
        constraints = [
            models.CheckConstraint(
                            condition=~(
                                Q(delta_quantity=0)
                                & Q(delta_pallets=0)
                                & Q(delta_area_m2=0)
                                & Q(delta_volume_m3=0)
                            ),
                            name="chk_ledger_nonzero_movement",
                        )
        ]
        indexes = [
            models.Index(fields=["company", "product", "created_at"]),
            models.Index(fields=["company", "source_type", "source_uf"]),
            models.Index(fields=["company", "product", "location"]),
        ]


class WHInbound(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_inbounds")

    owner = models.ForeignKey("att.Contact", on_delete=models.CASCADE, related_name="owner_wh_inbounds")

    reference = models.CharField(max_length=80, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="received_by_wh_inbounds"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_by_wh_inbounds"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
       
        indexes = [
            models.Index(fields=["company", "owner", "status"]),
            models.Index(fields=["company", "created_at"]),
        ]


class WHInboundLine(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    inbound = models.ForeignKey("WHInbound", on_delete=models.CASCADE, related_name="inbound_lines")
    product = models.ForeignKey("WHProduct", on_delete=models.PROTECT, related_name="product_inbound_lines")
    location = models.ForeignKey("WHLocation", on_delete=models.PROTECT, related_name="location_inbound_lines")
    
    quantity = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    pallets = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    area_m2 = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    volume_m3 = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)

    note = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(quantity__gt=0) |
                    Q(pallets__gt=0) |
                    Q(area_m2__gt=0) |
                    Q(volume_m3__gt=0)
                ),
                name="chk_inboundline_measurement_gt_0"
            )
        ]
        indexes = [
            models.Index(fields=["inbound"]),
            models.Index(fields=["product"]),
        ]


class WHOutbound(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        CANCELLED = "cancelled", "Cancelled"

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_outbounds")
    owner = models.ForeignKey("att.Contact", on_delete=models.CASCADE, related_name="owner_wh_outbounds")

    reference = models.CharField(max_length=80, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    created_by_user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_by_user_wh_outbounds"
    )
    created_by_portal = models.ForeignKey(
        "WHPortalAccount", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="crated_by_portal_wh_outbounds"
    )

    contact_person = models.ForeignKey(
        "att.Person", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="contact_person_wh_outbounds"
    )

    planned_pickup_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(created_by_user__isnull=False) & Q(created_by_portal__isnull=True)) |
                    (Q(created_by_user__isnull=True) & Q(created_by_portal__isnull=False)) |
                    (Q(created_by_user__isnull=True) & Q(created_by_portal__isnull=True))
                ),
                name="chk_outbound_creator_one_or_none",
            ),
           
        ]
        indexes = [
            models.Index(fields=["company", "owner", "status"]),
            models.Index(fields=["company", "created_at"]),
        ]


class WHOutboundLine(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    outbound = models.ForeignKey("WHOutbound", on_delete=models.CASCADE, related_name="outbound_lines")
    product = models.ForeignKey("WHProduct", on_delete=models.PROTECT, related_name="product_outbound_lines")
    location = models.ForeignKey("WHLocation", on_delete=models.PROTECT, null=True, blank=True)

    quantity = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    pallets = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    area_m2 = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    volume_m3 = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)

    note = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(quantity__gt=0) |
                    Q(pallets__gt=0) |
                    Q(area_m2__gt=0) |
                    Q(volume_m3__gt=0)
                ),
                name="chk_outboundline_measurement_gt_0"
            )
        ]
        indexes = [
            models.Index(fields=["outbound"]),
            models.Index(fields=["product"]),
        ]


class WHTariff(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="wms_tariffs")
    is_active = models.BooleanField(default=True)

    storage_mode = models.CharField(
        max_length=20,
        choices=WHStorageBillingMode.choices,
        default=WHStorageBillingMode.M2
    )

    storage_per_unit_per_day = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    storage_per_pallet_per_day = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    storage_per_m3_per_day = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    storage_per_m2_per_day = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    inbound_per_line = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    outbound_per_order = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    outbound_per_line = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    storage_min_days = models.PositiveIntegerField(
        default=1
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "is_active"]),
        ]


class WHContactTariffOverride(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_contact_tariff_overrides")
    contact = models.OneToOneField("att.Contact", on_delete=models.CASCADE, related_name="contact_wh_tariff_overrides")

    storage_mode = models.CharField(max_length=20, choices=WHStorageBillingMode.choices, null=True, blank=True)

    # STORAGE PRICES
    storage_per_pallet_per_day = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )

    storage_per_unit_per_day = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )

    storage_per_m2_per_day = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )

    storage_per_m3_per_day = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )

    inbound_per_line = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )

    outbound_per_order = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )

    outbound_per_line = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    storage_min_days = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
          models.CheckConstraint(
            condition=(
                models.Q(storage_mode="pallet", storage_per_pallet_per_day__isnull=False) |
                models.Q(storage_mode="unit", storage_per_unit_per_day__isnull=False) |
                models.Q(storage_mode="m2", storage_per_m2_per_day__isnull=False) |
                models.Q(storage_mode="volume", storage_per_m3_per_day__isnull=False)
            ),
            name="valid_storage_override_mode_price")  
        ]   
        indexes = [
            models.Index(fields=["company", "contact"]),
        ]


###### START WH BILLING ######

class WHBillingPeriod(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE)

    start_date = models.DateField()
    end_date = models.DateField()

    is_closed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                                    fields=["company", "start_date", "end_date"],
                                    name="uniq_company_billing_period"
                                )                             
        ]


class WHBillingCharge(models.Model):

    class Type(models.TextChoices):
        STORAGE = "storage"
        INBOUND = "inbound"
        OUTBOUND_ORDER = "outbound_order"
        OUTBOUND_LINE = "outbound_line"

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE)
    contact = models.ForeignKey("att.Contact", on_delete=models.CASCADE)

    billing_period = models.ForeignKey("WHBillingPeriod", on_delete=models.CASCADE)

    charge_type = models.CharField(max_length=30, choices=Type.choices)

    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    unit_type = models.CharField(max_length=20,
            choices=[
                ("unit", "Unit"),
                ("pallet", "Pallet"),
                ("m2", "m2"),
                ("m3", "m3"),
                ("day", "Day"),
                ("order", "Order"),
                ("line", "Line"),
            ],
        )
    total = models.DecimalField(max_digits=18, decimal_places=4) # calculated in save

    product = models.ForeignKey(
        "WHProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
        )

    location = models.ForeignKey(
        "WHLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
        )

    source_model = models.CharField(max_length=50)
    source_uf = models.CharField(max_length=36)

    invoiced = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    locked = models.BooleanField(default=False)

    class Meta:
        constraints = [
                models.UniqueConstraint(
                    fields=["company", "contact", "billing_period", "charge_type", "source_model", "source_uf"],
                    name="uniq_charge_company_contact_period_source_type",
                )
        ]
        indexes = [
            models.Index(fields=["company", "billing_period"]),
            models.Index(fields=["contact", "billing_period"]),
            models.Index(fields=["company", "source_model", "source_uf"])
        ]

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class WHBillingInvoice(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE)
    contact = models.ForeignKey("att.Contact", on_delete=models.CASCADE)

    period = models.ForeignKey("WHBillingPeriod", on_delete=models.PROTECT)

    total_amount = models.DecimalField(max_digits=18, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=[("draft", "Draft"), ("issued", "Issued"), ("paid", "Paid")],
        default="draft",
    )

    class Meta:        
        indexes = [
            models.Index(fields=["company", "period"]),
            models.Index(fields=["contact", "period"]),
        ]


class WHBillingInvoiceLine(models.Model):

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    invoice = models.ForeignKey(
        "WHBillingInvoice",
        on_delete=models.CASCADE,
        related_name="invoice_wh_lines"
    )

    charge_type = models.CharField(
        max_length=30,
        choices=WHBillingCharge.Type.choices
    )

    description = models.CharField(max_length=250)

    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4)
    total = models.DecimalField(max_digits=18, decimal_places=4)

    created_at = models.DateTimeField(auto_now_add=True)

    charges = models.ManyToManyField(
                                        "WHBillingCharge",
                                        related_name="invoice_lines",
                                        blank=True
                                    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "charge_type"],
                name="uniq_invoice_charge_type",
            )
        ]
        indexes = [
            models.Index(fields=["invoice", "charge_type"]),
            models.Index(fields=["invoice"])
        ]

###### END WH BILLING ######