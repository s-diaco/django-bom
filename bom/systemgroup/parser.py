"""Parse SystemGroup login forms and BoM Edit HTML/JSON.

FIXTURE SHAPE (scaffold): Live Edit.aspx markup was unreachable from the cloud
VM. Fixtures under bom/test_files/systemgroup/ define the contract. Replace them
with a saved authenticated BoM Edit HTML (or network JSON) from Diaco, then
tighten selectors / keys — see docs/systemgroup-bom-importer.md.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any


class SystemGroupParseError(ValueError):
    """Raised when login or BoM markup cannot be parsed."""


@dataclass
class LoginFormFields:
    action: str
    method: str
    hidden: dict[str, str]
    username_name: str
    password_name: str
    submit_name: str | None = None
    submit_value: str | None = None


@dataclass
class BomLine:
    part_number: str = ""
    quantity: str = "1"
    revision: str = ""
    description: str = ""
    reference: str = ""
    manufacturer_name: str = ""
    manufacturer_part_number: str = ""
    dnp: str = ""
    level: int = 1

    def as_csv_row(self) -> dict[str, str]:
        return {
            "level": str(self.level),
            "part_number": self.part_number.strip(),
            "quantity": self.quantity.strip() or "1",
            "revision": self.revision.strip(),
            "description": self.description.strip() or self.part_number.strip() or "Imported from SystemGroup",
            "reference": self.reference.strip(),
            "manufacturer_name": self.manufacturer_name.strip(),
            "manufacturer_part_number": self.manufacturer_part_number.strip(),
            "dnp": self.dnp.strip(),
        }


@dataclass
class ParsedBom:
    bom_id: str | None = None
    parent_part_number: str = ""
    parent_revision: str = ""
    parent_description: str = ""
    lines: list[BomLine] = field(default_factory=list)
    source: str = "unknown"


# --- Login form ---------------------------------------------------------------

_USER_NAME_HINTS = ("user", "login", "email", "uid", "account")
_PASS_NAME_HINTS = ("pass", "pwd")
_SUBMIT_HINTS = ("login", "submit", "signin", "logon")


class _LoginFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form":
            self._current = {
                "action": ad.get("action", ""),
                "method": (ad.get("method") or "post").lower(),
                "inputs": [],
            }
        elif tag == "input" and self._current is not None:
            self._current["inputs"].append(
                {
                    "type": (ad.get("type") or "text").lower(),
                    "name": ad.get("name", ""),
                    "value": ad.get("value", ""),
                    "id": ad.get("id", ""),
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._current is not None:
            self.forms.append(self._current)
            self._current = None


def parse_login_form(html: str) -> LoginFormFields:
    """Extract ASP.NET forms-auth fields from a Login.aspx HTML body."""
    parser = _LoginFormParser()
    parser.feed(html)
    if not parser.forms:
        raise SystemGroupParseError("No <form> found in login HTML.")

    # Prefer the form that has both a password input and a text/email username.
    chosen = None
    for form in parser.forms:
        types = {i["type"] for i in form["inputs"]}
        if "password" in types and types & {"text", "email", ""}:
            chosen = form
            break
    if chosen is None:
        chosen = parser.forms[0]

    hidden: dict[str, str] = {}
    username_name = ""
    password_name = ""
    submit_name = None
    submit_value = None

    for inp in chosen["inputs"]:
        name = inp["name"]
        if not name:
            continue
        itype = inp["type"]
        if itype == "hidden":
            hidden[name] = inp["value"]
        elif itype == "password" and not password_name:
            password_name = name
        elif itype in ("text", "email") and not username_name:
            lname = name.lower()
            if any(h in lname for h in _USER_NAME_HINTS) or not username_name:
                username_name = name
        elif itype in ("submit", "button", "image"):
            lname = name.lower()
            lval = (inp["value"] or "").lower()
            if any(h in lname or h in lval for h in _SUBMIT_HINTS) or submit_name is None:
                submit_name = name
                submit_value = inp["value"] or "Login"

    # Fallback: first non-hidden text-like input as username
    if not username_name:
        for inp in chosen["inputs"]:
            if inp["type"] in ("text", "email") and inp["name"]:
                username_name = inp["name"]
                break

    if not username_name or not password_name:
        raise SystemGroupParseError(
            "Could not locate username/password fields on login form. "
            "Save Login.aspx HTML and update parse_login_form()."
        )

    # Prefer password-hinted name if we grabbed a non-user text field first
    if not any(h in username_name.lower() for h in _USER_NAME_HINTS):
        for inp in chosen["inputs"]:
            if inp["type"] in ("text", "email") and any(
                h in inp["name"].lower() for h in _USER_NAME_HINTS
            ):
                username_name = inp["name"]
                break

    if password_name and any(h in password_name.lower() for h in _PASS_NAME_HINTS):
        pass  # good
    else:
        for inp in chosen["inputs"]:
            if inp["type"] == "password" and inp["name"]:
                password_name = inp["name"]
                break

    return LoginFormFields(
        action=chosen["action"],
        method=chosen["method"] or "post",
        hidden=hidden,
        username_name=username_name,
        password_name=password_name,
        submit_name=submit_name,
        submit_value=submit_value,
    )


# --- BoM document -------------------------------------------------------------

_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "part_number": (
        "part_number",
        "part number",
        "part no",
        "partno",
        "code",
        "code_material",
        "item",
        "item code",
        "شماره قطعه",
    ),
    "quantity": ("quantity", "qty", "count", "qty.", "تعداد"),
    "revision": ("revision", "rev", "rev.", "نسخه"),
    "description": ("description", "desc", "name", "name_material", "شرح", "توضیحات"),
    "reference": ("reference", "references", "designator", "designators", "ref", "مرجع"),
    "manufacturer_name": ("manufacturer", "manufacturer_name", "mfr", "mfg", "سازنده"),
    "manufacturer_part_number": (
        "manufacturer_part_number",
        "mpn",
        "mfg_part_number",
        "manufacturer part number",
        "کد سازنده",
    ),
    "dnp": ("dnp", "dnl", "do_not_load", "do not load", "do not populate"),
    "level": ("level", "lvl", "indent"),
}


def _normalize_header(raw: str) -> str | None:
    key = re.sub(r"\s+", " ", (raw or "").strip().lower())
    key = key.replace("-", " ").replace("_", " ")
    compact = key.replace(" ", "")
    for field_name, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            a = alias.lower().replace("_", " ")
            if key == a or compact == a.replace(" ", ""):
                return field_name
    return None


def _line_from_mapping(data: dict[str, Any], default_level: int = 1) -> BomLine:
    normalized: dict[str, str] = {}
    for k, v in data.items():
        field_name = _normalize_header(str(k))
        if field_name:
            normalized[field_name] = "" if v is None else str(v).strip()
    level_raw = normalized.get("level", "")
    try:
        level = int(float(level_raw)) if level_raw else default_level
    except ValueError:
        level = default_level
    return BomLine(
        part_number=normalized.get("part_number", ""),
        quantity=normalized.get("quantity", "1") or "1",
        revision=normalized.get("revision", ""),
        description=normalized.get("description", ""),
        reference=normalized.get("reference", ""),
        manufacturer_name=normalized.get("manufacturer_name", ""),
        manufacturer_part_number=normalized.get("manufacturer_part_number", ""),
        dnp=normalized.get("dnp", ""),
        level=level,
    )


class _BomTableParser(HTMLParser):
    """Collect tables; caller picks the best BoM-looking one."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict[str, Any]] = []
        self.meta: dict[str, str] = {}
        self._in_table = False
        self._in_tr = False
        self._in_cell = False
        self._cell_tag = ""
        self._cell_text: list[str] = []
        self._row_cells: list[tuple[str, str]] = []  # (tag, text)
        self._current_table: dict[str, Any] | None = None
        self._capture_meta_name: str | None = None
        self._meta_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag == "table":
            self._in_table = True
            self._current_table = {
                "id": ad.get("id", ""),
                "class": ad.get("class", ""),
                "rows": [],
            }
        elif self._in_table and tag == "tr":
            self._in_tr = True
            self._row_cells = []
        elif self._in_table and self._in_tr and tag in ("td", "th"):
            self._in_cell = True
            self._cell_tag = tag
            self._cell_text = []
        elif tag in ("span", "div", "td", "input") and ad.get("data-bom-field"):
            self._capture_meta_name = ad["data-bom-field"]
            self._meta_buf = []
            if tag == "input" and ad.get("value"):
                self.meta[ad["data-bom-field"]] = ad["value"]
                self._capture_meta_name = None

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_cell:
            text = re.sub(r"\s+", " ", "".join(self._cell_text)).strip()
            self._row_cells.append((self._cell_tag, text))
            self._in_cell = False
        elif tag == "tr" and self._in_tr:
            if self._row_cells and self._current_table is not None:
                self._current_table["rows"].append(self._row_cells)
            self._in_tr = False
        elif tag == "table" and self._in_table:
            if self._current_table is not None:
                self.tables.append(self._current_table)
            self._current_table = None
            self._in_table = False
        if self._capture_meta_name and tag in ("span", "div", "td"):
            self.meta[self._capture_meta_name] = re.sub(
                r"\s+", " ", "".join(self._meta_buf)
            ).strip()
            self._capture_meta_name = None

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)
        if self._capture_meta_name:
            self._meta_buf.append(data)


_JSON_PATTERNS = (
    re.compile(
        r"(?:var\s+|window\.)?(?:bomData|bomLines|BomLines|gridData)\s*=\s*(\{.*?\}|\[.*?\])\s*;",
        re.DOTALL | re.IGNORECASE,
    ),
    re.compile(
        r'<script[^>]*type=["\']application/json["\'][^>]*id=["\']bom-data["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    ),
)


def _parse_bom_json_blob(text: str) -> ParsedBom | None:
    text = text.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return _parsed_bom_from_json(data, source="json")


def _parsed_bom_from_json(data: Any, source: str = "json") -> ParsedBom:
    bom = ParsedBom(source=source)
    lines_raw: list[Any] = []
    if isinstance(data, list):
        lines_raw = data
    elif isinstance(data, dict):
        bom.bom_id = (
            str(data["bom_id"]) if data.get("bom_id") is not None else None
        ) or (str(data["id"]) if data.get("id") is not None else None)
        parent = data.get("parent") or data.get("header") or {}
        if isinstance(parent, dict):
            bom.parent_part_number = str(
                parent.get("part_number")
                or parent.get("partNumber")
                or parent.get("code")
                or ""
            )
            bom.parent_revision = str(parent.get("revision") or parent.get("rev") or "")
            bom.parent_description = str(
                parent.get("description") or parent.get("name") or ""
            )
        else:
            bom.parent_part_number = str(
                data.get("parent_part_number") or data.get("part_number") or ""
            )
            bom.parent_revision = str(data.get("parent_revision") or data.get("revision") or "")
            bom.parent_description = str(
                data.get("parent_description") or data.get("description") or ""
            )
        for key in ("lines", "items", "rows", "data", "BomLines"):
            if isinstance(data.get(key), list):
                lines_raw = data[key]
                break
    for item in lines_raw:
        if not isinstance(item, dict):
            continue
        line = _line_from_mapping(item)
        if line.part_number or line.manufacturer_part_number:
            bom.lines.append(line)
    if not bom.lines:
        raise SystemGroupParseError("JSON BoM contained no usable line items.")
    return bom


def _score_table(table: dict[str, Any]) -> int:
    score = 0
    tid = (table.get("id") or "").lower()
    tclass = (table.get("class") or "").lower()
    if any(x in tid or x in tclass for x in ("bom", "grid", "lines", "items")):
        score += 5
    rows = table.get("rows") or []
    if not rows:
        return score
    header_cells = [c[1] for c in rows[0]]
    mapped = sum(1 for h in header_cells if _normalize_header(h))
    score += mapped * 2
    if mapped >= 2:
        score += 3
    score += min(len(rows), 20)
    return score


def _parse_bom_html(html: str) -> ParsedBom:
    # Prefer embedded JSON if present (common for ASP.NET grids / SPA shells).
    for pattern in _JSON_PATTERNS:
        match = pattern.search(html)
        if match:
            blob = match.group(1)
            parsed = _parse_bom_json_blob(blob)
            if parsed and parsed.lines:
                parsed.source = "html-embedded-json"
                return parsed

    parser = _BomTableParser()
    parser.feed(html)
    if not parser.tables:
        raise SystemGroupParseError(
            "No BoM table or embedded JSON found. Save Edit.aspx HTML and update parser."
        )

    best = max(parser.tables, key=_score_table)
    rows = best["rows"]
    if len(rows) < 2:
        raise SystemGroupParseError("BoM table has no data rows.")

    header_map: list[str | None] = [_normalize_header(c[1]) for c in rows[0]]
    if sum(1 for h in header_map if h) < 2:
        raise SystemGroupParseError(
            "BoM table headers not recognized. Expected columns like "
            "part_number, quantity, description. Update _HEADER_ALIASES or fixture."
        )

    bom = ParsedBom(source="html-table")
    if parser.meta.get("bom_id"):
        bom.bom_id = parser.meta["bom_id"]
    bom.parent_part_number = parser.meta.get("parent_part_number", "")
    bom.parent_revision = parser.meta.get("parent_revision", "")
    bom.parent_description = parser.meta.get("parent_description", "")

    for row in rows[1:]:
        cells = [c[1] for c in row]
        mapping: dict[str, str] = {}
        for idx, field_name in enumerate(header_map):
            if field_name and idx < len(cells):
                mapping[field_name] = cells[idx]
        line = _line_from_mapping(mapping)
        if line.part_number or line.manufacturer_part_number:
            bom.lines.append(line)

    if not bom.lines:
        raise SystemGroupParseError("BoM table parsed but no line items extracted.")
    return bom


def parse_bom_document(content: str, content_type: str | None = None) -> ParsedBom:
    """Parse a BoM Edit HTML page or JSON payload into ParsedBom."""
    stripped = (content or "").strip()
    if not stripped:
        raise SystemGroupParseError("Empty BoM document.")

    ctype = (content_type or "").lower()
    looks_json = stripped[0] in "{[" or "json" in ctype
    if looks_json:
        try:
            return _parsed_bom_from_json(json.loads(stripped), source="json")
        except json.JSONDecodeError:
            if "json" in ctype:
                raise SystemGroupParseError("Invalid BoM JSON.") from None
            # fall through to HTML

    return _parse_bom_html(stripped)
