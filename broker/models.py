import logging
from django.db import models
from django.conf import settings
from django.db.models import Q
from django.contrib.auth import get_user_model

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
        unique_together = [("company", "name")]

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

    ref = models.CharField(max_length=50, db_index=True)  # internal reference
    status = models.CharField(max_length=30, default="new", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

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

    class Meta:
        unique_together = [("company", "code")]

    def __str__(self):
        return self.name


class CustomerServicePrice(models.Model):
    uf = models.CharField(max_length=36, db_index=True, default=hex_uuid, unique=True)
    company = models.ForeignKey("app.Company", on_delete=models.CASCADE, related_name="company_customer_service_prices")
    customer = models.ForeignKey("att.Contact", on_delete=models.CASCADE, related_name="customer_service_prices")
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE, related_name="service_type_customer_prices")

    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "customer", "service_type"], name="uniq_customer_service_price"),            
        ]