# BOM

BOM is a Django-based bill of materials system with a split application architecture:

- A Django REST Framework API under `/api/v1`
- A React + Vite + TypeScript client in `frontend/`
- JWT authentication powered by `djangorestframework-simplejwt`

The project still includes the original Django app and admin flows, but it now also ships a modern API/client stack for authenticated parts search, part detail views, and BOM exploration.

## What is in the repo

- Django 5 backend for BOM data, admin, legacy views, and integrations
- DRF API for auth, current user metadata, part list, part detail, and BOM views
- React client with login, protected routes, parts dashboard, and part detail/BOM page
- Frontend test coverage with Vitest and React Testing Library
- GitHub Actions workflow that runs frontend and backend validation in parallel

## Implemented API and client features

### Authentication

JWT endpoints are available under `/api/v1/auth/`:

- `POST /auth/login/`
- `POST /auth/refresh/`
- `POST /auth/logout/`
- `GET /auth/me/`

The React client stores access and refresh tokens locally and automatically attempts token refresh on `401` responses.

### Parts and BOM

Authenticated API endpoints currently include:

- `GET /api/v1/parts/`
- `GET /api/v1/parts/<part_id>/`
- `GET /api/v1/parts/<part_id>/bom/`

The frontend currently supports:

- Sign in with existing Django credentials
- Protected routing
- Paginated parts list with search
- Part detail page
- BOM rendering in `indented` and `flat` modes
- Quantity-based BOM recalculation

## Quick start

### Requirements

- Python 3.12+
- Node.js 20+
- npm
- Docker and Docker Compose if you want the container workflow

### Backend setup with uv

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
python manage.py migrate
python manage.py runserver
```

The Django app will be available at `http://127.0.0.1:8000/`.

### Frontend setup

```bash
cd frontend
npm ci
npm run dev
```

The Vite dev server proxies `/api` requests to `http://127.0.0.1:8000`.

If you need to point the client to a different backend, set `VITE_API_BASE_URL`.

## Docker workflow

The production stack runs four services defined in `docker-compose.yml`:

| Service  | Description |
|----------|-------------|
| `web`    | Django application served by Gunicorn, exposes the REST API and admin |
| `caddy`  | Reverse proxy that serves static files and forwards requests to `web` |
| `db`     | PostgreSQL 17 database |
| `backup` | Scheduled `pg_dump` that retains the last 7 compressed dumps in `./postgres_backup/` |

### Start the stack

1. Create `.env.prod` (and optionally `.env.db` for backup-specific overrides), or rename the example files.  
   Required variables: `SECRET_KEY`, `SQL_*`, `POSTGRES_*`, `NGINX_PORT`, `API_PORT`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.

2. If you need a PyPI mirror, add it to the Dockerfile before the dependency installation step:

```Dockerfile
ENV PIP_INDEX_URL=https://mirrors.sustech.edu.cn/pypi/web/simple
```

3. Build and start all services in detached mode:

```bash
docker compose --env-file .env.prod up --build -d
```

4. Restore the database from a dump if needed:

```bash
gunzip < dump_file.sql.gz | docker compose exec -T db psql -U bom_user -d bom_db
```

5. Run Django migrations and collect static files:

```bash
docker compose exec web sh entrypoint.sh
```

### Backup and restore database

Backup:

```bash
docker compose exec -T db pg_dump -c -U bom_user bom_db | gzip > ./dump_bom_db_$(date +"%Y-%m-%d_%H_%M_%S").sql.gz
```

Restore:

```bash
gunzip < dump_file.sql.gz | docker compose exec -T db psql -U bom_user -d bom_db
```

Restore an unzipped dump on Windows:

```bash
cat dump_file.sql | docker compose exec -T db psql -U bom_user -d bom_db
```

### Uninstall containers

```bash
docker compose --env-file .env.prod down --volumes --rmi local
```

## Development workflows

### Run backend tests

With Docker:

```bash
docker compose --env-file .env.test -f docker-compose.test.yml up --abort-on-container-exit --remove-orphans
```

Cleanup after Docker test runs:

```bash
docker compose -f docker-compose.test.yml down -v --rmi local
```

Or locally with uv:

```bash
uv run pytest
```

### Run frontend checks

```bash
cd frontend
npm run build
npm run test:run
```

### CI

GitHub Actions runs two jobs in parallel:

- `frontend`: install, build, and run Vitest
- `backend`: install Python dependencies and run `pytest`

## API examples

Obtain a token:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"yourusername","password":"yourpassword"}'
```

Fetch the authenticated user:

```bash
curl http://127.0.0.1:8000/api/v1/auth/me/ \
  -H "Authorization: Bearer youraccesstoken"
```

Fetch parts:

```bash
curl "http://127.0.0.1:8000/api/v1/parts/?q=resistor&page=1&page_size=25" \
  -H "Authorization: Bearer youraccesstoken"
```

Fetch a BOM:

```bash
curl "http://127.0.0.1:8000/api/v1/parts/42/bom/?view=indented&quantity=100" \
  -H "Authorization: Bearer youraccesstoken"
```

## Reusable Django app setup

The original `bom` app can still be embedded into another Django project.

Install the package:

```bash
pip install django-bom
```

Add required apps:

```python
INSTALLED_APPS = [
    ...,
    "bom",
    "social_django",
    "djmoney",
    "djmoney.contrib.exchange",
    "materializecssform",
]
```

Add URLs:

```python
from django.conf.urls import include

path("bom/", include("bom.urls")),
```

Add the BOM context processor and config:

```python
TEMPLATES = [
    {
        ...,
        "OPTIONS": {
            "context_processors": [
                ...,
                "bom.context_processors.bom_config",
            ],
        },
    },
]

BOM_CONFIG = {}
```

Run migrations:

```bash
python manage.py migrate
```

## Customize base template

```python
BOM_CONFIG = {
    "base_template": "base.html",
}
```

## Integrations

### Google Drive integration

Add the following to `settings.py`:

```python
AUTHENTICATION_BACKENDS = (
    "social_core.backends.google.GoogleOpenId",
    "social_core.backends.google.GoogleOAuth2",
    "social_core.backends.google.GoogleOAuth",
    "django.contrib.auth.backends.ModelBackend",
)

SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/plus.login",
]

SOCIAL_AUTH_GOOGLE_OAUTH2_AUTH_EXTRA_ARGUMENTS = {
    "access_type": "offline",
    "approval_prompt": "auto",
}
```

If production runs behind HTTPS:

```python
SOCIAL_AUTH_REDIRECT_IS_HTTPS = not DEBUG
```

### Fixer

Fixer.io is used for exchange-rate calculations when cost estimates involve multiple currencies. Add the API key to `local_settings.py`, then run:

```bash
python manage.py update_rates
```

## Installation pitfalls

### Windows

#### SQLite

If `pip install` fails while building SQLite-related packages, you may need the Visual C++ build tools.

#### Cryptography

If `cryptography` fails to install, missing environment configuration or native build prerequisites are usually the cause. This [Stack Overflow thread](https://stackoverflow.com/questions/46288737/error-while-installing-sqlite-using-pip-on-python-2-7-13) may help.
