# Sicily Thermal Comfort × Drought Map

This repository contains a deployable implementation of an interactive
Sicily-only bivariate climate map, alongside the preserved Mediterranean
crop-suitability prototype.

The target product pairs:

- **Human thermal comfort:** Universal Thermal Climate Index (UTCI)
- **Drought:** 3-month Standardised Precipitation-Evapotranspiration Index (SPEI-3)

Users can select one month, any non-empty combination of months, or the full
year with a circular month control. The map displays the median value of each
selected variable over that period and combines their classes in a bivariate
legend. The registry supports one-variable univariate views and compatible
two-variable bivariate views.

The scientific definitions and data dictionary are in
[METHODOLOGY.md](./METHODOLOGY.md). Deployment, promotion, monitoring,
refresh, rollback, and incident procedures are in
[OPERATIONS.md](./OPERATIONS.md), with the security model in
[SECURITY.md](./SECURITY.md).

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for the scientific rationale, temporal semantics, product specification, target architecture, migration strategy, phased delivery plan, risks, tests, and acceptance criteria.

See [COMPLETION_FOUNDATION.md](./COMPLETION_FOUNDATION.md) for the active route
from the bounded Night 1–6 implementation to complete Sicily data, production
tiles and storage, preview, validation, cutover, operations, and historical
backfill. It is also the repository's large-file and cache-cardinality plan.

The original bounded implementation sequence is in
[SEVEN_DAY_PLAN.md](./SEVEN_DAY_PLAN.md). It defines the Night 1–7 beta gates;
unfinished Night 7 work and all later completion milestones now follow the
active completion foundation.

## Current Sicily scope

`config/scope.json` is the geographic contract. It records Istat's generalized
regional boundary dated 1 January 2026, the source archive URL and SHA-256, a
provider-aligned acquisition box of `11.75°E–15.75°E, 35.25°N–39.00°N`, and
the 44 exact 0.25° ERA5 cell centers inside the Sicilia polygons. The raw Istat
archive and provider climate responses are not committed.

The initial climate release is the two latest shared complete years, 2025 and
2024, with all twelve months. Its exact bounded plan contains 60 requests: 24
UTCI monthly containers of daily maxima, 24 deterministic selected-year SPEI-3
containers, and 12 reference-period provider-quality containers reused across
both years. Build and inspect it with:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire plan
pipeline/.venv/bin/python -m thermal_drought.storage preflight --years 2
pipeline/.venv/bin/python -m thermal_drought.acquire fetch
pipeline/.venv/bin/python -m thermal_drought.acquire inspect \
  --output pipeline/reports/sicily-source-audit-v1.json
pipeline/.venv/bin/python -m thermal_drought.normalize \
  --report pipeline/reports/sicily-release-v1.json
```

Retrieval is restartable and fail-closed. Provider responses, receipts, and
published NetCDF products remain under ignored `data/`. A release is not
complete until all 60 checksummed official artifacts, 24 UTCI/SPEI grid pairs,
24 SPEI/quality pairs, both twelve-month products, and the 44-cell scope mask
validate. Missing or failed-quality values remain no data, never zero.

The 7 August 2026 local release satisfies that gate: 60/60 official artifacts,
both twelve-month products, 44 included cells, and latest complete year 2025.
The small source audit and release report are retained as commit candidates;
the 29,780,288 raw artifact bytes and 94,679 published NetCDF bytes remain
ignored.

## Current repository state

The `docs/` directory is the preserved legacy GitHub Pages prototype:

- a static Leaflet application;
- Mediterranean-only bounds;
- hard-coded crop/suitability controls;
- generated annual TerraClimate score rasters for 1991–2020;
- no connection to the replacement pipeline or deployable aggregation service.

Treat it as a recoverable reference implementation, not the foundation of the
new data model. The local annotated tag `legacy-mediterranean-v1` points to its
last legacy-only commit. Keep the tree available until the Sicily replacement
has completed its monitored public release and independent review gates.

## Intended repository layout

```text
config/           Versioned variable, classification, and deployment configuration
pipeline/         Source acquisition, normalization, aggregation, validation, and publishing
services/         Service operator handoff documentation
web/              Source for the Sicily interactive map
pipeline/tests/   Scientific, pipeline, API, runtime, and operations tests
docs/             Preserved legacy GitHub Pages application
```

Raw and analysis-ready climate data live outside Git. Production uses an
immutable checksummed release bundle plus separate API and frontend containers;
it does not use a Codex Site.

## Development foundation

Night 1 of the implementation sprint established the variable contracts, month-mask logic, Python package, web package, and continuous-integration checks.

```bash
python3 -m venv pipeline/.venv
pipeline/.venv/bin/python -m pip install --upgrade pip
pipeline/.venv/bin/python -m pip install -e './pipeline[dev]'
cd web
npm ci
cd ..
make foundation-check
```

Additional local checks:

```bash
pipeline/.venv/bin/ruff check pipeline/src pipeline/tests
pipeline/.venv/bin/mypy pipeline/src
cd web
npm run build
```

Audit every tracked and non-ignored commit-candidate path without opening
ignored credentials or climate data:

```bash
make repository-check
```

The audit verifies representative ignore rules, rejects generated data,
dependencies, caches, browser output, credentials, and climate rasters outside
the preserved legacy tree, and scans candidate text for high-confidence secret
patterns without echoing matched values. Only the already tracked rasters below
`docs/data/crops/` are grandfathered until the reviewed cutover; a newly added
raster in that path fails the audit.

## Storage safety and temporal retention

The checked-in [`config/storage-policy.json`](./config/storage-policy.json)
turns the local storage envelope into an enforced contract:

- keep at least 20 GiB free and stop before the volume exceeds 80% use;
- allow exactly the two-year initial Sicily release locally, with a three-times
  processing-peak allowance; a third year remains blocked;
- cap raw source storage at 3 GiB, canonical and published monthly stores at
  5 GiB each, and each reproducible cache/tile directory at 2 GiB;
- cap any one acquisition response at 512 MiB and reserve bounded workspace
  before provider retrieval, ZIP extraction, or normalization starts;
- precompute only 12 single-month masks, four meteorological seasons, and the
  all-month mask. Arbitrary month sets remain on demand;
- never delete data automatically. Deployment and any M9 historical
  acquisition still require reviewed object storage and lifecycle rules.

The temporal design is deliberately hybrid. UTCI begins with provider daily
maximum fields because they are needed to calculate the scientifically locked
monthly median of daily maxima. ERA5-Drought SPEI-3 already arrives monthly.
Only monthly UTCI, monthly SPEI-3, and provider quality state belong in the
serving store; daily UTCI sources are checksummed, used to validate the monthly
product, and then archived outside local serving storage. The application
therefore keeps day-level scientific fidelity without paying a daily-layer
serving and cache cost.

Validate the policy in any environment, inspect this machine, and preflight the
bounded two-year local release:

```bash
pipeline/.venv/bin/python -m thermal_drought.storage validate
pipeline/.venv/bin/python -m thermal_drought.storage status
pipeline/.venv/bin/python -m thermal_drought.storage preflight --years 2
make storage-check
```

Blocked operations exit nonzero with a machine-readable reason code and do not
start the guarded write. Verified existing acquisition partitions remain
restartable without reserving space again.

## Sicily official-data acquisition

The acquisition path submits bounded, restartable Sicily requests for ERA5-HEAT
daily UTCI statistics and deterministic ERA5-Drought SPEI-3 with its provider
normality-quality field. It retains exact requests, checksums, retrieval
timestamps, source metadata, licences, DOI, citations, and expected
coordinate/unit metadata in sidecar receipts.

Check credential and client availability without displaying secret values:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire status
```

Inspect the 60-request Sicily plan without downloading:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire plan
```

The plan includes an order-independent SHA-256 fingerprint over every request,
region, period, target path, and source-metadata record. The inspection report
repeats that fingerprint so the evidence set can be tied to one exact plan.

Run only the acquisition tests and secret-safe status check:

```bash
make acquisition-check
```

Official retrieval requires accepted CDS dataset terms, a local CDS credential,
and the optional data dependencies. Raw downloads remain ignored:

```bash
pipeline/.venv/bin/python -m pip install -e './pipeline[data,dev]'
pipeline/.venv/bin/python -m thermal_drought.acquire fetch
```

To test or resume one provider dataset without submitting the other, scope the
same exact Sicily plan by dataset ID:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire fetch \
  --dataset-id derived-utci-historical
pipeline/.venv/bin/python -m thermal_drought.acquire fetch \
  --dataset-id derived-drought-historical-monthly
```

Provider authentication, licence, and access failures return a secret-safe
machine-readable blocker with the dataset, planned request ID, reason code, and
official dataset page. Dataset-scoped retrieval does not weaken the acceptance
gate: the inspection command still requires all 60 plan-bound artifacts.

After retrieval, inspect the checksum-verified NetCDF headers and compare
observed UTCI, SPEI-3, and quality-field cell centers:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire inspect \
  --output pipeline/reports/sicily-source-audit-v1.json
```

The inspection reads coordinate arrays and structural metadata, not climate
arrays. It handles direct NetCDF responses and safely validates CDS ZIP
containers before reading every NetCDF member. It records dimensions, shapes,
units, nodata, archive membership, coordinate order, cell centers, and retrieval
latency in an audit report and the acquisition receipts.
Archive expansion is preflighted against the same free-space and volume
high-water guards before a temporary directory is created.
Before opening an artifact, it requires the receipt's dataset, request body,
request fingerprint, source metadata, period, region, and canonical target path
to match the fingerprinted plan. It exits unsuccessfully if any of the 60
planned artifacts is absent, unexpected, duplicated, fixture-backed, or
mismatched; if a checksum fails; if a source pair is missing; or if the observed
grids cannot map without interpolation. A mismatched receipt is never updated
with observed metadata.

See
[`pipeline/reports/m3-sicily-data-plane.md`](./pipeline/reports/m3-sicily-data-plane.md)
for the exact request plan, capacity evidence, bounded-retry policy, and the
completed official acquisition evidence. The earlier Night 2 reports remain
historical evidence for the superseded representative sample.

## Sicily normalization path

Normalization turns the checksum-verified two-year Sicily acquisition into
canonical monthly release products. It:

- reads the observed ZIP containers with the same path, member-count, type, and
  expansion bounds used by acquisition inspection;
- selects only ERA5-HEAT v1.1 `utci_daily_max`, applies the explicit
  product-versioned Kelvin contract when the observed unit attribute is absent,
  validates values, converts to °C, and takes the per-cell median across the
  complete set of daily members;
- retains ERA5-Drought v1.0 deterministic `SPEI3` for the selected year and
  month without recomputing its three-month window;
- retains the separate provider `significance` array and publishes SPEI-3 only
  where that flag equals 1;
- canonicalizes names, Gregorian month-start time, EPSG:4326 coordinates,
  north-to-south latitude, and `[-180, 180)` longitude without interpolation;
- masks every provider-grid cell outside the 44-cell Istat scope and writes one
  compact, atomic NetCDF product per year below ignored `data/published/`.

Normalization reserves bounded temporary and published space before inspection
updates receipts or opens climate arrays. Its report and NetCDF dataset metadata
record the daily-source/monthly-serving retention contract.

Run the scientific/unit checks and then require the complete official Sicily
audit before writing release products:

```bash
make normalization-check
```

The scientific tests pass independently. The command fails closed if any
official Sicily artifact is missing; it never substitutes the historical
sample or a structural fixture.

The current machine-readable release report is
`pipeline/reports/sicily-release-v1.json`; it is written only after the exact
official source audit passes. It includes output checksums and 24 center-cell
golden samples with source
quality state, precision tolerance, and expected class. Once acquired, the
official daily members and monthly source fields are independently replayed to
reproduce those values. All synthetic unit-test NetCDFs are created only in temporary
directories and label themselves as structural tests, not ERA5 observations.

The Sicily representation is compressed NetCDF. With two year-sized products,
44 published cells, and lossless sparse JSON delivery, chunked Zarr and raster
tiles add operational complexity without a demonstrated payload or latency
benefit. Climate products remain ignored and outside Git.

## Local aggregation and data service

The local WSGI service is configured to load the checksum-verified Sicily
release and fails closed while its report or products are absent.
One shared implementation selects monthly layers by the canonical
12-bit mask, requires `ceil(selected months × 0.75)` valid values, takes the
median, applies manifest-defined threshold ownership, and carries provider
quality state through both point and lossless map responses.

Validate the service tests and require the official release catalogue:

```bash
make service-check
```

Start it on loopback:

```bash
pipeline/.venv/bin/python -m thermal_drought.api
```

Then inspect health, availability, a central Sicily point, or the bounded
zoom-zero response:

```text
http://127.0.0.1:8000/v1/health
http://127.0.0.1:8000/v1/availability
http://127.0.0.1:8000/v1/sample?x=spei_3&y=utci_daymax_median&year=2025&months=fff&lng=13.75&lat=37.5
http://127.0.0.1:8000/v1/tiles/sicily-2024-2025-v1/spei_3/utci_daymax_median/2025/fff/0/0/0
```

`fff` selects all twelve months. The response is lossless sparse JSON over the
44 Sicily grid centers. Availability reports 2025 and 2024 as complete only
after all months and products validate. Missing and quality-masked SPEI values
are returned as `null`, never as zero.

## Sicily frontend

The manifest-driven TypeScript application uses the checked-in variable entries for labels, units,
classifications, publication versions, and the two-variable cap, then intersects
them with `/v1/availability` before enabling years or months.

Start the bounded service and Vite development server in separate terminals:

```bash
pipeline/.venv/bin/python -m thermal_drought.api
cd web
npm run dev
```

Vite proxies `/api` to the loopback service. The checked-in production build
defaults to same-origin `/api` and embeds no climate arrays. `VITE_API_BASE` is
available for an explicitly reviewed route.

The frontend provides:

- a dominant Sicily-bounded MapLibre navigation shell with a code-native graticule and
  no unreviewed external basemap assets;
- sparse markers only for cells admitted by the Istat-derived Sicily mask;
- one-variable and two-variable modes, compatibility-aware selectors, an axis
  swap, and a strict maximum of two active variables;
- a twelve-wedge native-button month ring in January-to-December DOM order,
  plus a synchronized checkbox fallback, `aria-pressed`, visible focus,
  final-month protection, and an all-available action;
- URL serialization for both axes, analysis year, three-digit month mask,
  longitude, latitude, and zoom, including reload and Back/Forward restoration;
- an abortable lossless-map loader that keeps the last valid map visible
  while a replacement loads or when a request fails;
- a collapsible narrow-screen control sheet that leaves at least half the
  viewport available to the map.

The generic state and month logic covers all 4,095 non-empty masks, including
disjoint selections. The final selected month cannot be cleared.

Run the frontend unit/type gate and production build:

```bash
cd web
npm run check
npm run build
```

The application chunk is kept separate from the MapLibre vendor chunk so its
own compressed JavaScript size remains measurable. The legacy `docs/`
application remains untouched.

## Legend, point inspection, and methodology

Night 6 makes every rendered class interpretable without relying on color. The
same palette and raw class indices now drive the map and either a three-class
univariate scale or a fixed 3 × 3 bivariate matrix. Axis order, exact threshold
ownership, labels, and units come from the manifests. Every bivariate cell has
a paired text label; the no-data crosshatch is outside the matrix and explicitly
states that missing or failed-quality values are never zero.

Click or tap the map, use the `Inspect map center` button, or focus the map and
press Enter or Space to request the shared point endpoint. The readout shows:

- the requested and sampled grid-cell coordinates and selected period;
- exact physical values, units, fixed classes, and valid-month evidence;
- provider quality state and pass counts;
- source dataset and product version, sample retrieval date, and data version;
- the 0.25° grid-cell and personal-exposure limitations.

Point requests are abortable. A control change marks the prior readout stale
until matching values arrive; errors retain it with explicit stale copy and a
retry. No-data and provider-quality failure responses remain readable and never
substitute a score or zero. Sources, selected-year median semantics, SPEI-3's
provider accumulation window, the 75% validity rule, and limitations are
available beside the legend.

The deterministic `artificial_interface_fixture` exists only in tests and is
repeatedly labeled as not climate observations. It passes through the same
registry, compatibility, selected-month median, classification, legend, URL,
and sampling code without adding variable-name branches or becoming a
published variable.

The Night 6 frontend gate is included in the normal commands:

```bash
make service-check
cd web
npm run check
npm run build
```

The tests cover all nine paired legend labels, break ownership, univariate and
swapped orientation, artificial-variable integration, point no-data/quality
copy, stale retry behavior, and WCAG AA legend-text contrast. Real Chromium
smoke also covers keyboard point inspection, the official Phoenix values, the
southern provider-quality failure, offline retry, and phone/desktop layouts.
Final Chromium, Firefox, and WebKit checks report zero axe violations. Automated
protanopia, deuteranopia, tritanopia, grayscale, text-alternative, and contrast
checks pass. Independent palette-comprehension and live assistive-technology
reviews remain external approval gates.

## Production runtime and operations

The production shape is two conventional containers: the bounded API installs
an immutable release bundle by HTTPS URL and SHA-256, while unprivileged nginx
serves the frontend and proxies same-origin `/api/` traffic. Both containers are
read-only, drop capabilities, and have CPU, memory, PID, timeout, response,
concurrency, rate, and cache bounds.

Run the end-to-end local production rehearsal and the non-promoting monthly
refresh rehearsal with:

```bash
make operations-check
make refresh-rehearsal-check
```

CI builds both images and validates Compose on every change. Separate workflows
publish SBOM/provenance images only for an authorized release tag, prepare an
unpromoted monthly data candidate, and monitor a configured production URL.
Evidence and open external gates are recorded in:

- [`pipeline/reports/m4-production-runtime.json`](./pipeline/reports/m4-production-runtime.json)
- [`pipeline/reports/m6-production-frontend.md`](./pipeline/reports/m6-production-frontend.md)
- [`pipeline/reports/m7-review-hardening.md`](./pipeline/reports/m7-review-hardening.md)
- [`pipeline/reports/m8-operations-readiness.md`](./pipeline/reports/m8-operations-readiness.md)
- [`pipeline/reports/m8-refresh-rehearsal.json`](./pipeline/reports/m8-refresh-rehearsal.json)

## Recoverable local beta preview

M1 adds a generated preview route without replacing or copying the legacy
application. Build the frontend, verify every generated artifact, enforce the
checked frontend transfer budgets, inventory the legacy boundary, and write an
ignored checksum manifest:

```bash
make beta-preview-check
```

The command writes the generated frontend only to ignored `web/dist/` and its
manifest to ignored `output/m1-beta-preview/manifest.json`. It rejects source
maps and symbolic links, measures the application separately from MapLibre,
and leaves all 753 legacy files in `docs/` untouched.

After the official Sicily release has been acquired and normalized, serve the
replacement, legacy application, and local API on one loopback origin:

```bash
pipeline/.venv/bin/python -m thermal_drought.preview --port 4173
```

The local handoff routes are:

- `http://127.0.0.1:4173/preview/` — replacement using the local Sicily release;
- `http://127.0.0.1:4173/legacy/` — the preserved legacy `docs/` tree served in
  place;
- `http://127.0.0.1:4173/api/v1/` — the bounded service behind the preview's
  same-origin `/api` requests.

Stopping the preview process or returning to `/legacy/` is the complete local
rollback; no route mutates `docs/`, climate products, or a release pointer.
This is a local beta handoff with complete local Sicily coverage, not a
deployment or evidence of production CORS, persistent remote storage, cache
behavior, monitoring, or production latency. See
[`pipeline/reports/m1-beta-handoff.md`](./pipeline/reports/m1-beta-handoff.md)
for the measured preview evidence and remaining M1 gates.
