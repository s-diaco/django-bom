#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

export PATH="$HOME/.local/bin:$PATH"
set -a
# shellcheck disable=SC1091
source "$REPO_ROOT/.env.dev.postgres"
set +a

uv run python manage.py runserver 0.0.0.0:8000
