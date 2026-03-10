import logging
from django.db import models
from django.conf import settings
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

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


class Job(models.Model):
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

    ref = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=30, default="new", blank=True, null=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "point", "status"]),
            models.Index(fields=["company", "assigned_to", "created_at"]),
        ]

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
    

