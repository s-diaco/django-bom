"""SystemGroup PAC Engineering BoM import (CRM → Lithium).

CRM client/parsers live in the standalone ``lithium-systemgroup`` package.
This module keeps Lithium-specific import orchestration and thin re-exports.
"""

from lithium_systemgroup import (
    BomListEntry,
    ParsedBom,
    SystemGroupClient,
    SystemGroupClientError,
    SystemGroupError,
    build_hashed_password,
    extract_bom_id_from_url,
    match_bom_list_entries,
    parse_bom_document,
    parse_bom_list_document,
    parse_login_form,
    unicode_correct_invalid_characters,
)

from .importer import (
    AmbiguousBomMatch,
    ImportResult,
    NoBomMatch,
    SystemGroupImportError,
    import_parsed_bom,
    list_revisions_for_part,
    load_bom_list_entries,
    resolve_bom_from_list,
    run_systemgroup_import,
)

__all__ = [
    "AmbiguousBomMatch",
    "BomListEntry",
    "SystemGroupClient",
    "SystemGroupClientError",
    "SystemGroupError",
    "SystemGroupImportError",
    "NoBomMatch",
    "ImportResult",
    "extract_bom_id_from_url",
    "import_parsed_bom",
    "list_revisions_for_part",
    "load_bom_list_entries",
    "match_bom_list_entries",
    "parse_bom_list_document",
    "resolve_bom_from_list",
    "run_systemgroup_import",
    "ParsedBom",
    "parse_bom_document",
    "parse_login_form",
    "build_hashed_password",
    "unicode_correct_invalid_characters",
]
