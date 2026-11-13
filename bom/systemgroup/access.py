"""Who may use SystemGroup BoM import (org flag + CRM URL + per-user credentials)."""

from __future__ import annotations

from .client import SystemGroupClient, SystemGroupClientError


def normalize_crm_base_url(raw: str) -> str:
    base = (raw or "").strip()
    if not base:
        return ""
    if not base.endswith("/"):
        base += "/"
    return base


def crm_base_url_from_organization(organization) -> str:
    """CRM host comes from Organization settings (not server env)."""
    if organization is None:
        raise SystemGroupClientError(
            "Missing SystemGroup CRM base URL. Set it under "
            "Settings → Organization."
        )
    base = normalize_crm_base_url(
        getattr(organization, "systemgroup_crm_base_url", None) or ""
    )
    if not base:
        raise SystemGroupClientError(
            "Missing SystemGroup CRM base URL. Set it under "
            "Settings → Organization."
        )
    return base


def user_meta_has_systemgroup_credentials(user_meta) -> bool:
    if user_meta is None:
        return False
    username = (getattr(user_meta, "systemgroup_username", None) or "").strip()
    password = getattr(user_meta, "systemgroup_password", None) or ""
    return bool(username and password)


def organization_systemgroup_import_enabled(organization) -> bool:
    return bool(
        organization is not None
        and getattr(organization, "systemgroup_import_enabled", False)
    )


def organization_has_systemgroup_crm_base_url(organization) -> bool:
    return bool(
        organization is not None
        and normalize_crm_base_url(
            getattr(organization, "systemgroup_crm_base_url", None) or ""
        )
    )


def user_can_access_systemgroup_import(user) -> bool:
    """True when an admin may open Import (org flag + CRM URL; credentials optional)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    profile = user.bom_profile()
    if profile.role != "A":
        return False
    org = profile.organization
    if not organization_systemgroup_import_enabled(org):
        return False
    if not organization_has_systemgroup_crm_base_url(org):
        return False
    return True


def user_can_import_systemgroup(user) -> bool:
    """True when org enables import, CRM URL is set, and CRM user/pass are set."""
    if not user_can_access_systemgroup_import(user):
        return False
    return user_meta_has_systemgroup_credentials(user.bom_profile())


def save_systemgroup_credentials(user_meta, username: str, password: str) -> None:
    """Persist CRM username/password on UserMeta (same fields as before)."""
    username = (username or "").strip()
    if not username or not password:
        raise SystemGroupClientError(
            "SystemGroup username and password are required."
        )
    user_meta.systemgroup_username = username
    user_meta.systemgroup_password = password
    user_meta.save(
        update_fields=["systemgroup_username", "systemgroup_password"]
    )


def clear_systemgroup_credentials(user_meta) -> None:
    """Clear saved CRM credentials (SystemGroup logout)."""
    user_meta.systemgroup_username = ""
    user_meta.systemgroup_password = ""
    user_meta.save(
        update_fields=["systemgroup_username", "systemgroup_password"]
    )


def login_systemgroup_credentials(user_meta, username: str, password: str) -> None:
    """Verify CRM login, then store credentials on UserMeta."""
    username = (username or "").strip()
    if not username or not password:
        raise SystemGroupClientError(
            "SystemGroup username and password are required."
        )
    organization = getattr(user_meta, "organization", None)
    client = SystemGroupClient(
        base_url=crm_base_url_from_organization(organization),
        username=username,
        password=password,
    )
    client.login()
    save_systemgroup_credentials(user_meta, username, password)


def handle_systemgroup_credential_post(request, user_meta):
    """Process login/logout POST buttons. Returns True if handled."""
    if "submit-systemgroup-logout" in request.POST:
        clear_systemgroup_credentials(user_meta)
        return "logout"
    if "submit-systemgroup-login" in request.POST:
        username = request.POST.get("systemgroup_username") or ""
        password = request.POST.get("systemgroup_password") or ""
        login_systemgroup_credentials(user_meta, username, password)
        return "login"
    return None


def client_for_user_meta(user_meta, session=None) -> SystemGroupClient:
    """Build a CRM client using the user's credentials + org CRM base URL."""
    if not user_meta_has_systemgroup_credentials(user_meta):
        raise SystemGroupClientError(
            "Log in to SystemGroup before importing."
        )
    organization = getattr(user_meta, "organization", None)
    return SystemGroupClient(
        base_url=crm_base_url_from_organization(organization),
        username=(user_meta.systemgroup_username or "").strip(),
        password=user_meta.systemgroup_password or "",
        session=session,
    )
