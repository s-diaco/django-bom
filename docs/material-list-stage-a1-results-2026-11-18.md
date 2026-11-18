# Materials list Stage A1 validation — 2026-11-18

## Change

`bom/list_queries.py` now deduplicates BoM database loading by assembly ID while distributing the loaded `subparts` QuerySet to **every encountered assembly instance**, including duplicates from earlier breadth-first waves and cached-empty results. Previously, skipped instances had no cache and fell back to SQL during pricing.

Page preparation also reuses organization-specific product-type maps across root rows before `is_product` classification. The map registry is local to one preparation call and keyed by organization ID. Existing `indented()` propagation handles descendants. No process-global cache, persisted prices, indexes, pagination changes, or pricing-rule changes were introduced.

Loaded seller relations may be shared, but optimal-seller results remain quantity-sensitive. Repeated BoM occurrences are still traversed; only loading is deduplicated.

## Regression coverage

New tests in `bom/tests/test_list_unit_cost.py` cover:

- Shared subassemblies across page roots and branches, including different BFS depths.
- Distinct Python assembly instances representing the same database assembly.
- Empty assemblies and raw-material leaves.
- Zero SQL during the **first** prepared pricing walk, and subsequent walks.
- Unchanged rollup costs, missing-price counts, and occurrence counts against fresh unprepared walks.
- Different extended quantities selecting different sellers from shared relations; revisiting lower quantities after bulk selection.
- `do_not_load` and LOI/non-LOI rollup equivalence.
- Product-type loading once per organization, tenant isolation, and fresh maps on subsequent preparation calls.
- Equal query counts for one versus five roots sharing a graph at fixed depth.

All three initial regressions failed before the implementation and passed afterward. The focused list-cost suite passes all 15 tests, including fixed query counts for duplicate root revisions whose assembly FK was not preloaded.

The full `bom.tests` suite against the final source snapshot passed **509 tests** in 183 seconds, with no system-check issues. The disposable runner supplied the development-only `parameterized` dependency, compiled Persian translations, and used writable temporary outputs; repository files remained mounted read-only or copied into disposable storage.

## Production-host candidate experiment

Target: actual production host `ubuntu@192.168.3.139`, container `lithium_bom-web-1`, production PostgreSQL, 518 parts, `product=1`, 25 rows per page.

**This was not a deployment.** Candidate function definitions were installed only in a separate management-shell process. No deployed files were replaced and web workers were not restarted. Django's authenticated test Client exercised the application and rendering, bypassing HTTP transport and Gunicorn queueing.

The same six-request sequence as the original baseline alternated pages 3 and 13, discarding the first pair as warmup. Values are medians of the remaining two observations per page, not p95/SLA or concurrent-load results. Original baseline timings were measured earlier on the same day; this is not a randomized benchmark.

| Stage | Page 3 baseline | Page 3 candidate | Page 13 baseline | Page 13 candidate |
| --- | ---: | ---: | ---: | ---: |
| Count | 13 ms | 12 ms | 14 ms | 8 ms |
| Page fetch | 37 ms | 31 ms | 42 ms | 29 ms |
| Seller preparation, excluding nested stages | 18 ms | 15 ms | 19 ms | 19 ms |
| BoM graph prefetch | 175 ms | 164 ms | 252 ms | 178 ms |
| Cost calculation, excluding graph prefetch | 4,291 ms | 254 ms | 8,591 ms | 398 ms |
| Rendering | 59 ms | 33 ms | 58 ms | 44 ms |
| Other request work | 26 ms | 15 ms | 27 ms | 17 ms |
| **Total** | **4,620 ms** | **524 ms** | **9,003 ms** | **694 ms** |
| **Total queries** | **254** | **25** | **475** | **25** |

The candidate cost-calculation stage executes two queries to initialize/load the root organization type map. Tests verify that the price walks themselves execute zero SQL after preparation.

### Same-process deployed/candidate comparison

A separate diagnostic process requested each page using deployed functions, then installed the candidate functions and repeated the requests:

| Metric | Page 3 deployed → candidate | Page 13 deployed → candidate |
| --- | ---: | ---: |
| Total queries | 254 → 25 | 475 → 25 |
| BoM walk cache uses | 69 → 250 | 111 → 481 |
| BoM fallback queries | 181 → **0** | 370 → **0** |
| Product-type queries across request | 52 → 4 | 52 → 4 |
| List prices | All 25 rows identical | All 25 rows identical |

All diagnostic requests returned HTTP 200. Equality compared revision IDs and rendered Money values for each list row. This checks these production pages, not every possible pricing configuration. The deployed source predates the current branch's incomplete-cost flag; local tests cover preservation of that newer behavior.

## Interpretation and remaining rollout validation

The experiment supports fixing prefetch coverage rather than changing pricing, adding listing indexes, or replacing pagination. Candidate application timings are below one second for both previously slow pages. This does **not** establish post-deployment HTTP latency: candidate functions were never installed into serving workers.

After review and deployment, repeat authenticated HTTP checks through the actual production URL and extend the filter/search matrix. Retain stage timings if HTTP latency differs materially. No additional pricing/pagination/index change is justified by this experiment.

## Session artifacts

- `/tmp/opencode/profile_materials_stage_a1.py`
- `/tmp/opencode/materials-production-stage-a1-profile-results.log`
- `/tmp/opencode/compare_materials_stage_a1.py`
- `/tmp/opencode/materials-production-stage-a1-comparison.log`
- `/tmp/opencode/stage-a1-full-tests.log`

Local automated tests use a disposable network-isolated container and SQLite test database; production PostgreSQL validation above is a separate read-only application experiment, not a PostgreSQL test-suite run.
