"""Seed product type display names / new types and upsert customers from CSV.

One-time (idempotent) data migration for an organization:

- Rename product types by code: no_loi→Compound, with_loi→Frit, no_bom→Raw Material
- Create ink and powder product types if missing (has_bom=True, apply_loi=False)
- Upsert Customer rows from a CSV with header company_name

Dry-run by default. Pass --execute to apply. Requires --organization-id.

Runbook: docs/seed-customers-and-product-types.md
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from djmoney.money import Money

from bom.models import Customer, Organization, ProductType

DEFAULT_CUSTOMERS_CSV = (
    Path(__file__).resolve().parents[2] / "data" / "customers.csv"
)

# code → target display name (existing rows are renamed when name differs)
PRODUCT_TYPE_RENAMES = {
    "no_loi": "Compound",
    "with_loi": "Frit",
    "no_bom": "Raw Material",
}

# code → (name, has_bom, apply_loi); created only if missing
PRODUCT_TYPES_TO_CREATE = (
    ("ink", "Ink", True, False),
    ("powder", "Powder", True, False),
)


class Command(BaseCommand):
    help = (
        "Rename/create product types and upsert customers from CSV for one "
        "organization. Dry-run by default; pass --execute to apply."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--organization-id",
            type=int,
            required=True,
            help="Organization primary key to seed (required).",
        )
        parser.add_argument(
            "--customers-csv",
            type=str,
            default=str(DEFAULT_CUSTOMERS_CSV),
            help=(
                "Path to CSV with header company_name. "
                f"Default: {DEFAULT_CUSTOMERS_CSV}"
            ),
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Apply changes. Without this flag, only print what would change.",
        )

    def handle(self, *args, **options):
        organization_id = options["organization_id"]
        execute = options["execute"]
        csv_path = Path(options["customers_csv"])

        try:
            org = Organization.objects.get(pk=organization_id)
        except Organization.DoesNotExist as exc:
            raise CommandError(
                f"No organization found with id={organization_id}"
            ) from exc

        if not csv_path.is_file():
            raise CommandError(f"Customers CSV not found: {csv_path}")

        names = self._read_customer_names(csv_path)
        existing_names = set(
            Customer.objects.filter(organization=org).values_list("name", flat=True)
        )
        to_create_customers = [n for n in names if n not in existing_names]
        skipped_customers = len(names) - len(to_create_customers)

        renames = []
        for code, target_name in PRODUCT_TYPE_RENAMES.items():
            pt = ProductType.objects.filter(organization=org, code=code).first()
            if pt is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"Product type code={code!r} missing; skip rename to {target_name!r}"
                    )
                )
                continue
            if pt.name != target_name:
                renames.append((pt, target_name))

        existing_codes = set(
            ProductType.objects.filter(organization=org).values_list("code", flat=True)
        )
        creates = [
            (code, name, has_bom, apply_loi)
            for code, name, has_bom, apply_loi in PRODUCT_TYPES_TO_CREATE
            if code not in existing_codes
        ]

        max_sort = (
            ProductType.objects.filter(organization=org).aggregate(m=Max("sort_order"))[
                "m"
            ]
            or 0
        )
        currency = org.currency or "USD"

        self.stdout.write(f"Organization id={org.id} name={org.name!r} currency={currency}")
        self.stdout.write(f"Customers CSV: {csv_path}")
        self.stdout.write(f"Customer names in CSV (unique, non-empty): {len(names)}")
        self.stdout.write(f"  would create: {len(to_create_customers)}")
        self.stdout.write(f"  already exist (skip): {skipped_customers}")
        self.stdout.write(f"Product type renames: {len(renames)}")
        for pt, target_name in renames:
            self.stdout.write(
                f"  code={pt.code!r}: {pt.name!r} → {target_name!r}"
            )
        self.stdout.write(f"Product types to create: {len(creates)}")
        for index, (code, name, has_bom, apply_loi) in enumerate(creates, start=1):
            self.stdout.write(
                f"  code={code!r} name={name!r} has_bom={has_bom} "
                f"apply_loi={apply_loi} sort_order={max_sort + index}"
            )

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN (no changes). Re-run with --execute to apply."
                )
            )
            return

        with transaction.atomic():
            for pt, target_name in renames:
                pt.name = target_name
                pt.save(update_fields=["name"])

            for index, (code, name, has_bom, apply_loi) in enumerate(creates, start=1):
                ProductType.objects.create(
                    organization=org,
                    code=code,
                    name=name,
                    has_bom=has_bom,
                    apply_loi=apply_loi,
                    overhead=Money(0, currency),
                    sort_order=max_sort + index,
                )

            Customer.objects.bulk_create(
                [
                    Customer(name=name, organization=org)
                    for name in to_create_customers
                ]
            )

            org.invalidate_product_type_cache()

        self.stdout.write(
            self.style.SUCCESS(
                f"Renamed {len(renames)} product type(s), created {len(creates)} "
                f"product type(s), created {len(to_create_customers)} customer(s)."
            )
        )

    def _read_customer_names(self, csv_path: Path) -> list[str]:
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or "company_name" not in reader.fieldnames:
                raise CommandError(
                    "CSV must have a company_name header. "
                    f"Found: {reader.fieldnames!r}"
                )
            seen = set()
            names = []
            for row in reader:
                name = (row.get("company_name") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                names.append(name)
            return names
