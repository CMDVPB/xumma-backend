import logging
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.conf import settings
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from abb.models import Currency
from abb.utils import hex_uuid

logger = logging.getLogger(__name__)

User = get_user_model()


class PointOfService(models.Model):
    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    company = models.ForeignKey('app.Company', on_delete=models.CASCADE, related_name="points_of_service")

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=50, blank=True, null=True)
   
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
                models.UniqueConstraint(fields=["company", "name"], name="uniq_point_name_per_company")
            ]

    def __str__(self):
        return f"{self.company_id} - {self.name}"
    

class Role(models.TextChoices):
    LEADER = "leader", "Leader"
    BROKER = "broker", "Broker"


class PointMembership(models.Model):   
    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_point_memberships")
    point = models.ForeignKey(PointOfService, on_delete=models.CASCADE, related_name="point_memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_point_memberships")

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.BROKER
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["point", "user"], name="uniq_point_user"),            
        ]

    
class TeamVisibilityGrant(models.Model):
    """
    Grants a user (leader or broker) access to jobs of specific points (teams).
    Created by level_admin.
    """
    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_team_visibility_grants")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_team_visibility_grants")
    point = models.ForeignKey(PointOfService, on_delete=models.CASCADE, related_name="point_team_visibility_grants")

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_by_team_visibility_grants"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "user", "point"], name="uniq_visibility_grant"),            
        ]

###### START BROKER JOB INVOICING ######
class BrokerInvoice(models.Model):
    class InvoiceStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        CANCELLED = "cancelled", "Cancelled"

    uf = models.CharField(max_length=36, default=hex_uuid, unique=True, db_index=True)

    company = models.ForeignKey(
        "app.Company",
        on_delete=models.CASCADE,
        related_name="broker_invoices"
    )

    customer = models.ForeignKey(
        "att.Contact",
        on_delete=models.PROTECT,
        related_name="customer_broker_invoices"
    )

    invoice_number = models.CharField(max_length=50, db_index=True)
    invoice_date = models.DateField()
    issued_at = models.DateTimeField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
        db_index=True
    )

    comments = models.CharField(max_length=500, blank=True, null=True)

    total_net = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)


class BrokerInvoiceLine(models.Model):
    invoice = models.ForeignKey(
        BrokerInvoice,
        on_delete=models.CASCADE,
        related_name="broker_invoice_lines"
    )

    job = models.ForeignKey(
        "broker.Job",
        on_delete=models.PROTECT,
        related_name="job_invoice_lines"
    )

    description = models.CharField(max_length=255, blank=True, null=True)

    amount_net = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    amount_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position"]


###### END BROKER JOB INVOICING ######

class Job(models.Model):
    class JobStatus(models.TextChoices):
        NEW = "new", "New"
        CREATED = "created", "Created"     
        PENDING = "pending", "Pending"
        FINISHED = "finished", "Finished"

    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_broker_jobs")
    point = models.ForeignKey(PointOfService, on_delete=models.PROTECT, related_name="point_broker_jobs")

    customer = models.ForeignKey("att.Contact", on_delete=models.PROTECT, related_name="customer_broker_jobs")

    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_to_broker_jobs"
    )

    job_add_info = models.CharField(max_length=100, blank=True, null=True)
    comments = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    date_job = models.DateField(blank=True, null=True)

    ref = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=30, choices=JobStatus, default=JobStatus.CREATED, db_index=True)

    broker_invoice = models.ForeignKey(
            BrokerInvoice,
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name="broker_invoice_jobs"
        )

    class Meta:
        indexes = [
            models.Index(fields=["company", "point", "status"]),
            models.Index(fields=["company", "assigned_to", "created_at"]),
        ]

    @property
    def is_invoiced(self):
        return self.broker_invoice_id is not None


    def __str__(self):
        return f"{self.ref}"
    

class ServiceType(models.Model):
    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="service_types")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)

    default_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        constraints = [
                    models.UniqueConstraint(fields=["company", "code"], name="uniq_service_type_code_per_company")
                ]

    def __str__(self):
        return self.name


class ServiceTypeTier(models.Model):
    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.CASCADE,
        related_name="pricing_tiers"
    )

    from_quantity = models.PositiveIntegerField()
    to_quantity = models.PositiveIntegerField(null=True, blank=True)

    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["from_quantity"]


class ServiceGroup(models.Model):

    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    company = models.ForeignKey(
        "app.Company",
        on_delete=models.CASCADE,
        related_name="company_service_groups"
    )

    name = models.CharField(max_length=120)

    main_service = models.ForeignKey(
        "ServiceType",
        on_delete=models.PROTECT,
        related_name="main_service_groups"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="uniq_service_group_name"
            )
        ]


class ServiceGroupItem(models.Model):

    group = models.ForeignKey(
        ServiceGroup,
        on_delete=models.CASCADE,
        related_name="service_group_items"
    )

    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT
    )

    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "service_type"],
                name="uniq_service_group_item"
            )
        ]


class CustomerServicePrice(models.Model):
    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_customer_service_prices")

    customer = models.ForeignKey("att.Contact", on_delete=models.CASCADE, related_name="customer_service_prices")

    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE, related_name="service_type_customer_prices")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    
    is_active = models.BooleanField(default=True)

    valid_from = models.DateTimeField(auto_now_add=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "customer", "service_type"], name="uniq_customer_service_price"),            
        ]
        indexes = [
                models.Index(fields=["company", "customer"]),
                models.Index(fields=["company", "service_type"]),
        ]


class CustomerServiceTierPrice(models.Model):

    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    company = models.ForeignKey(
        "app.Company",
        on_delete=models.CASCADE,
        related_name="customer_service_tier_prices"
    )

    customer = models.ForeignKey(
        "att.Contact",
        on_delete=models.CASCADE,
        related_name="customer_service_tier_prices"
    )

    service_tier = models.ForeignKey(
        "ServiceTypeTier",
        on_delete=models.CASCADE,
        related_name="customer_prices"
    )

    price = models.DecimalField(max_digits=12, decimal_places=2)

    is_active = models.BooleanField(default=True)

    valid_from = models.DateTimeField(auto_now_add=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    changed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "service_tier"],
                name="uniq_customer_service_tier_price"
            )
        ]


class JobLine(models.Model):
    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="job_lines"
    )

    parent_line = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="job_line_children",
    )

    service_group = models.ForeignKey(
        ServiceGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_group_job_lines"
    )

    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT,
        related_name="service_type_job_lines"
    )

    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price_net = models.DecimalField(max_digits=12, decimal_places=2)
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    other_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.CharField(max_length=100, blank=True, null=True)

    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position"]
        indexes = [
                models.Index(fields=["job", "parent_line", "position"]),
                models.Index(fields=["service_group"]),
                models.Index(fields=["service_type"]),
            ]

    def clean(self):
        super().clean()

        if not self.job_id:
            return

        if self.parent_line:
            if self.parent_line == self:
                raise ValidationError("A job line cannot be its own parent.")

            if self.parent_line.parent_line:
                raise ValidationError("Only one level of additional services allowed.")

            if self.parent_line.job_id != self.job_id:
                raise ValidationError("Parent line must belong to the same job.")

        if self.service_group and self.service_group.company_id != self.job.company_id:
            raise ValidationError("Service group must belong to the same company as the job.")

        if self.service_type and self.service_type.company_id != self.job.company_id:
            raise ValidationError("Service type must belong to the same company as the job.")

        if self.service_group and not self.parent_line:
            if self.service_group.main_service_id != self.service_type_id:
                raise ValidationError(
                    "Main line service type must match the service group's main service."
                )

        if self.parent_line and self.service_group:
            if (
                self.parent_line.service_group_id and
                self.parent_line.service_group_id != self.service_group_id
            ):
                raise ValidationError(
                    "Child line must use the same service group as the parent line."
                )

            allowed = ServiceGroupItem.objects.filter(
                group=self.service_group,
                service_type=self.service_type
            ).exists()

            if not allowed:
                raise ValidationError(
                    "This service type is not allowed in the selected service group."
                )

    def save(self, *args, **kwargs):
            self.full_clean()   # ensures clean() is always executed
            super().save(*args, **kwargs)

    @property
    def total_net(self):
        return self.quantity * self.unit_price_net

    @property
    def total_vat(self):
        return self.total_net * self.vat_percent / 100

    @property
    def total_gross(self):
        return self.total_net + self.total_vat
    

###### START BROKER COMPENSATION ######
class BrokerBaseSalary(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True, db_index=True)
    company = models.ForeignKey(
        "app.Company",
        on_delete=models.CASCADE,
        related_name="company_broker_base_salaries",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="broker_base_salaries"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="currency_broker_base_salaries")

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-valid_from"]
        indexes = [
            models.Index(fields=["user", "valid_from"]),
        ]

    def clean(self):

        overlapping = BrokerBaseSalary.objects.filter(
            user=self.user,
            company=self.company,
        ).exclude(pk=self.pk).filter(
            valid_from__lte=self.valid_to if self.valid_to else self.valid_from,
            valid_to__gte=self.valid_from
        )

        if overlapping.exists():
            raise ValidationError("Salary periods overlap.")
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} {self.amount} {self.currency}"
    

class BrokerCommissionType(models.TextChoices):
    INCL_VAT = "incl_vat", _("Including VAT")
    EXCL_VAT = "excl_vat", _("Excluding VAT")


class BrokerCommission(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True, db_index=True)
    company = models.ForeignKey(
            "app.Company",
            on_delete=models.CASCADE,
            related_name="company_broker_commissions"
        )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="broker_commissions"
    )

    customer = models.ForeignKey(
        "att.Contact",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="customer_broker_commissions"
    )

    service_type = models.ForeignKey(
        "broker.ServiceType",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="service_type_broker_commissions"
    )

    type = models.CharField(
            max_length=20,
            choices=BrokerCommissionType.choices,
            default=BrokerCommissionType.EXCL_VAT
        )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-valid_from"]        
        indexes = [
            models.Index(fields=["user", "valid_from"]),
            models.Index(fields=["company", "user"]),
        ]

    def clean(self):
        super().clean()

        if self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError({
                "valid_to": "valid_to cannot be earlier than valid_from."
            })
        
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} {self.value} ({self.type})"


class BrokerSettlementStatus(models.TextChoices):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"


class BrokerSettlement(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    company = models.ForeignKey(
        "app.Company",
        on_delete=models.CASCADE,
        related_name="company_broker_settlements",
    )

    broker = models.ForeignKey(User, on_delete=models.CASCADE)

    period_start = models.DateField()
    period_end = models.DateField()

    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    commission_total = models.DecimalField(max_digits=12, decimal_places=2)
    total_income = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=BrokerSettlementStatus.choices,
        default=BrokerSettlementStatus.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    settlement_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["broker", "period_start", "period_end"],
                name="unique_broker_period_start_period_end_settlement"
            )
        ]
        indexes = [
            models.Index(fields=["company", "broker"]),            
            models.Index(fields=["broker", "status"])
        ]

   
###### END BROKER COMPENSATION ######