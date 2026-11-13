# Material List Performance Plan

Targets the materials list (`materials()` in `bom/views/views.py`, template `dashboard.html`) at `/materials/`. Staff hub at `/` (`home()`) is separate.

**Goals:** page nav under ~1 s on production-like PostgreSQL; no N+1; no behavior changes to latest-revision semantics, seller selection, pricing, search, print, export, auth, or tenancy.

## Done (do not re-implement)

| Work | Where |
| --- | --- |
| Stage A seller prefetch + optimal-seller cache on page rows | `bom/list_queries.py` (`paginate_part_revs`, `prepare_part_revs_for_list_page`); baseline `stage-a` (~110 queries vs ~1,015) |
| CSV/XLSX export without BOM walk (#109) | `prepare_part_revs_for_export`; seller-only `print_unit_cost`; `test_list_export_cost.py` |
| List `list_unit_cost` + BoM graph prefetch (#123) | `prefetch_bom_graphs`, `attach_list_unit_costs`; `dashboard.html` uses `list_unit_cost`; `test_list_unit_cost.py` |
| Latest-revision subquery (was B0) | `latest_part_revision_ids()` — `.values("part_id").annotate(max_id=Max("id")).values("max_id")`; used by `materials()` and `report()` |
| Materials list route split | List at `/materials/`; hub at `/`. Perf test hits `bom:materials` (baseline key still named `home`) |
| Autocomplete off by default | `BOM_CONFIG.admin_dashboard.enable_autocomplete: False` |
| Materials PN typeahead (#161) | `materials_part_number_suggest` JSON endpoint; `dashboard.html` uses it — no full-catalog embed on the list request |

Perf harness exists (`bom/tests/test_performance.py`, `perf/baseline.json`, `perf/README.md`) but still measures page 1 only on an 80-part SQLite dataset (query ceiling 200). `perf/measure_e2e.sh` defaults to `/` and `/report/`, not `/materials/`. Extend measurement as part of Stage A below.

`report()` still shares the same latest-revision / search construction pattern as `materials()` — keep both in sync when touching query construction. Report still optionally embeds a full-catalog autocomplete dict when `enable_autocomplete` is True.

---

## Open bugs (fix first)

### Search rebuild drops `product` filter

`materials()` applies `product=0/1` on `part_revs`, then when `q` is set rebuilds `part_revs` from searched parts **without** re-applying the material filter. `/materials/?product=0&q=...` can ignore raw-material filtering.

**Do:** one query-building path (filters → latest rev → product filter → order); regression test for search + product combinations.

---

## Remaining stages

### Stage A (measure) — finish

Still needed:

1. Measure `/materials/`, page 2/10, `product=0/1`, search, and `product`+`q` (wall time, DB time, query count, response size).
2. Temporary instrumentation around form, query build, paginate/prefetch, template.
3. PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` on slowest requests; separate count vs page vs prefetch cost.
4. Extend `test_performance.py` / `perf/measure_e2e.sh` beyond page 1; dataset closer to ~480 parts. Point e2e at `/materials/` (not the hub `/`). Prefer renaming the baseline key from `home` → `materials` when rewriting the harness.

No indexes or query rewrites from assumptions alone.

### Stage B — Query construction

After the search+product fix:

1. Keep part IDs lazy (`parts.values("id")` or `part__in=parts`) — drop eager `list(parts.values_list(...))` in `materials()` / `report()`.
2. Single pipeline: org → part-class → search → latest revision → product filter → stable order → download/print/paginate.
3. Confirm domain rule remains greatest `PartRevision.id` per part (already encoded in `latest_part_revision_ids`) before changing it.
4. Ordering tie-breaker: add `part_id` (or revision id) after number fields.
5. Revisit `Paginator` `COUNT(*)` only after search+product is fixed; consider count-friendly queryset or next/prev-only if still hot (UI already omits totals).

### Stage C — Explicit `list_seller`

Unit cost attachment is done (#123). Seller column still calls `part.optimal_seller` in templates (cached Python after Stage A prefetch, not SQL N+1).

1. Attach `part_rev.list_seller` in `prepare_part_revs_for_list_page`.
2. Update `dashboard.html` / print / report templates to use it.
3. Query-capture tests: page 1 and 2 never hit `Part.optimal_seller()` fallback DB path.

Do not push seller selection into SQL unless profiling shows Python cost matters after prefetch.

### Stage D — Autocomplete / typeahead (optional leftovers)

Materials list typeahead is done (#161). Remaining:

- Keep default `enable_autocomplete` off.
- If report (or other surfaces) need suggest UX, reuse the org-scoped JSON pattern — do not re-embed a full-catalog dict in list HTML.
- Not blocking materials-list latency while disabled / AJAX-only.

### Stage E — Indexes (plan-driven only)

Candidates only after PostgreSQL plans:

```text
bom_partrevision (part_id, id DESC)
bom_partrevision (part_id, material, id DESC)
bom_part (organization_id, number_class_id, number_item, number_variation, id)
bom_sellerpart (manufacturer_part_id, minimum_order_quantity)
```

For `icontains` search, evaluate `pg_trgm` GIN/GiST only if search plans justify it. Before/after `EXPLAIN` + `ANALYZE` for every index.

### Stage F — Only if measured

- Further BOM cost denormalization / invalidation (list path already prefetches graphs).
- Current-revision FK / read model at larger scale.
- Keyset pagination or org-scoped count/autocomplete caches — only when offset/count/page latency proves it.

---

## Acceptance (when remaining work ships)

- Search + product filters compose correctly.
- Query count independent of page row count for seller/BOM depth; normal paginated materials page trending toward &lt; 15 queries (tighten ceiling after fixes).
- Page 1 and 2 under one second on production-like PostgreSQL; no SQLite-only success claims.
- Unchanged search, filter, cost, print, export, auth, tenancy behavior.

## Constraints

- Fix search+product before indexes or caching.
- No PostgreSQL-only ORM unless PostgreSQL is the supported production DB (it is).
- Cache only org/permission-isolated data.
- Preserve scalability beyond the ~480-part dump.

## Relevant files

- `bom/views/views.py` — `materials()`, `report()` query construction; `materials_part_number_suggest`
- `bom/list_queries.py` — `latest_part_revision_ids`, pagination, seller/BOM prefetch, export/print costs
- `bom/models.py` — `Customer.latest_prices()` pattern; `PartRevision.bom_unit_cost`
- `bom/templates/bom/dashboard.html` — list rendering (`list_unit_cost`, still `optimal_seller`)
- `bom/tests/test_performance.py`, `test_list_unit_cost.py`, `test_list_export_cost.py`, `test_materials_part_number_suggest.py`
- `perf/baseline.json`, `perf/README.md`, `perf/measure_e2e.sh`
