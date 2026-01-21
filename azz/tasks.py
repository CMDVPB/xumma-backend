import os
import pandas as pd
from datetime import timedelta
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive
from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from abb.models import Country, Currency
from abb.utils import normalize_excel_datetime, normalize_reg_number
from app.models import Company, TypeCost
from axx.models import Trip
from ayy.models import ItemCost, ItemForItemCost
from azz.utils import json_safe, recompute_batch_totals, resolve_country

from .models import ImportBatch, ImportRow, SupplierFormat
from .models import ImportBatch, ImportRow, SupplierFormat


def _match_row_to_trip(row: ImportRow):
    """
    Tries to match one ImportRow to a Trip and create ItemCost.

    Returns:
        ("matched", trip) |
        ("unmatched", None)

    Raises:
        Exception → handled by caller and stored as row error
    """

    batch = row.batch

    # ---- resolve FK defaults ----

    # ---- normalized payload ----
    normalized = row.raw_data.get("_normalized", {})
    truck_number = normalized.get("truck_number")
    total_amount = normalized.get("amount")
    country_code = (normalized.get("country_label") or "MD")
    item_for_item_cost_code = normalized.get("article_code")
    type_code = normalized.get("cost_type")

    currency_code = normalized.get(
        "currency_code") or row.raw_data.get("currency_code", "MDL")

    item_for_item_cost_obj = ItemForItemCost.objects.get(
        code=item_for_item_cost_code
    )
    type_obj = TypeCost.objects.get(code=type_code)
    currency_obj = Currency.objects.get(currency_code=currency_code)
    country_obj = resolve_country(country_code)
    date_from = parse_datetime(normalized.get("date_from"))
    date_to = parse_datetime(normalized.get("date_to"))

    if date_from and is_naive(date_from):
        date_from = make_aware(date_from)
    if date_to and is_naive(date_to):
        date_to = make_aware(date_to)

    required_missing = [
        truck_number is None,
        date_from is None,
        total_amount is None,
    ]

    print('3580', row,  truck_number, date_from,
          total_amount, date_from, date_to, )

    if any(required_missing):
        raise ValueError("Missing normalized data")

    normalized_truck = normalize_reg_number(truck_number)

    # ---- find trip ----
    trip = (
        Trip.objects
        .filter(
            company=batch.company,
            date_order__lte=date_to,
            date_end__gte=date_from,
        )
        .filter(
            Q(vehicle_tractor__normalized_reg_number=normalized_truck) |
            Q(vehicle_trailer__normalized_reg_number=normalized_truck)
        )
        .order_by("date_order")
        .first()
    )

    print('3584', trip, normalized_truck)

    if not trip:
        return "unmatched", None

    # ---- compute unit amount ----
    quantity = row.raw_data.get("Cantitate", 1)
    unit_amount = None
    if quantity and quantity > 0:
        unit_amount = total_amount / quantity

    # ---- accounting date ----
    date = date_from

    # ---- create cost ----
    ItemCost.objects.create(
        company=trip.company,
        trip=trip,
        date=date,
        item_for_item_cost=item_for_item_cost_obj,
        currency=currency_obj,
        type=type_obj,
        country=country_obj,
        quantity=quantity,
        amount=unit_amount,
        created_by=batch.created_by,
    )

    return "matched", trip


@shared_task(
    bind=True,
    autoretry_for=(),  # ❗ do NOT retry on data errors
)
def process_import_batch(self, batch_id, supplier_format_id, file_paths):
    """
    Steps:
    1. Mark batch as PROCESSING
    2. Read CSV/XLSX files
    3. Normalize rows using SupplierFormat.column_mapping
    4. Store ImportRow (raw_data + status)
    5. Update totals
    6. Cleanup temp files
    """

    batch = ImportBatch.objects.get(id=batch_id)
    supplier_format = SupplierFormat.objects.get(id=supplier_format_id)
    mapping = supplier_format.column_mapping or {}

    # ---- validate mapping ONCE (fail fast, no retry) ----
    REQUIRED_KEYS = {"truck_number", "amount", "date_from"}

    missing = REQUIRED_KEYS - set(mapping.keys())
    if missing:
        batch.status = ImportBatch.STATUS_FAILED
        batch.finished_at = timezone.now()
        batch.totals = {
            "error": f"SupplierFormat.column_mapping missing keys: {', '.join(missing)}"
        }
        batch.save(update_fields=["status", "finished_at", "totals"])
        return

    truck_col = mapping["truck_number"]
    amount_col = mapping["amount"]
    date_from_col = mapping["date_from"]
    country_col = mapping["country_label"]
    currency_col = mapping["currency_code"]
    supplier_row_id_col = mapping["supplier_row_id"]

    # derived from date_from_col as fallback
    date_to_col = mapping.get("date_to", date_from_col)

    # ---- mark processing ----
    batch.status = ImportBatch.STATUS_PROCESSING
    batch.save(update_fields=["status"])

    rows_total = 0
    rows_imported = 0
    rows_skipped = 0

    try:
        with transaction.atomic():
            for path in file_paths:
                filename = os.path.basename(path)

                # ---- load file ----
                if path.lower().endswith(".csv"):
                    df = pd.read_csv(path)
                elif path.lower().endswith((".xls", ".xlsx", ".xlsm")):
                    df = pd.read_excel(path)
                else:
                    continue

                for idx, row in df.iterrows():
                    rows_total += 1
                    raw = {k: json_safe(v) for k, v in row.to_dict().items()}

                    # ---- extract required fields ----
                    truck_number = raw.get(truck_col)
                    amount = raw.get(amount_col)
                    date_from = raw.get(date_from_col)
                    date_to = raw.get(date_to_col)
                    country_code = raw.get(country_col)
                    currency = raw.get(currency_col)
                    supplier_row_id = supplier_row_id = raw.get(supplier_row_id_col) or raw.get("ID") or raw.get(
                        "Id") or raw.get("Transaction ID")

                    article_code = supplier_format.column_mapping.get(
                        'article_code')
                    cost_type = supplier_format.column_mapping.get(
                        'cost_type')

                    # ---- normalize truck number / dates----
                    if truck_number:
                        truck_number = str(truck_number).replace(
                            " ", "").upper()
                    tz = timezone.get_current_timezone()
                    normalized_date_from = normalize_excel_datetime(
                        date_from, tz)
                    normalized_date_to = normalize_excel_datetime(
                        date_to or date_from, tz)

                    print('3580', truck_number, amount, date_from)

                    # ---- validation / create error ----
                    if not truck_number or amount in ("", None) or not date_from:
                        ImportRow.objects.create(
                            batch=batch,
                            source_file=filename,
                            row_number=idx + 1,
                            raw_data=raw,
                            status=ImportRow.STATUS_ERROR,
                            error_message="Missing truck number, amount, or date",
                        )
                        rows_skipped += 1
                        continue

                    print('3588', supplier_row_id)

                    # ---- Skip duplicates safely Before creating ImportRow ----
                    if supplier_row_id and ImportRow.objects.filter(
                        supplier_row_id=str(supplier_row_id),
                        batch__company=batch.company,
                    ).exists():
                        rows_skipped += 1
                        continue

                    # ---- store row ----
                    ImportRow.objects.create(
                        batch=batch,
                        supplier_row_id=str(supplier_row_id),
                        source_file=filename,
                        row_number=idx + 1,
                        raw_data={
                            **raw,
                            "_normalized": {
                                "article_code": article_code,
                                "cost_type": cost_type,
                                "truck_number": truck_number,
                                "date_from": normalized_date_from,
                                "date_to": normalized_date_to,
                                "amount": float(amount),
                                "currency": (
                                    currency or supplier_format.currency).strip().upper(),
                                "country_label": (
                                    country_code or supplier_format.country).strip().upper(),
                            },
                        },
                        status=ImportRow.STATUS_IMPORTED,
                    )
                    rows_imported += 1

        # ---- success ----
        batch.status = ImportBatch.STATUS_DONE
        batch.finished_at = timezone.now()
        batch.totals = {
            "rows_total": rows_total,
            "rows_imported": rows_imported,
            "rows_skipped": rows_skipped,
        }
        batch.save()

        match_import_rows_to_trips.delay(batch.id)

    except Exception as exc:
        batch.status = ImportBatch.STATUS_FAILED
        batch.finished_at = timezone.now()
        batch.totals = {"error": str(exc)}
        batch.save(update_fields=["status", "finished_at", "totals"])
        raise

    finally:
        # ---- cleanup temp files ----
        for path in file_paths:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"Could not delete temp file {path}: {e}")


@shared_task(bind=True)
def match_import_rows_to_trips(self, batch_id):
    batch = ImportBatch.objects.get(id=batch_id)

    rows = (
        ImportRow.objects
        .filter(batch=batch, status=ImportRow.STATUS_IMPORTED)
        .select_related("batch")
    )

    matched = skipped = errors = 0

    for row in rows:

        try:
            result, trip = _match_row_to_trip(row)

            if result == "unmatched":
                row.status = ImportRow.STATUS_UNMATCHED
                row.save(update_fields=["status"])
                skipped += 1
                continue

            row.matched_trip_id = trip.id
            row.status = ImportRow.STATUS_MATCHED
            row.save(update_fields=["matched_trip_id", "status"])
            matched += 1

        except Exception as exc:
            row.status = ImportRow.STATUS_ERROR
            row.error_message = str(exc)
            row.save(update_fields=["status", "error_message"])
            errors += 1

    batch.totals.update({
        "matched": matched,
        "unmatched": skipped,
        "match_errors": errors,
    })
    batch.save(update_fields=["totals"])


@shared_task(bind=True)
def match_unmatched_import_rows(self, company_id=None):
    qs = ImportRow.objects.filter(status=ImportRow.STATUS_UNMATCHED)

    if company_id:
        qs = qs.filter(batch__company_id=company_id)

    touched_batches = set()

    matched = skipped = errors = 0

    for row in qs:
        try:
            result, trip = _match_row_to_trip(row)

            if result == "unmatched":
                skipped += 1
                continue

            row.matched_trip_id = trip.id
            row.status = ImportRow.STATUS_MATCHED
            row.save(update_fields=["matched_trip_id", "status"])
            matched += 1

            touched_batches.add(row.batch_id)

        except Exception as exc:
            row.status = ImportRow.STATUS_ERROR
            row.error_message = str(exc)
            row.save(update_fields=["status", "error_message"])
            errors += 1

            touched_batches.add(row.batch_id)

    print(
        f"[MATCH_UNMATCHED] matched={matched}, skipped={skipped}, errors={errors}"
    )

    # 🔁 recompute totals ONLY for affected batches
    for batch_id in touched_batches:
        recompute_batch_totals(ImportBatch.objects.get(id=batch_id))


@shared_task(bind=True)
def match_unmatched_import_rows_all_companies(self, days_back=30, limit_per_company=None):
    """
    Re-run trip matching for UNMATCHED ImportRows
    across all companies, limited to last `days_back` days.

    Safe to run repeatedly.
    """

    cutoff_date = timezone.now() - timedelta(days=days_back)

    companies = Company.objects.all()

    for company in companies:
        qs = ImportRow.objects.filter(
            status=ImportRow.STATUS_UNMATCHED,
            batch__company=company,
            created_at__gte=cutoff_date,
        ).select_related("batch")

        if limit_per_company:
            qs = qs[:limit_per_company]

        matched = skipped = errors = 0

        for row in qs:
            try:
                result, trip = _match_row_to_trip(row)

                if result == "unmatched":
                    skipped += 1
                    continue

                row.matched_trip_id = trip.id
                row.status = ImportRow.STATUS_MATCHED
                row.save(update_fields=["matched_trip_id", "status"])
                matched += 1

            except Exception as exc:
                row.status = ImportRow.STATUS_ERROR
                row.error_message = str(exc)
                row.save(update_fields=["status", "error_message"])
                errors += 1

        # Optional logging / monitoring
        print(
            f"[MATCHING] Company {company.id}: "
            f"matched={matched}, skipped={skipped}, errors={errors}, "
            f"days_back={days_back}"
        )

        for batch in ImportBatch.objects.filter(
            company=company,
            importrow__status__in=[
                ImportRow.STATUS_MATCHED,
                ImportRow.STATUS_UNMATCHED,
                ImportRow.STATUS_ERROR,
            ],
        ).distinct():
            recompute_batch_totals(batch)
