"""Import a SystemGroup PAC Engineering BoM into Lithium.

Credentials (env only, never commit):
  CRM_BASE_URL   e.g. http://192.168.3.193/
  CRM_USERNAME
  CRM_PASSWORD

Examples:
  python manage.py import_systemgroup_bom --bom-id 39477 --organization-id 1
  python manage.py import_systemgroup_bom --html-file ./bom-edit.html --organization-id 1 --parent-part 500-1234-00
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bom.models import Organization, Part
from bom.systemgroup.client import SystemGroupClient, SystemGroupClientError
from bom.systemgroup.importer import import_parsed_bom
from bom.systemgroup.parser import SystemGroupParseError, parse_bom_document


class Command(BaseCommand):
    help = (
        "Import a SystemGroup PAC Engineering BoM into Lithium parts/revisions "
        "(reuses CSV BoM / Add-all-subparts semantics). Credentials: CRM_BASE_URL, "
        "CRM_USERNAME, CRM_PASSWORD."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--bom-id",
            type=str,
            default=None,
            help="CRM BoM id (Edit.aspx?id=...). Required unless --html-file/--json-file.",
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

        html_file = options["html_file"]
        json_file = options["json_file"]
        bom_id = options["bom_id"]
        dry_run = options["dry_run"]
        parent_pn = options["parent_part"]

        if not html_file and not json_file and not bom_id:
            raise CommandError("Provide --bom-id, or --html-file / --json-file.")

        parent_part = None
        if parent_pn:
            try:
                parent_part = Part.from_part_number(parent_pn, organization)
            except (Part.DoesNotExist, AttributeError) as exc:
                raise CommandError(
                    f"Parent part '{parent_pn}' not found in organization {org_id}."
                ) from exc

        try:
            if json_file:
                content = Path(json_file).read_text(encoding="utf-8")
                parsed = parse_bom_document(content, content_type="application/json")
            elif html_file:
                content = Path(html_file).read_text(encoding="utf-8")
                parsed = parse_bom_document(content, content_type="text/html")
            else:
                client = SystemGroupClient()
                body, ctype = client.fetch_bom(bom_id)
                parsed = parse_bom_document(body, content_type=ctype)
        except (SystemGroupClientError, SystemGroupParseError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        if bom_id and not parsed.bom_id:
            parsed.bom_id = str(bom_id)

        self.stdout.write(
            f"Parsed BoM id={parsed.bom_id or '?'} source={parsed.source} "
            f"lines={len(parsed.lines)} parent_crm={parsed.parent_part_number or '-'}"
        )

        result = import_parsed_bom(
            organization,
            parsed,
            parent_part=parent_part,
            parent_part_number=parent_pn,
            dry_run=dry_run,
        )

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
