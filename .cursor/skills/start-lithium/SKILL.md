---
name: start-lithium
description: >-
  Start the django-bom Docker stack locally. Use when the user asks to start
  the stack, bring up services, run docker compose, or start the app locally.
---

# Start Lithium

Start the full production-like Docker stack for this project.

## Command

From the repository root:

```bash
# Fast path: reuse an existing web image
docker compose --env-file .env.prod up -d

# Only when Dockerfile/deps changed and you need a fresh web image:
docker compose --env-file .env.prod up --build -d
```

Run with full permissions (`all`) so Docker can access the daemon.

Prefer `up -d` without `--build` unless the image is missing or dependency/Dockerfile
changes require a rebuild. Forced rebuilds are often the multi-minute wait before the UI
is reachable.

## After start

Verify containers are up:

```bash
docker compose --env-file .env.prod ps
```

If `web` is restarting, check logs:

```bash
docker compose --env-file .env.prod logs web
```

## Prerequisites

- Docker running locally
- `.env.prod` present in the repo root (not committed; copy from `.env.example` if missing)

## Notes

- `web` runs `migrate` and `collectstatic` on startup via `entrypoint.sh`.
- Default HTTP port comes from `NGINX_PORT` in `.env.prod` (Caddy reverse proxy).
- For Cloud Agent UI testing, prefer the env `terminals` Django runserver on port 8000
  instead of this Compose stack.
