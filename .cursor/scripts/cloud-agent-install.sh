#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

export PATH="$HOME/.local/bin:$PATH"

# --- PostgreSQL (restore before migrate; see README) ---
bash .cursor/scripts/cloud-agent-start.sh

SQL_USER="${SQL_USER:-bom_user}"
SQL_PASSWORD="${SQL_PASSWORD:-bom_pass}"
SQL_DATABASE="${SQL_DATABASE:-bom_db}"
DUMP_DIR="${BOM_DB_DUMP_DIR:-$REPO_ROOT}"
DUMP_PATH="${BOM_DB_DUMP_PATH:-}"
MARKER="$HOME/.cache/bom-db-restored"

if [[ -z "$DUMP_PATH" ]]; then
  DUMP_PATH="$(ls -1t "$DUMP_DIR"/dump_bom_db_*.sql.gz "$DUMP_DIR"/postgres_backup/dump_bom_db_*.sql.gz 2>/dev/null | head -1 || true)"
fi

if [[ -z "$DUMP_PATH" && -n "${BOM_DB_DUMP_URL:-}" ]]; then
  mkdir -p "$HOME/.cache/bom-dumps"
  DUMP_PATH="$HOME/.cache/bom-dumps/bom_db.sql.gz"
  echo "Downloading database dump..."
  curl -fsSL "$BOM_DB_DUMP_URL" -o "$DUMP_PATH"
fi

sudo -u postgres psql -v ON_ERROR_STOP=1 -tc "SELECT 1 FROM pg_roles WHERE rolname = '$SQL_USER'" | grep -q 1 \
  || sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE USER $SQL_USER WITH PASSWORD '$SQL_PASSWORD' SUPERUSER;"

sudo -u postgres psql -v ON_ERROR_STOP=1 -tc "SELECT 1 FROM pg_database WHERE datname = '$SQL_DATABASE'" | grep -q 1 \
  || sudo -u postgres createdb -O "$SQL_USER" "$SQL_DATABASE"

if [[ -n "$DUMP_PATH" && -f "$DUMP_PATH" ]]; then
  if [[ ! -f "$MARKER" || "$(cat "$MARKER")" != "$DUMP_PATH" ]]; then
    echo "Restoring dump: $DUMP_PATH"
    sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$SQL_DATABASE" -c \
      "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO $SQL_USER; GRANT ALL ON SCHEMA public TO public;"
    # Strip PG17-only settings so restores work on PG16 dev VMs too.
    gunzip -c "$DUMP_PATH" | sed '/^SET transaction_timeout/d' \
      | sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$SQL_DATABASE"
    PART_COUNT="$(sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$SQL_DATABASE" -tc "SELECT COUNT(*) FROM bom_part" | tr -d ' ')"
    if [[ "${PART_COUNT:-0}" -eq 0 ]]; then
      echo "Restore finished but bom_part is empty — check dump URL and PostgreSQL version." >&2
      exit 1
    fi
    echo "Restored $PART_COUNT parts from dump."
    mkdir -p "$(dirname "$MARKER")"
    echo "$DUMP_PATH" >"$MARKER"
  else
    echo "Dump already restored: $DUMP_PATH"
  fi
else
  echo "No dump found (set BOM_DB_DUMP_PATH, BOM_DB_DUMP_URL, or place dump_bom_db_*.sql.gz in repo root)." >&2
fi

# --- App dependencies ---
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

uv sync --locked
npm ci
npm run build:css

set -a
# shellcheck disable=SC1091
source "$REPO_ROOT/.env.dev.postgres"
set +a

# After a restore, migrate applies only newer migrations than the dump.
uv run python manage.py migrate --noinput
