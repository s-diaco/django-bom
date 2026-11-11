"""Import a SystemGroup PAC Engineering BoM into Lithium.

CLI credentials (env only, never commit):
  CRM_BASE_URL   e.g. http://192.168.3.193/
  CRM_USERNAME
  CRM_PASSWORD

The Admin GUI reads the CRM base URL from Organization settings and
per-user credentials from User settings instead of these env vars.

Examples:
  python manage.py import_systemgroup_bom --bom-id 39477 --organization-id 1
  python manage.py import_systemgroup_bom --parent-part 500-9001-00 --organization-id 1
  python manage.py import_systemgroup_bom --from-list --parent-part 500-9001-00 --organization-id 1
  python manage.py import_systemgroup_bom --html-file ./bom-edit.html --organization-id 1 --parent-part 500-1234-00

Admin UI: Home → Import material (same backend).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from bom.models import Organization
from bom.systemgroup.importer import (
    AmbiguousBomMatch,
    ExistingBomConflict,
    SystemGroupError,
    SystemGroupImportError,
    load_bom_list_entries,
    run_systemgroup_import,
)


class Command(BaseCommand):
    help = (
        "Import a SystemGroup PAC Engineering BoM into Lithium parts/revisions "
        "(reuses CSV BoM / Add-all-subparts semantics). Credentials: CRM_BASE_URL, "
        "CRM_USERNAME, CRM_PASSWORD. Same backend as the Admin Upload UI. "
        "When --bom-id is omitted, resolves from the CRM BoM list via --parent-part "
        "and/or --from-list."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--bom-id",
            type=str,
            default=None,
            help="CRM BoM id (Edit.aspx?id=...). Optional when --parent-part / "
            "--from-list can resolve it from the BoM list.",
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
            help="Existing Lithium parent part number. If --bom-id is omitted, "
            "matches this PN on the CRM BoM list («کد BOM»).",
        )
        parser.add_argument(
            "--parent-revision",
            type=str,
            default=None,
            help="Selected Lithium revision string to match CRM «کد BOM» suffix "
            "(PN/rev). Never inferred from latest — pass the revision you mean.",
        )
        parser.add_argument(
            "--from-list",
            action="store_true",
            help="Resolve BoM id from the CRM BoM list (implied when --parent-part "
            "is set and --bom-id/--crm-url/--html-file/--json-file are omitted). "
            "Without --parent-part, prints matching candidates and exits.",
        )
        parser.add_argument(
            "--list-file",
            type=str,
            default=None,
            help="Offline: path to saved BoM list HTML/JSON (skips list network fetch).",
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
        parser.add_argument(
            "--existing-bom-action",
            type=str,
            choices=("keep", "replace"),
            default=None,
            help="When the target Lithium revision already has a BoM tree: "
            "'keep' appends imported lines; 'replace' clears then imports. "
            "Required in that case (GUI prompts instead).",
        )

    def handle(self, *args, **options):
        org_id = options["organization_id"]
        try:
            organization = Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist as exc:
            raise CommandError(f"Organization id={org_id} not found.") from exc

        # Browse-only: --from-list without parent and without bom id → print list.
        if (
            options["from_list"]
            and not options["parent_part"]
            and not options["bom_id"]
            and not options["crm_url"]
            and not options["html_file"]
            and not options["json_file"]
        ):
            try:
                entries = load_bom_list_entries(list_path=options["list_file"])
            except SystemGroupError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(f"{len(entries)} CRM BoM(s) on list:")
            for entry in entries:
                self.stdout.write(f"  {entry.label()}")
            self.stdout.write(
                "Re-run with --bom-id <id> or --parent-part <pn> to import."
            )
            return

        try:
            result = run_systemgroup_import(
                organization,
                bom_id=options["bom_id"],
                crm_url=options["crm_url"],
                parent_part_number=options["parent_part"],
                parent_revision=options["parent_revision"],
                html_path=options["html_file"],
                json_path=options["json_file"],
                dry_run=options["dry_run"],
                from_list=bool(options["from_list"] or options["list_file"]),
                list_path=options["list_file"],
                existing_bom_action=options["existing_bom_action"],
            )
        except AmbiguousBomMatch as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            for entry in exc.matches:
                self.stdout.write(f"  {entry.label()}")
            raise CommandError(
                "Ambiguous CRM BoM match; pass --bom-id to disambiguate."
            ) from exc
        except ExistingBomConflict as exc:
            raise CommandError(
                f"{exc} Pass --existing-bom-action keep|replace."
            ) from exc
        except SystemGroupError as exc:
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
        if result.resolved_bom_id:
            self.stdout.write(
                self.style.SUCCESS(f"CRM BoM id: {result.resolved_bom_id}")
            )
        self.stdout.write(self.style.SUCCESS("Done."))
