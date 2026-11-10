"""ASP.NET forms-auth client for SystemGroup PAC Engineering BoM pages."""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse, urlunparse

import requests

from .parser import LoginFormFields, parse_login_form


class SystemGroupClientError(RuntimeError):
    """Network / auth failure talking to SystemGroup CRM."""


DEFAULT_LOGIN_PATH = "/Authentication/Login.aspx"
DEFAULT_BOM_EDIT_PAGE = "PAC/Engineering/BomPages/Edit.aspx"

_BOM_ID_IN_URL = re.compile(
    r"(?:[?&]id=|/id/)(\d+)",
    re.IGNORECASE,
)


def extract_bom_id_from_url(url: str) -> str | None:
    """Pull BoM id from a Shell/Edit CRM URL (handles nested page= query)."""
    if not url or not str(url).strip():
        return None
    raw = str(url).strip()
    # Nested page=PAC/...Edit.aspx?id=N may be percent-encoded once or twice.
    candidates = [raw, unquote(raw), unquote(unquote(raw))]
    for candidate in candidates:
        parsed = urlparse(candidate)
        qs = parse_qs(parsed.query)
        if "id" in qs and qs["id"]:
            return qs["id"][0]
        if "page" in qs and qs["page"]:
            page_val = qs["page"][0]
            match = _BOM_ID_IN_URL.search(page_val)
            if match:
                return match.group(1)
        match = _BOM_ID_IN_URL.search(candidate)
        if match:
            return match.group(1)
    return None


def credentials_from_env() -> tuple[str, str, str]:
    """Return (base_url, username, password) from CRM_* env vars."""
    base = (os.environ.get("CRM_BASE_URL") or "").strip()
    user = (os.environ.get("CRM_USERNAME") or "").strip()
    password = os.environ.get("CRM_PASSWORD") or ""
    missing = [
        name
        for name, val in (
            ("CRM_BASE_URL", base),
            ("CRM_USERNAME", user),
            ("CRM_PASSWORD", password),
        )
        if not val
    ]
    if missing:
        raise SystemGroupClientError(
            "Missing required env vars: "
            + ", ".join(missing)
            + ". Set them in the environment or a gitignored env file; never commit secrets."
        )
    if not base.endswith("/"):
        base += "/"
    return base, user, password


def bom_edit_url(base_url: str, bom_id: str | int) -> str:
    """Build Shell.aspx?page=...Edit.aspx?id=<id> under base_url."""
    page = f"{DEFAULT_BOM_EDIT_PAGE}?id={bom_id}"
    # Shell wraps the real page; some installs also accept the page URL directly.
    query = urlencode({"page": page})
    return urljoin(base_url, f"Shell.aspx?{query}")


def bom_edit_direct_url(base_url: str, bom_id: str | int) -> str:
    return urljoin(base_url, f"{DEFAULT_BOM_EDIT_PAGE}?id={bom_id}")


class SystemGroupClient:
    """Session-backed forms-auth client."""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 60.0,
    ) -> None:
        if base_url is None or username is None or password is None:
            env_base, env_user, env_pass = credentials_from_env()
            base_url = base_url or env_base
            username = username or env_user
            password = password if password is not None else env_pass
        if not base_url.endswith("/"):
            base_url += "/"
        self.base_url = base_url
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = session or requests.Session()
        self._logged_in = False

    def login_url(self) -> str:
        return urljoin(self.base_url, DEFAULT_LOGIN_PATH.lstrip("/"))

    def build_login_payload(self, form: LoginFormFields) -> dict[str, str]:
        payload = dict(form.hidden)
        payload[form.username_name] = self.username
        payload[form.password_name] = self.password
        if form.submit_name:
            payload[form.submit_name] = form.submit_value or "Login"
        return payload

    def login(self, login_html: str | None = None) -> None:
        """GET login page (unless login_html provided), POST credentials, keep cookies."""
        login_url = self.login_url()
        if login_html is None:
            try:
                resp = self.session.get(login_url, timeout=self.timeout)
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise SystemGroupClientError(f"Failed to fetch login page: {exc}") from exc
            login_html = resp.text

        form = parse_login_form(login_html)
        action_url = urljoin(login_url, form.action) if form.action else login_url
        payload = self.build_login_payload(form)
        try:
            resp = self.session.post(
                action_url,
                data=payload,
                timeout=self.timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise SystemGroupClientError(f"Login POST failed: {exc}") from exc

        # Heuristic: still on login page with password field → failed auth
        lower = resp.text.lower()
        if "login.aspx" in (resp.url or "").lower() and 'type="password"' in lower:
            raise SystemGroupClientError(
                "Login appears to have failed (still on Login.aspx). "
                "Check CRM_USERNAME / CRM_PASSWORD."
            )
        self._logged_in = True

    def fetch_bom(self, bom_id: str | int) -> tuple[str, str]:
        """Return (body_text, content_type) for the BoM Edit page.

        Tries Shell.aspx wrapper first, then the direct Edit.aspx URL.
        """
        if not self._logged_in:
            self.login()

        urls = [
            bom_edit_url(self.base_url, bom_id),
            bom_edit_direct_url(self.base_url, bom_id),
        ]
        errors: list[str] = []
        for url in urls:
            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                resp.raise_for_status()
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
                continue
            if "login.aspx" in (resp.url or "").lower():
                errors.append(f"{url}: redirected to login")
                continue
            ctype = resp.headers.get("Content-Type", "text/html")
            return resp.text, ctype
        raise SystemGroupClientError(
            "Could not fetch BoM Edit page. Tried:\n" + "\n".join(errors)
        )


def rewrite_url_host(url: str, base_url: str) -> str:
    """Utility for tests: swap host of url to match base_url."""
    base = urlparse(base_url)
    parsed = urlparse(url)
    return urlunparse(
        (
            base.scheme or parsed.scheme,
            base.netloc or parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
