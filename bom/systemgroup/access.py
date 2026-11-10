"""Who may use SystemGroup BoM import (org flag + per-user CRM credentials)."""

from __future__ import annotations

import os

from .client import SystemGroupClient, SystemGroupClientError


def crm_base_url_from_env() -> str:
    """CRM host still comes from the server env (not a per-user secret)."""
    base = (os.environ.get("CRM_BASE_URL") or "").strip()
    if not base:
        raise SystemGroupClientError(
            "Missing CRM_BASE_URL. Set it in the server environment "
            "(e.g. .env.prod); never commit secrets."
        )
    if not base.endswith("/"):
        base += "/"
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


def user_can_import_systemgroup(user) -> bool:
    """True when org enables import, user is admin, and CRM user/pass are set."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    profile = user.bom_profile()
    if profile.role != "A":
        return False
    if not organization_systemgroup_import_enabled(profile.organization):
        return False
    return user_meta_has_systemgroup_credentials(profile)


def client_for_user_meta(user_meta, session=None) -> SystemGroupClient:
    """Build a CRM client using the user's saved credentials + CRM_BASE_URL."""
    if not user_meta_has_systemgroup_credentials(user_meta):
        raise SystemGroupClientError(
            "Set your SystemGroup username and password under Settings → User "
            "before importing."
        )
    return SystemGroupClient(
        base_url=crm_base_url_from_env(),
        username=(user_meta.systemgroup_username or "").strip(),
        password=user_meta.systemgroup_password or "",
        session=session,
    )
