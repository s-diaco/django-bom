"""Map ParsedBom → Lithium via existing BOMCSVForm (Add all subparts path)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from django.core.files.uploadedfile import SimpleUploadedFile

from bom.forms import BOMCSVForm
from bom.models import Organization, Part

from .parser import BomLine, ParsedBom


CSV_COLUMNS = [
    "level",
    "part_number",
    "quantity",
    "revision",
    "description",
    "reference",
    "manufacturer_name",
    "manufacturer_part_number",
    "dnp",
]


@dataclass
class ImportResult:
    successes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    parent_part: Part | None = None
    dry_run: bool = False
    row_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def parsed_bom_to_csv_bytes(
    parsed: ParsedBom,
    *,
    include_parent_row: bool,
) -> bytes:
    """Serialize ParsedBom lines to the CSV shape BOMCSVForm expects."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    if include_parent_row and parsed.parent_part_number:
        parent = BomLine(
            part_number=parsed.parent_part_number,
            quantity="1",
            revision=parsed.parent_revision or "1",
            description=parsed.parent_description
            or parsed.parent_part_number
            or "SystemGroup BoM parent",
            level=0,
        )
        writer.writerow(parent.as_csv_row())

    for line in parsed.lines:
        row = line.as_csv_row()
        if include_parent_row and parsed.parent_part_number:
            # Keep relative indent under synthetic level-0 parent
            try:
                lvl = int(row["level"])
            except ValueError:
                lvl = 1
            if lvl < 1:
                lvl = 1
            row["level"] = str(lvl)
        elif not include_parent_row:
            row["level"] = "1"
        writer.writerow(row)

    return buf.getvalue().encode("utf-8")


def resolve_parent_part(
    organization: Organization,
    parent_part_number: str | None,
) -> Part | None:
    if not parent_part_number:
        return None
    try:
        return Part.from_part_number(parent_part_number.strip(), organization)
    except (Part.DoesNotExist, AttributeError):
        return None


def import_parsed_bom(
    organization: Organization,
    parsed: ParsedBom,
    *,
    parent_part: Part | None = None,
    parent_part_number: str | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """Import ParsedBom using BOMCSVForm (same semantics as part-upload-bom).

    Resolution order for parent:
    1. Explicit ``parent_part`` instance
    2. ``parent_part_number`` / ``parsed.parent_part_number`` looked up in Lithium
    3. If still missing but CRM header has a parent PN, emit level-0 CSV row so
       BOMCSVForm creates part+revision, then attaches children under it
    """
    result = ImportResult(dry_run=dry_run)
    if not parsed.lines:
        result.errors.append("Parsed BoM has no line items.")
        return result

    resolved = parent_part
    pn = parent_part_number or parsed.parent_part_number or None
    if resolved is None and pn:
        resolved = resolve_parent_part(organization, pn)

    include_parent_row = resolved is None and bool(parsed.parent_part_number)
    if resolved is None and not include_parent_row:
        result.errors.append(
            "No parent part: pass --parent-part, or ensure the CRM BoM header "
            "includes a parent part number so one can be created."
        )
        return result

    csv_bytes = parsed_bom_to_csv_bytes(parsed, include_parent_row=include_parent_row)
    result.row_count = len(parsed.lines) + (1 if include_parent_row else 0)

    if dry_run:
        result.successes.append(
            f"Dry run: would import {len(parsed.lines)} line(s) "
            f"({'create parent ' + parsed.parent_part_number if include_parent_row else 'under ' + (resolved.full_part_number() if resolved else '?')})."
        )
        result.parent_part = resolved
        return result

    upload = SimpleUploadedFile("systemgroup_bom.csv", csv_bytes, content_type="text/csv")
    form = BOMCSVForm(
        data={},
        files={"file": upload},
        parent_part=resolved,
        organization=organization,
    )
    if form.is_valid():
        result.successes.extend(form.successes)
        result.warnings.extend(form.warnings)
        if resolved is not None:
            result.parent_part = resolved
        elif parsed.parent_part_number:
            result.parent_part = resolve_parent_part(
                organization, parsed.parent_part_number
            )
    else:
        # BOMCSVForm stores row errors as non-field / field errors
        for err in form.errors.get("__all__", form.errors.get(None, [])):
            result.errors.append(str(err))
        for field_name, errs in form.errors.items():
            if field_name in (None, "__all__"):
                continue
            for err in errs:
                result.errors.append(f"{field_name}: {err}")
        if not result.errors:
            result.errors.append(str(form.errors))
        # Partial successes still useful to surface
        if getattr(form, "successes", None):
            result.successes.extend(form.successes)
        if getattr(form, "warnings", None):
            result.warnings.extend(form.warnings)

    return result
