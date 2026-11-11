"""Re-export SystemGroup CRM client from lithium-systemgroup."""

from lithium_systemgroup.client import (  # noqa: F401
    DEFAULT_BOM_EDIT_PAGE,
    DEFAULT_BOM_LIST_PAGE,
    DEFAULT_LOGIN_PATH,
    SystemGroupClient,
    SystemGroupClientError,
    bom_edit_direct_url,
    bom_edit_url,
    bom_list_direct_url,
    bom_list_url,
    credentials_from_env,
    extract_bom_id_from_url,
    rewrite_url_host,
)

__all__ = [
    "DEFAULT_BOM_EDIT_PAGE",
    "DEFAULT_BOM_LIST_PAGE",
    "DEFAULT_LOGIN_PATH",
    "SystemGroupClient",
    "SystemGroupClientError",
    "bom_edit_direct_url",
    "bom_edit_url",
    "bom_list_direct_url",
    "bom_list_url",
    "credentials_from_env",
    "extract_bom_id_from_url",
    "rewrite_url_host",
]
