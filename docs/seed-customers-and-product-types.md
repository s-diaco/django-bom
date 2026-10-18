# Seed customers and product types

One-time (idempotent) data seed for an organization: rename product type display names, add Ink/Powder types, and upsert customers from a CSV of company names.

Do this on production **after this code is deployed**. Dry-run first. Take a backup before `--execute`.

## Backup

See [Backup and restore database](../README.md#backup-and-restore-database-if-using-docker-compose-and-postgres).

```
docker compose --env-file .env.prod exec -T db pg_dump -c -U bom_user bom_db | gzip > ./dump_bom_db_$(date +"%Y-%m-%d_%H_%M_%S").sql.gz
```

## Prerequisites

- Know the target `--organization-id` (Django admin or `Organization` table).
- Customers CSV with header `company_name` (Persian names OK). Checked-in default:

  `bom/data/customers.csv`

## Dry-run (default, no writes)

```
docker compose --env-file .env.prod exec web python manage.py seed_customers_and_product_types --organization-id N
```

Optional custom CSV:

```
docker compose --env-file .env.prod exec web python manage.py seed_customers_and_product_types --organization-id N --customers-csv /path/to/customers.csv
```

## Apply

```
docker compose --env-file .env.prod exec web python manage.py seed_customers_and_product_types --organization-id N --execute
```

If `web` is not running, use a one-off container instead:

```
docker compose --env-file .env.prod run --rm --no-deps --entrypoint python web manage.py seed_customers_and_product_types --organization-id N
```

## What it renames (by code)

| Code     | New name      |
|----------|---------------|
| `no_loi` | Compound      |
| `with_loi` | Frit        |
| `no_bom` | Raw Material  |

Codes are unchanged. If a code is missing for that org, the command warns and skips that rename.

## What it creates

- Product types (only if missing): `ink` → Ink, `powder` → Powder, both `has_bom=True`, `apply_loi=False`, overhead `0` in the org currency, `sort_order` after existing types.
- Customers: one `Customer(name=..., organization=org)` per unique non-empty `company_name`. Existing org+name pairs are skipped.

After product type changes, the org product-type cache is invalidated.

## Idempotent re-run

Safe to re-run. Already-renamed types and existing customers/types are skipped. Dry-run should report zeros for create/rename after a successful `--execute`.

## New organizations

`DEFAULT_PRODUCT_TYPES` in `bom/constants.py` already seeds Compound / Frit / Raw Material / Ink / Powder for **new** orgs. This command is for existing production data.
