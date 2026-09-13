# Clean up empty manufacturer parts

BOM CSV import used to create a blank `Manufacturer` plus a `ManufacturerPart` with an empty MPN on every row that had no manufacturer name and no MPN. It also overwrote that part's primary manufacturer part. New imports skip that path; this command removes rows already in the database.

Do this on production **after this code is deployed**. Dry-run first. Take a backup before `--execute`.

## Backup

See [Backup and restore database](../README.md#backup-and-restore-database-if-using-docker-compose-and-postgres).

```
docker compose --env-file .env.prod exec -T db pg_dump -c -U bom_user bom_db | gzip > ./dump_bom_db_$(date +"%Y-%m-%d_%H_%M_%S").sql.gz
```

## Dry-run (default, no writes)

Review the counts:

```
docker compose --env-file .env.prod exec web python manage.py cleanup_empty_manufacturer_parts
```

Optional: limit to one organization with `--organization-id N`.

## Apply

```
docker compose --env-file .env.prod exec web python manage.py cleanup_empty_manufacturer_parts --execute
```

If `web` is not running, use a one-off container instead:

```
docker compose --env-file .env.prod run --rm --no-deps --entrypoint python web manage.py cleanup_empty_manufacturer_parts
```

## What it deletes

- `ManufacturerPart` rows with a blank MPN and a blank/null manufacturer name
- leftover `Manufacturer` rows whose name is blank and that have no remaining parts

## What it keeps

- manufacturer parts that have seller/pricing rows (`SellerPart`)
- the parts-upload placeholder manufacturer `انتخاب نشده (پیش فرض)`
- real MPNs and named manufacturers

For parts whose primary manufacturer part is empty junk, the command re-points primary to a remaining manufacturer part, or clears it if none remain.

This does **not** merge duplicate real manufacturer parts (same MPN under different manufacturer rows). That is a separate pass if you still see duplicates after cleanup.
