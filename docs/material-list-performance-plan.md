# Material List Performance Plan

Targets the materials list (`materials()` in `bom/views/views.py`, template `dashboard.html`) at `/materials/`. Staff hub at `/` (`home()`) is separate.

**Goals:** page nav under ~1 s on production-like PostgreSQL; no N+1; no behavior changes to latest-revision semantics, seller selection, pricing, search, print, export, auth, or tenancy.

## Done (do not re-implement)

| Work | Where |
| --- | --- |
| Stage A seller prefetch + optimal-seller cache on page rows | `bom/list_queries.py` (`paginate_part_revs`, `prepare_part_revs_for_list_page`); baseline `stage-a` (~110 queries vs ~1,015) |
| CSV/XLSX export without BOM walk (#109) | `prepare_part_revs_for_export`; seller-only `print_unit_cost`; `test_list_export_cost.py` |
| List `list_unit_cost` + initial BoM graph prefetch (#123) | `prefetch_bom_graphs`, `attach_list_unit_costs`; `dashboard.html` uses `list_unit_cost`; `test_list_unit_cost.py`. Implemented, but production profiling confirms incomplete cache coverage and fallback queries; see Stage A1. |
| Latest-revision subquery (was B0) | `latest_part_revision_ids()` — `.values("part_id").annotate(max_id=Max("id")).values("max_id")`; used by `materials()` and `report()` |
| Materials list route split | List at `/materials/`; hub at `/`. Perf test hits `bom:materials` (baseline key still named `home`) |
| Autocomplete off by default | `BOM_CONFIG.admin_dashboard.enable_autocomplete: False` |
| Materials PN typeahead (#161) | `materials_part_number_suggest` JSON endpoint; `dashboard.html` uses it — no full-catalog embed on the list request |

Perf harness exists (`bom/tests/test_performance.py`, `perf/baseline.json`, `perf/README.md`) but still measures page 1 only on an 80-part SQLite dataset (query ceiling 200). `perf/measure_e2e.sh` defaults to `/` and `/report/`, not `/materials/`. Extend measurement as part of Stage A below.

`report()` still shares the same latest-revision / search construction pattern as `materials()` — keep both in sync when touching query construction. Report still optionally embeds a full-catalog autocomplete dict when `enable_autocomplete` is True.

---

## Production findings — 2026-11-18

Full results and methodology: [production timing report](material-list-performance-results-2026-11-18.md).

Measured on `192.168.3.139`, deployed Django/PostgreSQL, 518 parts, `product=1`, 25 rows per page. Six sequential application requests alternated pages 3 and 13; the first pair was warmup. Values below are medians of the remaining two requests per page, not p95 or concurrency benchmarks. Timings are exclusive, so nested stages are not double-counted.

| Stage | Page 3 | Page 13 |
| --- | ---: | ---: |
| Paginator count | 13 ms | 14 ms |
| Page fetch | 37 ms | 42 ms |
| Page seller preparation | 18 ms | 19 ms |
| BoM graph prefetch | 175 ms | 252 ms |
| Cost calculation after prefetch | **4,291 ms / 231 queries** | **8,591 ms / 452 queries** |
| Template rendering | 59 ms | 58 ms |
| Other middleware/view work | 26 ms | 27 ms |
| **Total** | **4.62 s / 254 queries** | **9.00 s / 475 queries** |

Separate authenticated HTTP checks through the production URL returned materials HTML in 4.62–4.74 s (page 3) and 9.34–9.42 s (page 13), corroborating the application timings. Temporary instrumentation ran only in a separate management-shell process; no deployed behavior was changed. Initial local-copy measurements are excluded.

**Confirmed:** BoM prefetch + pricing accounts for approximately 97–98% of application latency. Price calculation alone includes approximately 3.04 s / 6.07 s of SQL execution; this is not just expensive Python arithmetic.

A diagnostic page-13 request found:

- 370 `_bom_walk_subparts()` fallback queries versus 111 prefetched-cache uses.
- 52 product-type queries (26 existence checks + 26 loads).
- Repeated manufacturer/seller loading originating from fallback BoM walks.

**Hypothesis to test:** `prefetch_bom_graphs()` deduplicates by assembly ID, but relation caches belong to individual model instances. Shared/repeated assemblies represented by different instances may therefore miss the cache. Empty assemblies also need cached-empty coverage. The fallback queries are proven; this precise cache-coverage mechanism still needs a regression fixture.

**Decision:** fix BoM query amplification without changing pricing semantics first. Count + page fetch costs only 50–56 ms; larger page numbers do not establish an offset bottleneck. Do not replace pagination, add listing indexes, or introduce persisted price caches to address this incident before remeasurement.

---

## Open bugs (fix first)

### BoM traversal still falls back to database queries

Existing graph prefetching does not prevent hundreds of queries during `attach_list_unit_costs()` → `bom_unit_cost` → `indented()` → `_bom_walk_subparts()`. Treat this as the primary performance defect, not as a request to change price calculation rules. Implement Stage A1 below, alongside the search correctness fix.

### Search rebuild drops `product` filter

`materials()` applies `product=0/1` on `part_revs`, then when `q` is set rebuilds `part_revs` from searched parts **without** re-applying the material filter. `/materials/?product=0&q=...` can ignore raw-material filtering.

**Do:** one query-building path (filters → latest rev → product filter → order); regression test for search + product combinations.

---

## Remaining stages

### Stage A (measure) — production split complete; extend and remeasure

Completed: production stage timing and query capture for pages 3/13 with `product=1`, plus authenticated HTTP cross-checks. This establishes the current bottleneck; it does not cover all filters or prove a latency SLA.

Still needed:

1. Retain/reproduce separate timings for count, page materialization, seller preparation, BoM prefetch, cost calculation, rendering, and remaining request work. Measure SQL time and query count per stage; do not equate wall time minus SQL time with CPU time.
2. Extend the matrix to pages 1/2/3/10/12/13 where available, `product=0/1` and omitted, search, and `product`+`q`. Keep user, page size and dataset comparable; record warmup, repeated-run ranges, response size and HTTP authentication status.
3. Extend `test_performance.py` / `perf/measure_e2e.sh` beyond page 1. Include a production-like PostgreSQL dataset of at least the measured ~518-part scale, shared/repeated subassemblies, empty assemblies, and varying depth. Point e2e at `/materials/`, not `/`; rename the baseline key from `home` → `materials` when rewriting the harness.
4. After Stage A1, repeat the same production stage split and HTTP checks. Profile remaining Python/ORM work only if it is still material after fallback queries are removed.
5. Use PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` on remaining slow SQL before proposing indexes/query rewrites. Count/page SQL is currently low priority; revisit if the filter matrix or larger datasets show otherwise. If client latency exceeds measured application work, investigate worker/connection queueing and lock waits.

No indexes, pagination replacement, or persisted pricing caches from assumptions alone.

### Stage A1 — Fix BoM prefetch coverage and repeated lookups (highest performance priority)

1. Add regression fixtures reproducing shared assemblies reached from multiple page roots and through different model instances, repeated nested subassemblies, empty assemblies, and multiple BoM depths. Confirm which cases trigger the measured fallback path before selecting an implementation.
2. Ensure every instance traversed by list pricing can reuse loaded subparts, including cached-empty results. Preserve traversal semantics while deduplicating database loading; do not skip a valid repeated BoM occurrence merely because its assembly ID was already visited for prefetching.
3. Eliminate per-node manufacturer/seller fallback loading. Preserve quantity-dependent seller selection: different extended quantities may choose different sellers even when relation data is shared.
4. Reuse organization-scoped product-type data across page roots and descendants within the request, rather than repeatedly checking/loading it on distinct organization instances. Do not introduce process-global or cross-tenant caches.
5. Add query-capture tests separating graph loading from price calculation. After preparation, the price walk must issue no fallback subpart/manufacturer/seller/product-type queries for the supported graph fixtures.
6. Assert unchanged costs, overhead/LOI behavior, quantities, `do_not_load` handling and seller selection. Keep the seller-only export path free of BoM walks; check print/report behavior for shared helper changes.
7. Remeasure pages 3 and 13 before considering pricing changes, persisted caches, indexes, or pagination replacement. Record remaining CPU/ORM cost rather than promising that eliminating SQL alone meets the latency target.

### Stage B — Query correctness and construction (not the measured latency driver)

Fix search+product composition early; do not let unrelated query optimization delay Stage A1:

1. Single pipeline: org → part-class → search → latest revision → product filter → stable order → download/print/paginate. Keep `materials()` and `report()` in sync and test search+product combinations.
2. Preserve the greatest `PartRevision.id` per part rule. Apply product filtering to the selected latest revision, not inside revision selection where it could return an older matching revision.
3. Add a mandatory unique ordering tie-breaker (`part_id` or revision id) after number fields for deterministic pagination.
4. Evaluate lazy part IDs (`parts.values("id")` or `part__in=parts`) instead of eager `list(parts.values_list(...))`; compare generated SQL/plans before treating this as a performance improvement.
5. Leave `Paginator` behavior unchanged for this incident: count is currently ~13–14 ms. Consider count-friendly queries or next/prev-only pagination only if new measurements establish a significant count cost (UI already omits totals).

### Stage C — Explicit `list_seller`

Page-row seller prefetch and unit cost attachment exist (#123). The seller column still calls `part.optimal_seller` (cached Python on prepared page rows). This does **not** establish that seller loading inside the recursive BoM walk is query-free; Stage A1 addresses the confirmed fallback path first.

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

Deferred for the current incident: measured count/page fetch totals only 50–56 ms. Reconsider candidates only after Stage A1 remeasurement or slow search/larger-dataset PostgreSQL plans:

```text
bom_partrevision (part_id, id DESC)
bom_partrevision (part_id, material, id DESC)
bom_part (organization_id, number_class_id, number_item, number_variation, id)
bom_sellerpart (manufacturer_part_id, minimum_order_quantity)
```

For `icontains` search, evaluate `pg_trgm` GIN/GiST only if search plans justify it. Before/after `EXPLAIN` + `ANALYZE` for every index.

### Stage F — Only if measured

- More efficient BoM rollup implementation if significant Python/ORM cost remains after Stage A1; preserve the existing pricing rules.
- BoM cost denormalization / invalidation only if corrected prefetching and rollup still miss the target. Existing prefetching is not proof of query-free traversal.
- Current-revision FK / read model at larger scale.
- Keyset pagination or org-scoped count/autocomplete caches — only when offset/count/page latency proves it; current production timings do not justify replacing pagination.

---

## Acceptance (when remaining work ships)

- Search + product filters compose correctly; latest-revision selection and deterministic pagination remain correct.
- Shared/repeated and empty assembly fixtures show zero fallback SQL during prepared price calculation. Product-type data is loaded per organization/request, not per root/node instance.
- Query count must not grow per BoM occurrence or page row at fixed graph depth; bulk prefetch may require additional query waves as depth increases. Set stage-specific ceilings from corrected measurements; retain < 15 total queries as an aspirational shallow-fixture target, not an unsupported ceiling for arbitrary-depth graphs.
- Pages 1/2 **and the measured problem pages 3/13** under one second on production-like PostgreSQL. Report warmup policy, dataset, page size, repeated-run ranges, stage timings and authenticated HTTP timings; no SQLite-only success claims or p95 claims from two samples.
- Unchanged search, filter, cost, quantity-dependent seller selection, overhead/LOI, print, export, auth and tenancy behavior.

## Constraints

- Fix search+product and BoM fallback query amplification before new indexes or persisted pricing caches. Remeasure before changing pricing or pagination.
- No PostgreSQL-only ORM unless PostgreSQL is the supported production DB (it is).
- Cache only org/permission-isolated data; prefer request-scoped reuse for this fix and preserve quantity-sensitive seller decisions.
- Preserve scalability beyond the measured 518-part production dataset.

## Relevant files

- `bom/views/views.py` — `materials()`, `report()` query construction; `materials_part_number_suggest`
- `bom/list_queries.py` — `latest_part_revision_ids`, pagination, seller/BOM prefetch, export/print costs
- `bom/models.py` — `PartRevision.bom_unit_cost`, `indented`, `_bom_walk_subparts`; `Organization.product_types_by_code`; quantity-sensitive `Part.optimal_seller`
- `bom/part_bom.py`, `bom/part_bom_weighted.py` — rollup implementation if profiling after fallback fixes justifies optimization
- `docs/material-list-performance-results-2026-11-18.md` — production baseline, diagnostic findings and measurement limitations
- `bom/templates/bom/dashboard.html` — list rendering (`list_unit_cost`, still `optimal_seller`)
- `bom/tests/test_performance.py`, `test_list_unit_cost.py`, `test_list_export_cost.py`, `test_materials_part_number_suggest.py`
- `perf/baseline.json`, `perf/README.md`, `perf/measure_e2e.sh`
