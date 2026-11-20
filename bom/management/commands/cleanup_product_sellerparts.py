"""Delete SellerParts attached to product parts (has_bom / is_product).

Dry-run by default. Pass --execute to delete. Never touches ManufacturerParts
or raw-material SellerParts.

Examples:
  python manage.py cleanup_product_sellerparts
  python manage.py cleanup_product_sellerparts --execute
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Max

from bom.models import PartRevision, SellerPart


def product_sellerparts_queryset():
    """SellerParts whose manufacturer_part.part latest revision is_product."""
    part_ids = (
        SellerPart.objects.values_list("manufacturer_part__part_id", flat=True)
        .distinct()
    )
    latest_rev_ids = (
        PartRevision.objects.filter(part_id__in=part_ids)
        .values("part_id")
        .annotate(max_id=Max("id"))
        .values_list("max_id", flat=True)
    )
    # Warm org product-type maps once while evaluating is_product.
    product_part_ids = []
    for rev in PartRevision.objects.filter(id__in=latest_rev_ids).select_related(
        "part__organization"
    ):
        if rev.is_product:
            product_part_ids.append(rev.part_id)
    return SellerPart.objects.filter(
        manufacturer_part__part_id__in=product_part_ids
    )


class Command(BaseCommand):
    help = (
        "Find SellerParts on product parts (latest revision is_product / "
        "has_bom) and delete them. Dry-run by default; use --execute to delete. "
        "Does not delete ManufacturerParts or raw-material SellerParts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually delete matching SellerParts (default is dry-run).",
        )

    def handle(self, *args, **options):
        qs = product_sellerparts_queryset()
        count = qs.count()
        raw_remaining = SellerPart.objects.exclude(
            pk__in=qs.values_list("pk", flat=True)
        ).count()

        self.stdout.write(f"Product SellerParts found: {count}")
        self.stdout.write(f"Raw-material SellerParts left untouched: {raw_remaining}")

        if not options["execute"]:
            self.stdout.write(
                self.style.WARNING("Dry-run only. Re-run with --execute to delete.")
            )
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted product SellerParts: {count}"))
