import os
import csv
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from abb.models import Currency
from abb.models import Currency


class Command(BaseCommand):
    help = "Import currencies from CSV / Excel (skip existing safely)"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        file_path = options["file"]
        dry_run = options["dry_run"]

        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".csv":
            rows = self._read_csv(file_path)
        elif ext in (".xls", ".xlsx", ".xlsm"):
            rows = self._read_excel(file_path)
        else:
            raise CommandError("Unsupported file format")

        created = 0
        skipped = 0

        with transaction.atomic():
            for row in rows:
                existing = Currency.objects.filter(
                    Q(currency_code=row["currency_code"]) |
                    Q(serial_number=row["serial_number"]) |
                    Q(currency_numeric=row["currency_numeric"])
                ).first()

                if existing:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping existing currency: "
                            f"{row['currency_code']} "
                            f"(id={existing.id})"
                        )
                    )
                    skipped += 1
                    continue

                Currency.objects.create(
                    currency_code=row["currency_code"],
                    currency_name=row["currency_name"],
                    currency_symbol=row["currency_symbol"],
                    currency_numeric=row["currency_numeric"],
                    serial_number=row["serial_number"],
                )
                created += 1

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN — rollback applied "
                        f"(would create {created}, skip {skipped})"
                    )
                )
                return

        self.stdout.write(
            self.style.SUCCESS(
                f"Import finished: created {created}, skipped {skipped}"
            )
        )

    # -----------------------
    # Readers
    # -----------------------

    def _read_csv(self, path):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [self._normalize_row(r) for r in reader]

    def _read_excel(self, path):
        df = pd.read_excel(path)
        return [self._normalize_row(r.to_dict()) for _, r in df.iterrows()]

    # -----------------------
    # Normalization
    # -----------------------

    def _normalize_row(self, r):
        try:
            return {
                "currency_code": str(r["currency_code"]).strip().upper(),
                "currency_name": self._clean(r.get("currency_name")),
                "currency_symbol": self._clean(r.get("currency_symbol")),
                "currency_numeric": int(r["currency_numeric"]),
                "serial_number": int(r["serial_number"]),
            }
        except KeyError as e:
            raise CommandError(f"Missing required column: {e}")

    def _clean(self, value):
        return str(value).strip() if value not in ("", None) else None
