"""Import a SystemGroup PAC Engineering BoM into Lithium.

Credentials (env only, never commit):
  CRM_BASE_URL   e.g. http://192.168.3.193/
  CRM_USERNAME
  CRM_PASSWORD

Examples:
  python manage.py import_systemgroup_bom --bom-id 39477 --organization-id 1
  python manage.py import_systemgroup_bom --html-file ./bom-edit.html --organization-id 1 --parent-part 500-1234-00

Admin UI: Upload → Import SystemGroup BoM (same backend).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from bom.models import Organization
from bom.systemgroup.importer import SystemGroupImportError, run_systemgroup_import


class Command(BaseCommand):
    help = (
        "Import a SystemGroup PAC Engineering BoM into Lithium parts/revisions "
        "(reuses CSV BoM / Add-all-subparts semantics). Credentials: CRM_BASE_URL, "
        "CRM_USERNAME, CRM_PASSWORD. Same backend as the Admin Upload UI."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--bom-id",
            type=str,
            default=None,
            help="CRM BoM id (Edit.aspx?id=...). Required unless --html-file/--json-file/--crm-url.",
        )
        parser.add_argument(
            "--crm-url",
            type=str,
            default=None,
            help="Optional CRM Shell/Edit URL; id is extracted when --bom-id is omitted.",
        )
        parser.add_argument(
            "--organization-id",
            type=int,
            required=True,
            help="Lithium Organization primary key to import into.",
        )
        parser.add_argument(
            "--parent-part",
            type=str,
            default=None,
            help="Existing Lithium parent part number. If omitted, uses CRM header "
            "parent PN (creates part+revision when missing).",
        )
        parser.add_argument(
            "--html-file",
            type=str,
            default=None,
            help="Offline: path to saved BoM Edit HTML (skips CRM network).",
        )
        parser.add_argument(
            "--json-file",
            type=str,
            default=None,
            help="Offline: path to saved BoM JSON payload (skips CRM network).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and map only; do not write to the database.",
        )

    def handle(self, *args, **options):
        org_id = options["organization_id"]
        try:
            organization = Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Organization id={org_id} not found.") from exc

        try:
            result = run_systemgroup_import(
                organization,
                bom_id=options["bom_id"],
                crm_url=options["crm_url"],
                parent_part_number=options["parent_part"],
                html_path=options["html_file"],
                json_path=options["json_file"],
                dry_run=options["dry_run"],
            )
        except SystemGroupImportError as exc:
            raise CommandError(str(exc)) from exc

        for msg in result.successes:
            self.stdout.write(self.style.SUCCESS(msg))
        for msg in result.warnings:
            self.stdout.write(self.style.WARNING(msg))
        for msg in result.errors:
            self.stderr.write(self.style.ERROR(msg))

        if not result.ok:
            raise CommandError("Import finished with errors.")

        if result.parent_part:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Parent part: {result.parent_part.full_part_number()} "
                    f"(id={result.parent_part.id})"
                )
            )
        self.stdout.write(self.style.SUCCESS("Done."))
