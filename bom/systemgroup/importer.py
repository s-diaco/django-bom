"""Map ParsedBom → Lithium via existing BOMCSVForm (Add all subparts path)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile

from bom.forms import BOMCSVForm
from bom.models import Organization, Part

from .client import SystemGroupClient, SystemGroupClientError, extract_bom_id_from_url
from .parser import (
    BomListEntry,
    BomLine,
    ParsedBom,
    SystemGroupParseError,
    match_bom_list_entries,
    parse_bom_document,
    parse_bom_list_document,
)


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
    resolved_bom_id: str | None = None
    candidates: list[BomListEntry] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class SystemGroupImportError(Exception):
    """User-facing failure before/during SystemGroup import orchestration."""


class AmbiguousBomMatch(SystemGroupImportError):
    """Multiple CRM BoM list rows matched the parent query."""

    def __init__(self, matches: list[BomListEntry], query: str):
        self.matches = matches
        self.query = query
        labels = "; ".join(m.label() for m in matches[:20])
        more = "" if len(matches) <= 20 else f" (+{len(matches) - 20} more)"
        super().__init__(
            f"Multiple CRM BoMs matched '{query}': {labels}{more}. "
            "Pick one BoM id (GUI pick list, --bom-id, or CRM URL)."
        )


class NoBomMatch(SystemGroupImportError):
    """No CRM BoM list row matched the parent query."""

    def __init__(self, query: str):
        self.query = query
        super().__init__(
            f"No CRM BoM on the list matched '{query}'. "
            "Check the parent part number/description, or enter a CRM BoM id / Edit URL."
        )


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


def load_bom_list_entries(
    *,
    client: SystemGroupClient | None = None,
    list_html: str | None = None,
    list_json: str | None = None,
    list_path: str | Path | None = None,
) -> list[BomListEntry]:
    """Load BoM list rows from offline content/path or live CRM fetch."""
    try:
        if list_json is not None:
            return parse_bom_list_document(list_json, content_type="application/json")
        if list_html is not None:
            return parse_bom_list_document(list_html, content_type="text/html")
        if list_path is not None:
            content = Path(list_path).read_text(encoding="utf-8")
            ctype = (
                "application/json"
                if str(list_path).lower().endswith(".json")
                or content.lstrip()[:1] in "{["
                else "text/html"
            )
            return parse_bom_list_document(content, content_type=ctype)
        sg = client or SystemGroupClient()
        body, ctype = sg.fetch_bom_list()
        return parse_bom_list_document(body, content_type=ctype)
    except (SystemGroupClientError, SystemGroupParseError, OSError) as exc:
        raise SystemGroupImportError(str(exc)) from exc


def resolve_bom_from_list(
    *,
    part_number: str | None = None,
    description: str | None = None,
    revision: str | None = None,
    client: SystemGroupClient | None = None,
    list_html: str | None = None,
    list_json: str | None = None,
    list_path: str | Path | None = None,
    entries: list[BomListEntry] | None = None,
) -> BomListEntry:
    """Fetch/parse the CRM BoM list and resolve a single match.

    List rows often expose parent as «کد BOM» = ``part_number/revision``.
    Raises ``NoBomMatch`` or ``AmbiguousBomMatch``. When neither part_number nor
    description is set, returns AmbiguousBomMatch with the full list (browse).
    """
    rows = entries if entries is not None else load_bom_list_entries(
        client=client,
        list_html=list_html,
        list_json=list_json,
        list_path=list_path,
    )
    pn = (part_number or "").strip() or None
    desc = (description or "").strip() or None
    rev = (revision or "").strip() or None
    query = pn or desc or "(all)"
    if pn and rev:
        query = f"{pn}/{rev}"

    if not pn and not desc:
        raise AmbiguousBomMatch(rows, query)

    matches = match_bom_list_entries(
        rows, part_number=pn, description=desc, revision=rev
    )
    if not matches:
        raise NoBomMatch(query)
    if len(matches) > 1:
        raise AmbiguousBomMatch(matches, query)
    return matches[0]


def run_systemgroup_import(
    organization: Organization,
    *,
    bom_id: str | None = None,
    crm_url: str | None = None,
    parent_part_number: str | None = None,
    parent_revision: str | None = None,
    html_content: str | None = None,
    json_content: str | None = None,
    html_path: str | Path | None = None,
    json_path: str | Path | None = None,
    dry_run: bool = False,
    client: SystemGroupClient | None = None,
    from_list: bool = False,
    list_html: str | None = None,
    list_json: str | None = None,
    list_path: str | Path | None = None,
    parent_description: str | None = None,
) -> ImportResult:
    """Shared entry used by the management command and Admin UI.

    Source priority: json_content/path → html_content/path → live CRM fetch by
    bom_id (or id extracted from crm_url / resolved from BoM list). Credentials
    always come from CRM_* env (or an injected ``client``).

    When ``bom_id`` / ``crm_url`` are omitted and ``from_list`` is true (or a
    parent part number is set), the CRM BoM list is fetched and matched by
    parent part number and optional selected ``parent_revision`` (CRM «کد BOM»
    suffix). Revision is never inferred from latest().
    """
    resolved_bom_id = (bom_id or "").strip() or None
    if not resolved_bom_id and crm_url:
        resolved_bom_id = extract_bom_id_from_url(crm_url)

    parent_pn = (parent_part_number or "").strip() or None
    # Explicit selected revision only (e.g. from part/…/rev/…/#bom) — never latest().
    parent_rev = (parent_revision or "").strip() or None
    parent_part = None
    parent_desc = (parent_description or "").strip() or None
    if parent_pn:
        try:
            parent_part = Part.from_part_number(parent_pn, organization)
        except (Part.DoesNotExist, AttributeError) as exc:
            raise SystemGroupImportError(
                f"Parent part '{parent_pn}' not found in this organization."
            ) from exc
        if parent_desc is None and parent_part is not None:
            # Description fallback only when no revision disambiguation was provided.
            if parent_rev is None:
                latest = parent_part.latest()
                if latest is not None and latest.description:
                    parent_desc = latest.description

    offline_edit = any(
        x is not None
        for x in (json_content, json_path, html_content, html_path)
    )
    explicit_list = bool(from_list or list_html or list_json or list_path)
    # Auto-resolve by parent when live-fetching; explicit --from-list / list
    # fixtures also resolve even alongside offline Edit HTML/JSON.
    should_resolve_list = not resolved_bom_id and (
        explicit_list or (bool(parent_pn) and not offline_edit)
    )

    list_entry: BomListEntry | None = None
    if should_resolve_list:
        list_entry = resolve_bom_from_list(
            part_number=parent_pn,
            description=parent_desc if parent_pn else None,
            revision=parent_rev if parent_pn else None,
            client=client,
            list_html=list_html,
            list_json=list_json,
            list_path=list_path,
        )
        resolved_bom_id = list_entry.bom_id

    try:
        if json_content is not None:
            parsed = parse_bom_document(json_content, content_type="application/json")
        elif json_path is not None:
            content = Path(json_path).read_text(encoding="utf-8")
            parsed = parse_bom_document(content, content_type="application/json")
        elif html_content is not None:
            parsed = parse_bom_document(html_content, content_type="text/html")
        elif html_path is not None:
            content = Path(html_path).read_text(encoding="utf-8")
            parsed = parse_bom_document(content, content_type="text/html")
        else:
            if not resolved_bom_id:
                raise SystemGroupImportError(
                    "Provide a BoM id, a CRM Edit URL containing id=, "
                    "a parent part (auto-resolve from CRM list), "
                    "--from-list, or an HTML/JSON upload."
                )
            sg = client or SystemGroupClient()
            body, ctype = sg.fetch_bom(resolved_bom_id)
            parsed = parse_bom_document(body, content_type=ctype)
    except (SystemGroupClientError, SystemGroupParseError, OSError) as exc:
        raise SystemGroupImportError(str(exc)) from exc

    if resolved_bom_id and not parsed.bom_id:
        parsed.bom_id = str(resolved_bom_id)

    result = import_parsed_bom(
        organization,
        parsed,
        parent_part=parent_part,
        parent_part_number=parent_pn,
        dry_run=dry_run,
    )
    result.resolved_bom_id = resolved_bom_id
    if list_entry is not None:
        result.successes.insert(
            0,
            f"Resolved CRM BoM {list_entry.label()} from list.",
        )
    return result
