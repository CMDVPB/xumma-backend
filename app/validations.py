import re
from django.core.exceptions import ValidationError

def validate_invoice_start_number(value):
    if not value:
        raise ValidationError("Invoice start number is required.")

    if not re.match(r"^.*\d+$", value):
        raise ValidationError(
            "Invoice start number must end with digits, e.g. 1, INV-1, AB2026-001."
        )