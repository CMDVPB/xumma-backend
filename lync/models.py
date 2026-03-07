import logging
from django.contrib.auth import get_user_model
from django.db import models

from abb.security.fields import EncryptedJSONField

logger = logging.getLogger(__name__)

User = get_user_model()

class LoadSecret(models.Model):
    company = models.ForeignKey(
        "app.Company",
        on_delete=models.CASCADE,
        related_name="company_load_secrets"
    )

    load = models.OneToOneField(
        "axx.Load",
        on_delete=models.CASCADE,
        related_name="load_secrets",
        db_index=True
    )

    payload = EncryptedJSONField(blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_load_secrets"
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_load_secrets"
    )

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["company"]),
        ]

    def __str__(self):
        return f"LoadSecret<{self.load_id}>"