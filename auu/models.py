from django.db import models

from abb.utils import hex_uuid
from app.models import Company


class PaymentMethod(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_payment_methods')

    serial_number = models.PositiveSmallIntegerField(unique=True)

    code = models.CharField(max_length=20)

    label = models.CharField(max_length=30)

    is_active = models.BooleanField(default=True)

    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ['is_system', 'serial_number']

    def __str__(self):
        return self.label
