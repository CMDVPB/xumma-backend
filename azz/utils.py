import pandas as pd
from django.db.models import Q
from datetime import datetime, date

from abb.models import Country
from azz.models import ImportBatch, ImportRow


def json_safe(value):
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def resolve_country(code_or_name: str) -> Country:
    value = (code_or_name or "").strip().upper()

    country = Country.objects.filter(
        Q(label=value) |        # ISO2 (HR)
        Q(value=value) |        # Full name (CROATIA)
        Q(value_iso3=value)     # ISO3 (HRV)
    ).first()

    if not country:
        raise ValueError(f"Country not found: {value}")

    return country


def resolve_mapped_value(raw, mapping_value):
    if mapping_value in raw:
        return raw.get(mapping_value)
    return mapping_value


def recompute_batch_totals(batch: ImportBatch):
    totals = {
        "matched": ImportRow.objects.filter(
            batch=batch,
            status=ImportRow.STATUS_MATCHED
        ).count(),
        "unmatched": ImportRow.objects.filter(
            batch=batch,
            status=ImportRow.STATUS_UNMATCHED
        ).count(),
        "match_errors": ImportRow.objects.filter(
            batch=batch,
            status=ImportRow.STATUS_ERROR
        ).count(),
        "rows_imported": ImportRow.objects.filter(
            batch=batch,
            status__in=[
                ImportRow.STATUS_MATCHED,
                ImportRow.STATUS_UNMATCHED,
                ImportRow.STATUS_ERROR,
            ],
        ).count(),
    }

    batch.totals.update(totals)
    batch.save(update_fields=["totals"])
