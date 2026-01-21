import os
import csv
import pandas as pd
from django.db.models import Q
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from abb.models import Country


class Command(BaseCommand):
    help = "Import countries from CSV / XLS / XLSX / XLSM"

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=str,
            help="Path to CSV or Excel file",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse file but do not write to database",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        dry_run = options["dry_run"]

        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".csv":
            rows = self._read_csv(file_path)
        elif ext in [".xls", ".xlsx", ".xlsm"]:
            rows = self._read_excel(file_path)
        else:
            raise CommandError("Unsupported file format")

        created = 0
        skipped = 0

        with transaction.atomic():
            for row in rows:
                existing = Country.objects.filter(
                    Q(value=row["value"]) |
                    Q(serial_number=row["serial_number"])
                ).first()

                if existing:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping country: value={row['value']}, "
                            f"serial_number={row['serial_number']} "
                            f"(existing id={existing.id})"
                        )
                    )
                    skipped += 1
                    continue

                Country.objects.create(
                    serial_number=row["serial_number"],
                    label=row["label"],
                    value=row["value"],
                    value_iso3=row["value_iso3"],
                    value_numeric=row["value_numeric"],
                )
                created += 1

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN — rollback applied (would create {created}, skip {skipped})"
                    )
                )
                return

        self.stdout.write(
            self.style.SUCCESS(
                f"Import finished: created {created}, skipped {skipped}"
            )
        )

    # ------------------------
    # Readers
    # ------------------------

    def _read_csv(self, path):
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(self._normalize_row(r))
        return rows

    def _read_excel(self, path):
        df = pd.read_excel(path)
        rows = []
        for _, r in df.iterrows():
            rows.append(self._normalize_row(r.to_dict()))
        return rows

    # ------------------------
    # Normalization
    # ------------------------

    def _normalize_row(self, r):
        try:
            return {
                "serial_number": int(r["serial_number"]),
                "label": str(r["label"]).strip(),
                "value": str(r["value"]).strip().upper(),          # ISO2
                "value_iso3": str(r["value_iso3"]).strip().upper(),
                "value_numeric": str(r["value_numeric"]).strip(),
            }
        except KeyError as e:
            raise CommandError(f"Missing column: {e}")
