"""Ensure fa_IR catalogs are compiled so gettext UI assertions see Farsi."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _compile_fa_messages():
    repo_root = Path(__file__).resolve().parents[2]
    po = repo_root / "locale" / "fa_IR" / "LC_MESSAGES" / "django.po"
    if not po.is_file():
        return
    if not shutil.which("msgfmt"):
        return
    subprocess.run(
        [sys.executable, "manage.py", "compilemessages", "-l", "fa_IR"],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
