#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
set -a
# shellcheck disable=SC1091
source "$REPO_ROOT/.env.dev.postgres"
set +a

# start.sh should already have Postgres up; wait briefly if this terminal races it.
for _ in $(seq 1 30); do
  if pg_isready -h "${SQL_HOST:-127.0.0.1}" -p "${SQL_PORT:-5432}" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

exec uv run python manage.py runserver 0.0.0.0:8000
