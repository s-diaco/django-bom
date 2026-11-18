# Materials list: production timing results

Date: 2026-11-18  
Target: `http://192.168.3.139:1313/materials/`  
Filter: `product=1`; default page size 25

## Conclusion

BoM price preparation is the dominant cost: approximately **97% of page 3** and **98% of page 13** application latency. Count and page retrieval are not the current bottleneck.

The cost-calculation phase still executes hundreds of database queries after graph prefetching. Investigate and fix those fallback queries before changing pricing behavior, adding pagination indexes, or replacing pagination.

## Method

Executed the deployed Django application inside `lithium_bom-web-1` on the actual production host over SSH, against production PostgreSQL. The production database contained 518 parts at measurement time.

Temporary wrappers existed only in a separate management-shell process; no deployed source files, database indexes, pricing rules, pagination behavior, or worker configuration were changed. Existing authenticated user-1 session used via Django's test Client, including middleware and template rendering. This bypasses HTTP/Gunicorn queueing and is explicitly an **application-stage measurement**, not a browser benchmark.

Six sequential GETs: pages 3 and 13 alternating, with the first pair treated as warmup. Table values are medians of the remaining two requests per page; these are a small diagnostic sample, not p95/SLA estimates. All requests returned HTTP 200.

Wall times below are exclusive (nested stages are subtracted), avoiding double counting. SQL duration measures database `execute()` calls and does not include all result fetching/ORM work. Wall time minus SQL time is not necessarily pure CPU time.

An initial exploratory run against the local Docker copy is excluded from these production results.

## Stage timings

| Stage | Page 3 wall time | Page 13 wall time | Queries: page 3 / page 13 |
| --- | ---: | ---: | ---: |
| Other middleware/view/query-building work | 26 ms | 27 ms | 8 / 8 |
| Paginator count | 13 ms | 14 ms | 1 / 1 |
| Page fetch | 37 ms | 42 ms | 1 / 1 |
| Page seller preparation, excluding nested work | 18 ms | 19 ms | 2 / 2 |
| BoM graph prefetch | 175 ms | 252 ms | 8 / 8 |
| Cost calculation, excluding graph prefetch | **4,291 ms** | **8,591 ms** | **231 / 452** |
| Template rendering | 59 ms | 58 ms | 3 / 3 |
| **Total** | **4,620 ms** | **9,003 ms** | **254 / 475** |

Cost calculation alone includes approximately **3,037 ms / 6,066 ms** of SQL execution on pages 3 / 13. Therefore this is not simply a query-free, expensive Python arithmetic problem.

Warm measured request ranges:

- Page 3: 4.518–4.722 seconds.
- Page 13: 8.622–9.384 seconds.

These reproduce the previously observed browser-level latency of roughly 5 and 9.5 seconds.

## Confirmed fallback queries

A separate diagnostic request for page 13 returned HTTP 200 and executed 475 queries, matching the stage measurements:

- `_bom_walk_subparts()` used its prefetched cache 111 times.
- It entered its fallback database-query path **370 times**.
- The most frequent SQL shape was the subpart/part-revision join, executed **370 times**, called from the recursive price walk at `bom/models.py:1202`.
- There were **52 product-type queries** (26 existence checks and 26 loads), showing that organization-instance caches are also not shared across the request as a whole.
- Repeated manufacturer/seller prefetch queries also originated from fallback walks.

The existing `prefetch_bom_graphs()` deduplicates work by assembly ID, while Django's relation cache belongs to individual Python model instances. Repeated/shared assemblies represented by different instances are a likely source of missing cache coverage; confirm with a focused regression fixture before choosing the fix. Empty assemblies also need prefetched-empty coverage so they do not issue repeated queries.

These results establish that the list still has a BoM traversal N+1-style problem despite existing graph prefetching. They do not establish that pricing rules must change.

## HTTP cross-check

Sequential authenticated HTTP requests from the production container through the production URL (not Django's test Client):

| Page | Run 1 total | Run 2 total |
| --- | ---: | ---: |
| 3 | 4.738 s | 4.617 s |
| 13 | 9.344 s | 9.424 s |

All returned HTTP 200 with final URL `/materials/`, not a login redirect. Time to response headers was within 3 ms of total time. This corroborates the stage measurements, although it is a server-origin HTTP check rather than a desktop-browser/network benchmark.

## Decision guidance

1. **Keep current pricing semantics for now.** First eliminate unnecessary queries inside BoM calculation, then remeasure remaining Python/ORM work.
2. **Do not replace pagination to solve this incident.** Count plus page retrieval totals approximately 50–56 ms. Eliminating both cannot remove the multi-second pricing delay.
3. **Do not prioritize new pagination/latest-revision indexes based on this incident.** They may be useful at larger scale, but measured count/page-fetch timings do not explain the current latency.
4. Add regression tests for repeated/shared subassemblies and price-calculation query counts. Prefetch existing does not establish that every traversed object uses it.
5. Reassess denormalized/cached prices or a more efficient rollup implementation only after fixing fallback queries, while preserving seller quantities, overhead, LOI and tenancy semantics.

## Artifacts

Local session artifacts (not deployed):

- `/tmp/opencode/profile_materials.py`
- `/tmp/opencode/materials-production-profile-results.log`
- `/tmp/opencode/profile_materials_queries.py`
- `/tmp/opencode/materials-production-query-results.log`
- `/tmp/opencode/materials-timing-methodology.md`
