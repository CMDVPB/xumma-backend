from app.models import Company
from abb.utils import hex_uuid
from django.db import models
from django.contrib.auth import get_user_model
import logging
logger = logging.getLogger(__name__)


User = get_user_model()


class DocumentTemplate(models.Model):
    TEMPLATE_TYPES = (
        ('invoice', 'Invoice'),
        ('order', 'Order'),
        ('act', 'Act'),
    )

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_document_templates"
    )

    code = models.CharField(max_length=100)  # e.g. "invoice_default"
    type = models.CharField(max_length=16, choices=TEMPLATE_TYPES)
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_by_document_templates"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = (
            "company",
            "type",
            "is_default",
        )


class DocumentTemplateTranslation(models.Model):
    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.CASCADE,
        related_name="template_document_translations"
    )

    language = models.CharField(max_length=2)  # "en", "ro", "ru"
    body_html = models.TextField()

    class Meta:
        unique_together = ("template", "language")
