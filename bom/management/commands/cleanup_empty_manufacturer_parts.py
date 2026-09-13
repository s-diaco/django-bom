"""Remove empty ManufacturerPart rows left by BOM CSV import.

BOM CSV import used to create Manufacturer(name="") + ManufacturerPart(mpn="")
on every row that lacked manufacturer name and MPN. Those rows also overwrote
Part.primary_manufacturer_part.

Default is a dry run. Pass --execute to apply.

Does not delete ManufacturerParts that have SellerPart pricing, and does not
touch the parts-upload placeholder manufacturer "انتخاب نشده (پیش فرض)".

New BOM/parts CSV rows with no manufacturer name and no MPN skip creating a
manufacturer part. A default manufacturer part is created later if a seller
price is added.

Runbook: docs/cleanup-empty-manufacturer-parts.md
"""

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q, Value
from django.db.models.functions import Coalesce, Trim

from bom.models import Manufacturer, ManufacturerPart, Organization, Part

SAMPLE_LIMIT = 20


def empty_manufacturer_parts_qs(organization_id=None):
    qs = ManufacturerPart.objects.annotate(
        mpn_stripped=Trim("manufacturer_part_number"),
        mfg_name_stripped=Coalesce(Trim("manufacturer__name"), Value("")),
    ).filter(mpn_stripped="", mfg_name_stripped="")
    if organization_id is not None:
        qs = qs.filter(part__organization_id=organization_id)
    return qs


def _blank_manufacturers_qs(organization_id=None):
    qs = Manufacturer.objects.annotate(name_stripped=Trim("name")).filter(
        name_stripped=""
    )
    if organization_id is not None:
        qs = qs.filter(organization_id=organization_id)
    return qs


def _pick_keeper(siblings):
    siblings = sorted(siblings, key=lambda mp: mp.id)
    for mp in siblings:
        if (mp.manufacturer_part_number or "").strip():
            return mp
    return siblings[0] if siblings else None


class Command(BaseCommand):
    help = (
        "Delete empty ManufacturerParts (blank MPN and blank/null manufacturer) "
        "created by BOM CSV import. Dry-run by default; pass --execute to apply."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Apply deletions. Without this flag, only print what would change.",
        )
        parser.add_argument(
            "--organization-id",
            type=int,
            default=None,
            help="Limit to one organization. Omit to scan the whole database.",
        )

    def handle(self, *args, **options):
        organization_id = options["organization_id"]
        execute = options["execute"]

        if (
            organization_id is not None
            and not Organization.objects.filter(pk=organization_id).exists()
        ):
            raise CommandError(f"No organization found with id={organization_id}")

        empty_qs = empty_manufacturer_parts_qs(organization_id).annotate(
            seller_count=Count("sellerpart")
        )
        skipped_priced = empty_qs.filter(seller_count__gt=0)
        deletable = empty_qs.filter(seller_count=0)
        deletable_ids = list(deletable.values_list("id", flat=True))
        skipped_priced_count = skipped_priced.count()
        empty_count = len(deletable_ids) + skipped_priced_count

        parts_with_empty_primary = list(
            Part.objects.filter(
                primary_manufacturer_part_id__in=deletable_ids
            ).values_list("id", flat=True)
        )
        keepers_by_part = defaultdict(list)
        if parts_with_empty_primary:
            for mp in ManufacturerPart.objects.filter(
                part_id__in=parts_with_empty_primary
            ).exclude(pk__in=deletable_ids):
                keepers_by_part[mp.part_id].append(mp)

        repointed = []
        cleared = []
        for part_id in parts_with_empty_primary:
            keeper = _pick_keeper(keepers_by_part.get(part_id, []))
            if keeper is None:
                cleared.append(part_id)
            else:
                repointed.append((part_id, keeper.id))

        orphan_mfg_ids = list(
            _blank_manufacturers_qs(organization_id)
            .annotate(
                keep_count=Count(
                    "manufacturerpart",
                    filter=~Q(manufacturerpart__id__in=deletable_ids),
                )
            )
            .filter(keep_count=0)
            .values_list("id", flat=True)
        )

        self.stdout.write(
            f"Empty manufacturer parts (blank MPN + blank/null manufacturer): {empty_count}"
        )
        self.stdout.write(f"  with seller/pricing (skipped): {skipped_priced_count}")
        self.stdout.write(f"  deletable: {len(deletable_ids)}")
        self.stdout.write(
            f"Parts whose primary would be reassigned: {len(parts_with_empty_primary)}"
        )
        self.stdout.write(
            f"  re-pointed to a remaining manufacturer part: {len(repointed)}"
        )
        self.stdout.write(
            f"  primary cleared (no remaining manufacturer part): {len(cleared)}"
        )
        self.stdout.write(
            f"Blank manufacturers that would become unused: {len(orphan_mfg_ids)}"
        )

        sample = list(
            deletable.order_by("id").values(
                "id",
                "part_id",
                "manufacturer_id",
                "manufacturer_part_number",
                "manufacturer__name",
            )[:SAMPLE_LIMIT]
        )
        if sample:
            self.stdout.write(f"Sample (up to {SAMPLE_LIMIT}):")
            for row in sample:
                self.stdout.write(
                    "  part_id={part_id} mp_id={id} mpn={manufacturer_part_number!r} "
                    "manufacturer_id={manufacturer_id} manufacturer_name={manufacturer__name!r}".format(
                        **row
                    )
                )

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN (no changes). Re-run with --execute to apply."
                )
            )
            return

        with transaction.atomic():
            for part_id, keeper_id in repointed:
                Part.objects.filter(pk=part_id).update(
                    primary_manufacturer_part_id=keeper_id
                )
            if cleared:
                Part.objects.filter(pk__in=cleared).update(
                    primary_manufacturer_part=None
                )
            deleted_mp, _ = ManufacturerPart.objects.filter(
                pk__in=deletable_ids
            ).delete()
            deleted_mfg, _ = Manufacturer.objects.filter(pk__in=orphan_mfg_ids).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {len(deletable_ids)} manufacturer parts "
                f"({deleted_mp} objects including cascades) and "
                f"{len(orphan_mfg_ids)} blank manufacturers ({deleted_mfg} objects)."
            )
        )
