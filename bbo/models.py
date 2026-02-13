import logging
from django.db import models
from django.contrib.auth import get_user_model

from abb.utils import hex_uuid
from app.models import Company

logger = logging.getLogger(__name__)

User = get_user_model()


class Notification(models.Model):

    class Severity(models.TextChoices):
        INFO = "info"
        WARNING = "warning"
        CRITICAL = "critical"

    class Type(models.TextChoices):
        DOCUMENT_EXPIRY = "document_expiry"
        BIRTHDAY = "birthday"

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="company_notifcations"
    )

    type = models.CharField(max_length=50, choices=Type.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices)

    # title = models.CharField(max_length=255)
    # message = models.TextField()

    payload = models.JSONField(default=dict)

    related_object_type = models.CharField(
        max_length=50)   # "driver" / "vehicle"
    related_object_id = models.PositiveIntegerField()

    due_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "type",
                    "related_object_type",
                    "related_object_id",
                    "due_date"
                ],
                name="unique_document_expiry_notification"
            )
        ]


class NotificationRead(models.Model):

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="read_states"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="read_notifications"
    )

    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "user"],
                name="unique_notification_read"
            )
        ]
