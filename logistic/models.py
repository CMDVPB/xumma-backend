import logging
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth import get_user_model

from abb.utils import hex_uuid

logger = logging.getLogger(__name__)

User = get_user_model()


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

    product = models.ForeignKey("WHProduct", on_delete=models.CASCADE, related_name="product_stock_rows")
    location = models.ForeignKey("WHLocation", on_delete=models.PROTECT, related_name="location_stock_rows")

    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint("product", "location", name="uniq_stock_product_location"),
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

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_stock_ledger")

    product = models.ForeignKey("WHProduct", on_delete=models.CASCADE, related_name="product_ledger_rows")
    location = models.ForeignKey("WHLocation", on_delete=models.PROTECT, related_name="location_ledger_rows")

    delta = models.DecimalField(max_digits=18, decimal_places=3)  # +in / -out
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

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(delta=0), name="chk_ledger_delta_nonzero"),
        ]
        indexes = [
            models.Index(fields=["company", "product", "created_at"]),
            models.Index(fields=["company", "source_type", "source_uf"]),
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

    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    note = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="chk_inboundline_qty_gt_0"),
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
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    note = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="chk_outboundline_qty_gt_0"),
        ]
        indexes = [
            models.Index(fields=["outbound"]),
            models.Index(fields=["product"]),
        ]


class WHTariff(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="wms_tariffs")
    is_active = models.BooleanField(default=True)

    storage_per_unit_per_day = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    inbound_per_line = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    outbound_per_order = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    outbound_per_line = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "is_active"]),
        ]


class WHContactTariffOverride(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True, unique=True)

    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_wh_contact_tariff_overrides")
    contact = models.OneToOneField("att.Contact", on_delete=models.CASCADE, related_name="contact_wh_tariff_overrides")

    storage_per_unit_per_day = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    inbound_per_line = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    outbound_per_order = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    outbound_per_line = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:        
        indexes = [
            models.Index(fields=["company", "contact"]),
        ]