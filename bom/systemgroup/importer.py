"""Map ParsedBom → Lithium via existing BOMCSVForm (Add all subparts path)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile

from bom.forms import BOMCSVForm
from bom.models import Assembly, Organization, Part, PartRevision

from lithium_systemgroup import (
    AmbiguousBomMatch,
    BomListEntry,
    BomLine,
    NoBomMatch,
    ParsedBom,
    SystemGroupClient,
    SystemGroupClientError,
    SystemGroupError,
    SystemGroupParseError,
    extract_bom_id_from_url,
    list_revisions_for_part,
    load_bom_list_entries,
    parse_bom_document,
    resolve_bom_from_list,
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


class SystemGroupImportError(SystemGroupError):
    """User-facing failure before/during SystemGroup import orchestration."""


class ExistingBomConflict(SystemGroupImportError):
    """Target Lithium revision already has a BoM tree; user must keep or replace."""

    def __init__(self, part: Part, part_revision: PartRevision, subpart_count: int):
        self.part = part
        self.part_revision = part_revision
        self.subpart_count = subpart_count
        pn = part.full_part_number()
        rev = part_revision.revision
        super().__init__(
            f"Part {pn} revision {rev} already has {subpart_count} BoM line(s). "
            "Choose keep (append) or replace."
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


def _revision_subpart_count(part_revision: PartRevision | None) -> int:
    if part_revision is None or part_revision.assembly_id is None:
        return 0
    return part_revision.assembly.subparts.count()


def first_product_type_code(organization: Organization, *, has_bom: bool) -> str | None:
    """Return the first org product-type code with the given has_bom flag."""
    organization.ensure_default_product_types()
    for pt in organization.product_types.all():
        if pt.has_bom is has_bom:
            return pt.code
    return None


def ensure_parent_revision(
    organization: Organization,
    *,
    part: Part,
    revision: str,
    description: str = "",
    material: str | None = None,
) -> PartRevision:
    """Return existing PartRevision or create one (with empty assembly)."""
    rev = (revision or "").strip() or "1"
    existing = PartRevision.objects.filter(part=part, revision=rev).first()
    if existing is not None:
        return existing
    assembly = Assembly.objects.create()
    kwargs = {
        "part": part,
        "revision": rev,
        "description": (description or "").strip() or part.full_part_number(),
        "assembly": assembly,
    }
    if material:
        kwargs["material"] = material
    return PartRevision.objects.create(**kwargs)


def import_parsed_bom(
    organization: Organization,
    parsed: ParsedBom,
    *,
    parent_part: Part | None = None,
    parent_part_number: str | None = None,
    parent_revision: str | None = None,
    existing_bom_action: str | None = None,
    material: str | None = None,
    dry_run: bool = False,
) -> ImportResult:
    """Import ParsedBom using BOMCSVForm (same semantics as part-upload-bom).

    Resolution order for parent:
    1. Explicit ``parent_part`` instance (+ optional ``parent_revision``)
    2. ``parent_part_number`` / ``parsed.parent_part_number`` looked up in Lithium
    3. If part exists but revision does not, create the revision
    4. If part is missing, emit level-0 CSV so BOMCSVForm creates part+revision
    5. If the target revision already has a BoM tree and ``existing_bom_action``
       is unset, raise ``ExistingBomConflict`` (keep vs replace)
    """
    result = ImportResult(dry_run=dry_run)
    if not parsed.lines:
        result.errors.append("Parsed BoM has no line items.")
        return result

    resolved = parent_part
    # Explicit UI/CLI parent wins over CRM header values.
    explicit_pn = (parent_part_number or "").strip() or None
    explicit_rev = (parent_revision or "").strip() or None
    pn = explicit_pn or (parsed.parent_part_number or "").strip() or None
    rev = explicit_rev or (parsed.parent_revision or "").strip() or None
    if explicit_pn:
        parsed.parent_part_number = explicit_pn
    elif pn and not parsed.parent_part_number:
        parsed.parent_part_number = pn
    if explicit_rev:
        parsed.parent_revision = explicit_rev
    elif rev and not parsed.parent_revision:
        parsed.parent_revision = rev
    if resolved is None and pn:
        resolved = resolve_parent_part(organization, pn)

    parent_part_revision: PartRevision | None = None
    include_parent_row = False
    action = (existing_bom_action or "").strip().lower() or None
    # Dropdown material is for the parent only; new children use first raw type.
    parent_material = (material or "").strip() or None
    child_material = first_product_type_code(organization, has_bom=False)

    if resolved is not None:
        # Part exists — use/create the requested revision (default latest or "1").
        target_rev = rev or (
            resolved.latest().revision if resolved.latest() is not None else "1"
        )
        parent_part_revision = ensure_parent_revision(
            organization,
            part=resolved,
            revision=target_rev,
            description=parsed.parent_description or "",
            material=parent_material,
        )
        count = _revision_subpart_count(parent_part_revision)
        if count > 0 and action not in ("keep", "replace"):
            if dry_run:
                result.warnings.append(
                    f"Dry run: {resolved.full_part_number()} rev "
                    f"{parent_part_revision.revision} already has {count} "
                    "BoM line(s); a real import would ask keep vs replace."
                )
            else:
                raise ExistingBomConflict(resolved, parent_part_revision, count)
        if (
            not dry_run
            and action == "replace"
            and parent_part_revision.assembly_id
        ):
            parent_part_revision.assembly.subparts.all().delete()
            parent_part_revision.clear_bom_unit_cost_cache()
            result.warnings.append(
                f"Replaced existing BoM on {resolved.full_part_number()} "
                f"rev {parent_part_revision.revision}."
            )
        elif action == "keep" and count > 0:
            result.warnings.append(
                f"Keeping existing BoM on {resolved.full_part_number()} "
                f"rev {parent_part_revision.revision}; new lines will append."
            )
    else:
        # Missing part — BOMCSVForm creates from a level-0 parent row.
        if not parsed.parent_part_number:
            result.errors.append(
                "No parent part: enter Part ID + Revision, or ensure the CRM BoM "
                "header includes a parent part number so one can be created."
            )
            return result
        if not parsed.parent_revision:
            parsed.parent_revision = rev or "1"
        include_parent_row = True

    csv_bytes = parsed_bom_to_csv_bytes(parsed, include_parent_row=include_parent_row)
    result.row_count = len(parsed.lines) + (1 if include_parent_row else 0)

    if dry_run:
        where = (
            f"create parent {parsed.parent_part_number}/{parsed.parent_revision}"
            if include_parent_row
            else (
                f"under {resolved.full_part_number()} "
                f"rev {parent_part_revision.revision if parent_part_revision else '?'}"
            )
        )
        result.successes.append(
            f"Dry run: would import {len(parsed.lines)} line(s) ({where})."
        )
        result.parent_part = resolved
        return result

    upload = SimpleUploadedFile("systemgroup_bom.csv", csv_bytes, content_type="text/csv")
    form = BOMCSVForm(
        data={},
        files={"file": upload},
        parent_part=resolved if not include_parent_row else None,
        parent_part_revision=parent_part_revision if not include_parent_row else None,
        organization=organization,
        parent_material=parent_material if include_parent_row else None,
        default_material=child_material,
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
    user_meta=None,
    from_list: bool = False,
    list_html: str | None = None,
    list_json: str | None = None,
    list_path: str | Path | None = None,
    parent_description: str | None = None,
    existing_bom_action: str | None = None,
    material: str | None = None,
) -> ImportResult:
    """Shared entry used by the management command and Admin UI.

    Source priority: json_content/path → html_content/path → live CRM fetch by
    bom_id (or id extracted from crm_url / resolved from BoM list).

    Live credentials: injected ``client``, else ``user_meta`` (GUI per-user
    username/password + organization CRM base URL), else CRM_* env (CLI).

    When ``bom_id`` / ``crm_url`` are omitted and ``from_list`` is true (or a
    parent part number is set), the CRM BoM list is fetched and matched by
    parent part number and optional selected ``parent_revision`` (CRM «کد BOM»
    suffix). Missing Lithium parts/revisions are created. If the target
    revision already has a BoM tree, ``existing_bom_action`` must be
    ``keep`` or ``replace`` (else ``ExistingBomConflict``).
    """
    from .access import client_for_user_meta

    resolved_bom_id = (bom_id or "").strip() or None
    if not resolved_bom_id and crm_url:
        resolved_bom_id = extract_bom_id_from_url(crm_url)

    parent_pn = (parent_part_number or "").strip() or None
    # Explicit selected revision only — never latest() for CRM list matching.
    parent_rev = (parent_revision or "").strip() or None
    parent_part = None
    parent_desc = (parent_description or "").strip() or None
    if parent_pn:
        parent_part = resolve_parent_part(organization, parent_pn)
        if parent_desc is None and parent_part is not None and parent_rev is None:
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

    def ensure_client() -> SystemGroupClient:
        nonlocal client
        if client is None:
            try:
                if user_meta is not None:
                    client = client_for_user_meta(user_meta)
                else:
                    client = SystemGroupClient()
            except SystemGroupClientError as exc:
                # Surface as ImportError so GUI/CLI catch one exception type.
                raise SystemGroupImportError(str(exc)) from exc
        return client

    list_entry: BomListEntry | None = None
    try:
        if should_resolve_list:
            needs_live_list = (
                list_html is None and list_json is None and list_path is None
            )
            list_entry = resolve_bom_from_list(
                part_number=parent_pn,
                description=parent_desc if parent_pn else None,
                revision=parent_rev if parent_pn else None,
                client=ensure_client() if needs_live_list else client,
                list_html=list_html,
                list_json=list_json,
                list_path=list_path,
            )
            resolved_bom_id = list_entry.bom_id
            # Prefer list-row PN/rev when the user only typed a bare PN.
            if not parent_pn and list_entry.part_number:
                parent_pn = list_entry.part_number
            if not parent_rev and list_entry.revision:
                parent_rev = list_entry.revision

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
                    "Provide Part ID + Revision, a BoM id / Edit URL, "
                    "--from-list, or an HTML/JSON upload."
                )
            body, ctype = ensure_client().fetch_bom(resolved_bom_id)
            parsed = parse_bom_document(body, content_type=ctype)
    except (SystemGroupClientError, SystemGroupParseError, OSError) as exc:
        raise SystemGroupImportError(str(exc)) from exc

    if resolved_bom_id and not parsed.bom_id:
        parsed.bom_id = str(resolved_bom_id)
    if parent_pn and not parsed.parent_part_number:
        parsed.parent_part_number = parent_pn
    if parent_rev and not parsed.parent_revision:
        parsed.parent_revision = parent_rev

    result = import_parsed_bom(
        organization,
        parsed,
        parent_part=parent_part,
        parent_part_number=parent_pn,
        parent_revision=parent_rev,
        existing_bom_action=existing_bom_action,
        material=material,
        dry_run=dry_run,
    )
    result.resolved_bom_id = resolved_bom_id
    if list_entry is not None:
        result.successes.insert(
            0,
            f"Resolved CRM BoM {list_entry.label()} from list.",
        )
    return result
