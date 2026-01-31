from __future__ import annotations

import uuid
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone


from app.models import Company

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
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="%(class)s_created"
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class CalendarEventType(models.Model):
    uf = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, blank=True, null=True, related_name="company_calendar_event_types"
    )
    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_by_calendar_event_types"
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=50)
    code = models.CharField(max_length=50, unique=True)

    is_system = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Calendar(TimeStampedModel):

    name = models.CharField(max_length=100)

    color = models.CharField(max_length=20, default="#1890ff")

    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class CalendarEvent(TimeStampedModel):

    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="events"
    )

    event_type = models.ForeignKey(
        CalendarEventType,
        blank=True, null=True,
        on_delete=models.PROTECT,
        related_name="event_type_calendar_events"
    )

    title = models.CharField(max_length=100)
    description = models.TextField()

    start = models.DateTimeField()
    end = models.DateTimeField()

    all_day = models.BooleanField(default=False)

    color = models.CharField(max_length=20, default="#1890ff")

    class Meta:
        ordering = ["start"]

    def __str__(self):
        return self.title


class ActivityLog(TimeStampedModel):
    action = models.CharField(max_length=50, null=True, blank=True)

    entity_type = models.CharField(max_length=50, null=True, blank=True)
    entity_id = models.UUIDField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    is_reversible = models.BooleanField(default=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reversed_activity_logs",
    )
    reverse_metadata = models.JSONField(
        default=dict, blank=True)  # the patch to apply to undo


class CalendarMember(models.Model):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("editor", "Editor"),
        ("viewer", "Viewer"),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ("calendar", "user")
