# Sicily Thermal Comfort × Drought Map — Completion Foundation

Status: active execution plan
Prepared: 2026-08-04
Product specification: [`PROJECT_PLAN.md`](./PROJECT_PLAN.md)
Sprint evidence: [`progress.md`](./progress.md)

## 1. Purpose

This document turns the working Night 1–6 vertical slice into the execution
foundation for a complete, scientifically defensible, production-shaped Sicily
map. It does not replace the scientific and product requirements in
`PROJECT_PLAN.md`. It defines the order of work, storage boundaries, release
architecture, large-file strategy, acceptance gates, and stopping conditions
needed to finish them.

The completion path must preserve these locked outcomes:

- Sicilia-only coverage using the checked Istat 2026 0.25° cell-center mask;
- UTCI as the monthly median of daily maximum UTCI;
- deterministic ERA5-Drought SPEI-3 with provider quality state;
- one selected analysis year and every non-empty combination of calendar months;
- equal-weight median aggregation across selected monthly layers;
- one-variable univariate and two-variable 3 × 3 bivariate modes;
- exact values, units, classes, sources, versions, dates, quality, and limitations
  at the point of interpretation;
- a variable-neutral registry path that does not add variable-name branches to
  generic selection, median, tile, sample, URL, or legend code;
- versioned climate data outside Git and a static, accessible frontend;
- tested refresh, preview, release, monitoring, and rollback procedures.

## 2. Current baseline

Nights 1–6 provide a verified bounded vertical slice:

- official January and July 2024 source evidence for Phoenix, Paris, Fairbanks,
  and the ERA5-HEAT southern coverage edge;
- restartable acquisition, checksum receipts, observed-metadata inspection,
  normalization, quality handling, monthly aggregation, and fixed classes;
- a bounded local WSGI service with health, availability, point, and sparse
  development-tile responses;
- a manifest-driven TypeScript/MapLibre interface with month ring, URL state,
  univariate/bivariate modes, legend, point interpretation, and failure states;
- passing Python, TypeScript, schema, storage, lint, type, and production-build
  checks documented in `progress.md`.

The baseline is not yet a Sicily beta or production release. The Night 1–6
implementation is checkpointed on `main` at `30596c2`, while this completion
plan and later M0 work remain local and reviewable. Night 7 is incomplete, the
service reads local sample NetCDFs, the tile response is development JSON rather
than a lossless raster, and no object store, container deployment, full-year
publication, monitoring, refresh, or rollback path exists.

Measured repository and local-storage facts at the start of this plan:

| Item | Measured size or count | Treatment |
| --- | ---: | --- |
| Legacy `docs/` site | 112 MiB, 753 tracked files | Preserve through cutover |
| Legacy rasters | 248 TIFF and 496 WebP files | Remove from the active tree only after release gates |
| Git object pack | 187 MiB | Address separately after cutover |
| Official bounded raw sample | 9.7 MiB | Ignored and reproducible |
| Local Python and web dependencies | approximately 303 MiB | Ignored and regenerated from lockfiles |

## 3. Definition of completion

The product is complete when all of the following are true:

1. At least two complete recent analysis years are published on the common
   Sicily grid, with the latest complete year selected by default.
2. All twelve months are available for both default variables and the SPEI
   quality field in every published complete year.
3. Every month mask from `001` through `fff`, except the empty mask, works for
   univariate and bivariate views without precomputing every combination.
4. Tile and point results use the same aggregation and classification code and
   agree on values, valid-month counts, quality, and class indices.
5. Versioned manifests expose availability, source metadata, classification,
   palette, software, retrieval, and data-release identity.
6. Missing, outside-coverage, or failed-quality observations never become zero.
7. The frontend passes supported Chromium, Firefox, and WebKit flows, automated
   accessibility checks, keyboard review, responsive visual review, and the
   agreed performance budgets.
8. A climate reviewer approves the variables, aggregation order, quality rule,
   thresholds, terminology, golden locations, and limitations.
9. A palette-comprehension review demonstrates that the nine combined states
   can be interpreted without relying on color alone.
10. Preview, refresh, cache warming, monitoring, failure response, and rollback
    have been rehearsed with immutable release versions.
11. The replacement completes a monitored production cycle before the legacy
    assets are removed from the active tree.

Historical publication from 1991 onward is an incremental post-launch backfill.
It must use the same release gates, but it is not allowed to delay or weaken the
complete recent-year launch.

## 4. Source-control and artifact boundary

### 4.1 Immediate checkpoint

Before expanding behavior:

1. Preserve the current `main` commit as a recoverable legacy tag.
2. Prepare the current work as explicit reviewable commit groups:
   - plans, manifests, Makefile, and CI;
   - acquisition, normalization, storage policy, and evidence;
   - aggregation, classification, and service;
   - frontend;
   - tests and documentation.
3. Stage explicit paths and run a secret scan; never stage `data/`, `.venv/`,
   `node_modules/`, `web/dist/`, caches, credentials, or browser output.
4. Run the complete supported verification suite before requesting a checkpoint
   commit.

Automated nightly work may prepare these groups and report them, but it must not
commit, push, rewrite history, or tag without explicit authorization.

### 4.2 Git policy

Git contains source, schemas, small deterministic fixtures, release manifests,
checksums, provenance summaries, tests, and runbooks. It never contains provider
archives, canonical arrays, published rasters, rendered climate tiles, runtime
caches, credentials, virtual environments, package installations, or generated
browser artifacts.

Git LFS is not the production climate-data store. It does not provide the
spatial range-read layout, lifecycle separation, atomic release pointer, cache,
or operational controls required by this product.

The 187 MiB historical pack remains until after cutover. Removing legacy files
from the current tree does not shrink existing clones. A history rewrite or clean
source repository is a separate, reviewed maintenance operation after the legacy
release is archived and every clone owner is coordinated.

## 5. Production data architecture

```text
Copernicus source
  -> immutable raw provider partition and receipt
  -> normalized monthly canonical array
  -> validated published spatial object
  -> stateless median/classification service
  -> immutable lossless tile cache and CDN
  -> static MapLibre frontend
```

### 5.1 Storage layers

| Layer | Initial production representation | Authority and retention |
| --- | --- | --- |
| Raw | Original ZIP/NetCDF plus request, receipt, checksum, byte size, and source metadata | Private immutable archive; retained for reproducibility and moved to a colder tier only by reviewed lifecycle policy |
| Canonical | Consolidated annual Zarr per variable with monthly time chunks and spatial chunks | Private scientific authority for derived publication |
| Published | Monthly Cloud Optimized GeoTIFFs or a measured equivalent | Read-optimized immutable serving input |
| Composite cache | Palette-indexed PNG or lossless WebP tiles | Regenerable, bounded, and lifecycle-managed |
| Release record | Small JSON manifest, checksums, provenance, validation report | Indefinite retention and repository copy |

The canonical-versus-published format split is deliberate. Zarr supports
scientific array processing and reproducibility; COG is a strong candidate for
bounded spatial range reads and ordinary raster tooling. A representative
benchmark must verify that combination before it becomes a locked decision.

### 5.2 Immutable object identity

Use release-scoped or checksum-scoped keys. Never overwrite a published data
object in place.

```text
raw/{providerVersion}/{variable}/{year}/{month}/{checksum}.nc
canonical/{dataVersion}/{variable}/{year}.zarr/...
published/{dataVersion}/{variable}/{year}/{month}.tif
tiles/{dataVersion}/{classificationVersion}/{paletteVersion}/
  {xVariable}/{yVariable}/{year}/{monthMask}/{z}/{x}/{y}.png
releases/{releaseId}/manifest.json
releases/current.json
```

Only the small `releases/current.json` pointer is mutable. Promotion changes it
atomically after the new release passes validation. The prior pointer and at
least one prior complete release remain available for rollback.

### 5.3 Format and chunk benchmark gate

Before a full-year release, implement one production-format spike using an
official Sicily month and a deterministic Sicily-grid structural fixture. Compare:

- annual Zarr with multiple spatial/time chunk layouts;
- monthly COG and annual twelve-band COG layouts;
- float32 against candidate loss-bounded integer encodings;
- PNG-8 against lossless WebP for categorical tiles.

Measure compressed bytes, number of remote reads, bytes read for one point and
one 256-pixel tile, cold and warm latency, peak memory, write time, and exact
value/class parity. Quantization is allowed only after a documented tolerance
study and climate review. Lossy imagery is not allowed for categorical class
tiles.

## 6. Large-file and backfill strategy

The versioned storage policy estimates, before compression:

| Scope | Raw sources | Monthly canonical values |
| --- | ---: | ---: |
| One Sicily year | 72 MiB conservative pre-acquisition estimate | 32 MiB conservative estimate |
| Two-year initial release | 144 MiB | 64 MiB |
| Two-year processing peak | 624 MiB including the three-times multiplier | — |

Capacity planning adds at least 25 percent for quality arrays, metadata,
compression variance, temporary objects, concurrent releases, and storage
implementation overhead. Estimates are replaced with measured full-month and
full-year values after the provider succeeds. The two-year local preflight is
authorized by the Sicily-scoped storage policy; a third year remains blocked.

### 6.1 One-month processing unit

Process one Sicily year/month partition at a time:

1. Validate the exact request plan and preflight local/worker capacity.
2. Retrieve to a bounded temporary target with restart and checksum support.
3. Inspect the response before opening climate arrays.
4. Retain the untouched raw partition and receipt locally; copy it to private
   immutable storage before any deployment that depends on remote persistence.
5. Normalize coordinates, units, time, nodata, and quality.
6. Reduce UTCI daily maxima to the monthly median; retain monthly SPEI-3 and its
   separate provider quality state.
7. Run structural, value-range, golden-cell, and coordinate-alignment checks.
8. Write canonical and published monthly products atomically.
9. Verify checksums and record the partition complete in release state.
10. Keep the bounded local workspace until a reviewed remote archive verifies;
    do not auto-delete source evidence.

The first complete year runs serially. Concurrency can increase only after the
measured peak, provider limits, and remote request behavior prove that two or
more parallel months remain within explicit quotas.

### 6.2 Backfill order

1. Latest provider-complete year.
2. Immediately preceding complete year, proving a second year needs no code
   changes.
3. Stop initial acquisition. Historical years are M9 and require continued
   explicit authorization plus a reviewed archive target.

Each year is a separate immutable release candidate. A historical failure
cannot block or corrupt the current complete-year product.

### 6.3 Cache-cardinality control

Never precompute all month combinations. Even for only 44 Sicily cells, 4,095
masks multiply across years, variable orientations, and data versions without
adding scientific value.

Prewarm only:

- the twelve single-month masks;
- the four meteorological-season masks;
- the all-month mask;
- the default variable pair and orientation;
- the two initial complete years;
- zoom levels 0–4.

The Sicily extent intersects only a handful of low-zoom tiles, so this produces
at most hundreds rather than millions of initial responses. Higher zooms,
arbitrary masks, univariate modes, and swapped orientation are rendered on
first request and cached within measured quotas. Versioned successful tiles
receive immutable cache headers and strong ETags. Errors and incomplete release
responses are never cached as successful data.

## 7. Service and deployment foundation

Keep the tested scientific core independent of the HTTP framework. For the
44-cell Sicily scope, the lossless sparse-grid JSON response is the production
data shape; raster encoding would add complexity without reducing meaningful
payload. The production adapter:

- reads only the bounded Sicily product and selected monthly layers from the
  active immutable release;
- calls the existing shared median and classification implementation;
- emits exact values, class indices, quality counts, and cell centers without
  lossy imagery;
- uses the same core for `/tiles` and `/sample`;
- validates variables, version, year, mask, zoom, and coordinates before reads;
- enforces request timeout, memory, response-size, concurrency, rate, and zoom
  limits;
- prevents cache stampedes for the same immutable key;
- returns structured no-data and quality results;
- publishes health, data readiness, latency, cache-hit, error, and freshness
  metrics;
- keeps credentials and provider access server-side.

Package the service as a reproducible container with non-root execution,
readiness/liveness checks, pinned dependencies, and a read-only application
filesystem. Runtime storage is disposable; object storage and release manifests
are authoritative.

Select storage and compute through a measured preview bake-off. Require an
S3-compatible storage interface so provider choice remains portable. Compare a
low-egress object store plus managed container runtime with a co-located
storage/runtime option. Decide using cold/warm tile latency, point latency,
request count, bandwidth, cache behavior, operational complexity, and projected
cost rather than a provider assumption.

No scheduled run may create paid resources, publish, deploy, or alter DNS/CORS
without explicit authorization.

## 8. Frontend, preview, and cutover

The existing TypeScript application remains the frontend foundation. Complete
it by replacing the sparse development cells with production raster tiles and
production availability while preserving:

- manifest-driven controls and compatibility;
- every non-empty month mask;
- immediate local control feedback and abortable network work;
- the last valid map during updates and recoverable errors;
- exact legend orientation, point interpretation, source metadata, and limits;
- keyboard, touch, screen-reader, and narrow-screen behavior.

Move GitHub Pages publication to a generated CI artifact. Generated frontend
bundles and climate rasters do not become source-controlled inputs.

Cutover sequence:

1. Preserve the legacy root and assets unchanged.
2. Publish the new application at a preview route or preview environment.
3. Exercise production-shaped storage, service, cache, CORS, and limits.
4. Run scientific, browser, accessibility, palette, performance, and rollback
   gates.
5. Promote the replacement to the root while keeping the legacy release
   recoverable.
6. Monitor one cache-warm cycle and rehearse one data refresh.
7. Remove legacy raster assets from the active tree in a later explicit change.
8. Evaluate repository-history cleanup only after the archive and cutover are
   secure.

## 9. Validation and review gates

### Pull-request gate

- Python and frontend units;
- manifest and release schema validation;
- exhaustive month-mask behavior;
- Ruff, strict mypy, TypeScript, and production build;
- small deterministic scientific and service fixtures;
- dependency and secret scanning.

### Release-candidate gate

- official golden-cell reproduction;
- complete-year coverage and quality inventory;
- point/tile value and class parity;
- class-area distribution comparison with explained change thresholds;
- hot/arid, tropical, temperate, cold, coastal, mountain, urban-adjacent,
  southern-edge, quality-failure, and no-data locations;
- current Chromium, Firefox, and WebKit core flows;
- automated accessibility, keyboard, screen-reader, responsive, grayscale, and
  color-vision review;
- bundle, tile, cached/uncached update, point, layout-shift, and interaction
  performance budgets;
- bounded-input, timeout, rate-limit, CORS, credential, and failure testing.

### External approval gate

- climate-science approval of source variables, transformations, temporal
  semantics, missing-data rule, quality handling, thresholds, labels, golden
  locations, and limitations;
- palette-comprehension evidence for the fixed 3 × 3 matrix;
- licensing and attribution review.

External review blockers are reported honestly and do not prevent independent
engineering, test, documentation, and preview work from continuing.

## 10. Execution milestones

| Milestone | Deliverables | Exit gate |
| --- | --- | --- |
| M0 — Baseline safety | Commit-ready groups, legacy tag request, secret-safe inventory, complete check report | A fresh checkout can reproduce Night 1–6 after authorized checkpointing |
| M1 — Night 7 beta | Browser/accessibility coverage, representative structural cases, budgets, preview build, beta gap report | Bounded beta passes without replacing legacy |
| M2 — Format and infrastructure decision | Zarr/COG/chunk/encoding benchmark, object/runtime bake-off plan, ADRs | Measured production data and hosting choices |
| M3 — Sicily data plane | Latest complete Sicily year, immutable manifests, provenance, publish/validate commands | Twelve months for both variables and the Istat-derived scope and provider-quality masks pass |
| M4 — Production service | Remote bounded reads, real lossless tiles, container, cache, metrics, limits | Tile/sample parity and provisional latency budgets pass |
| M5 — Second complete year | Unchanged pipeline processes and publishes the prior year | Reproducibility and year selection proven |
| M6 — Production frontend and preview | Real availability/tiles, reviewed basemap, CI Pages artifact, production-shaped preview | Latest complete all-year default and core flows pass |
| M7 — Review and hardening | Climate, palette, licensing, accessibility, browser, load, security, and failure gates | No open P0/P1 scientific, data, accessibility, security, or operational defect |
| M8 — Cutover and operations | Signoff, monitoring, refresh, cache warm, rollback rehearsal, production smoke | Replacement completes a monitored release cycle |
| M9 — Historical backfill and cleanup | Reverse-chronological releases, legacy active-tree removal, repository-size decision | Every added year and cleanup change is independently recoverable |

Expected remaining engineering time is approximately five to eight working
weeks, plus external-review scheduling and provider acquisition time. The
schedule is evidence-driven: a milestone remains active until its exit gate
passes, regardless of calendar date.

## 11. Nightly automation operating rules

Every scheduled run must:

1. Read `README.md`, `PROJECT_PLAN.md`, `COMPLETION_FOUNDATION.md`,
   `SEVEN_DAY_PLAN.md`, and `progress.md` before editing.
2. Inspect Git status and preserve all user work.
3. Resume the earliest incomplete milestone and acceptance gate.
4. Complete one coherent, reviewable implementation slice rather than broad
   speculative planning.
5. Prefer measured implementation and validation over adding duplicate plans.
6. Add or update tests with behavioral changes and run all relevant supported
   checks.
7. Record exact measurements, decisions, blockers, files changed, checks, and
   next action in `progress.md`.
8. Preserve scientific semantics and distinguish official data from fixtures.
9. Keep generated and climate artifacts outside Git.
10. Avoid deleting legacy assets, committing, pushing, history rewriting,
    purchasing, publishing, deploying, DNS changes, or external contact without
    explicit authorization.

When an external decision blocks one path, the run continues with independent
in-scope work. When M0–M8 and the complete-product gates are genuinely satisfied,
the automation records the handoff, stops implementation, and deactivates
itself. M9 historical work proceeds only while it remains explicitly active or
is separately scheduled.
