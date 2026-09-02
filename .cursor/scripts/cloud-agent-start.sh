#!/usr/bin/env bash
set -euo pipefail

# Start PostgreSQL for each agent boot (idempotent).
if ! sudo pg_isready -h 127.0.0.1 -p 5432 -U postgres >/dev/null 2>&1; then
  sudo service postgresql start
fi

for _ in $(seq 1 60); do
  if sudo pg_isready -h 127.0.0.1 -p 5432 -U postgres >/dev/null 2>&1; then
    exit 0
  fi
  sleep 0.5
done

echo "PostgreSQL did not become ready in time" >&2
exit 1
