# Global Thermal Comfort × Drought Map

This repository is being redirected from a Mediterranean crop-suitability prototype to an interactive global bivariate climate map.

The target product pairs:

- **Human thermal comfort:** Universal Thermal Climate Index (UTCI)
- **Drought:** 3-month Standardised Precipitation-Evapotranspiration Index (SPEI-3)

Users will be able to select one month, any non-empty combination of months, or the full year with a circular month control. The map will display the median value of each selected variable over that period and combine their classes in a bivariate legend. The architecture will support a future registry of variables, with one variable shown as a univariate map or two shown together as a bivariate map.

See [PROJECT_PLAN.md](./PROJECT_PLAN.md) for the scientific rationale, temporal semantics, product specification, target architecture, migration strategy, phased delivery plan, risks, tests, and acceptance criteria.

The immediate implementation sequence is in [SEVEN_DAY_PLAN.md](./SEVEN_DAY_PLAN.md). It defines the nightly work scheduled for July 23–29, 2026 and the beta expected at the end of that sprint.

## Current repository state

The current `docs/` directory is the legacy GitHub Pages prototype:

- a static Leaflet application;
- Mediterranean-only bounds;
- hard-coded crop/suitability controls;
- generated annual TerraClimate score rasters for 1991–2020;
- no source data pipeline, automated tests, or deployable aggregation service in this repository.

Treat it as a disposable reference implementation, not the foundation of the new data model. Keep it available until the global replacement passes the release gates in the project plan.

## Intended repository layout

```text
config/           Versioned variable, classification, and deployment configuration
pipeline/         Source acquisition, normalization, aggregation, validation, and publishing
services/         Median aggregation, raster tile, and point-sampling API
web/              Source for the global interactive map
tests/            Scientific, pipeline, API, UI, accessibility, and performance tests
docs/             Generated GitHub Pages frontend only
```

Raw and analysis-ready climate data should live in versioned object storage, not Git. `docs/` remains a generated publish target for the static frontend.

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

## Storage safety and temporal retention

The checked-in [`config/storage-policy.json`](./config/storage-policy.json)
turns the local storage envelope into an enforced contract:

- keep at least 20 GiB free and stop before the volume exceeds 80% use;
- allow at most one estimated full-year local backfill at a time, with a
  three-times processing-peak allowance;
- cap raw source storage at 3 GiB, canonical and published monthly stores at
  5 GiB each, and each reproducible cache/tile directory at 2 GiB;
- cap any one acquisition response at 512 MiB and reserve bounded workspace
  before provider retrieval, ZIP extraction, or normalization starts;
- precompute only 12 single-month masks, four meteorological seasons, and the
  all-month mask. Arbitrary month sets remain on demand;
- never delete data automatically. Multi-year acquisition must wait for
  reviewed object storage and lifecycle rules.

The temporal design is deliberately hybrid. UTCI begins with provider daily
maximum fields because they are needed to calculate the scientifically locked
monthly median of daily maxima. ERA5-Drought SPEI-3 already arrives monthly.
Only monthly UTCI, monthly SPEI-3, and provider quality state belong in the
serving store; daily UTCI sources are checksummed, used to validate the monthly
product, and then archived outside local serving storage. The application
therefore keeps day-level scientific fidelity without paying a daily-layer
serving and cache cost.

Validate the policy in any environment, inspect this machine, and preflight one
full local year:

```bash
pipeline/.venv/bin/python -m thermal_drought.storage validate
pipeline/.venv/bin/python -m thermal_drought.storage status
pipeline/.venv/bin/python -m thermal_drought.storage preflight --years 1
make storage-check
```

Blocked operations exit nonzero with a machine-readable reason code and do not
start the guarded write. Verified existing acquisition partitions remain
restartable without reserving space again.

## Official-data access proof

Night 2 added bounded, restartable acquisition requests for ERA5-HEAT daily UTCI
statistics and deterministic ERA5-Drought SPEI-3 with its provider normality
quality field. The code retains exact requests, checksums, retrieval timestamps,
source metadata, licences, DOI, citations, and expected coordinate/unit metadata
in sidecar receipts.

Check credential and client availability without displaying secret values:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire status
```

Inspect the 24-partition representative plan without downloading:

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
same exact representative plan by dataset ID:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire fetch \
  --dataset-id derived-utci-historical
pipeline/.venv/bin/python -m thermal_drought.acquire fetch \
  --dataset-id derived-drought-historical-monthly
```

Provider authentication, licence, and access failures return a secret-safe
machine-readable blocker with the dataset, planned request ID, reason code, and
official dataset page. Dataset-scoped retrieval does not weaken the acceptance
gate: the inspection command still requires all 24 plan-bound artifacts.

After retrieval, inspect the checksum-verified NetCDF headers and compare
observed UTCI, SPEI-3, and quality-field cell centers:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire inspect \
  --output pipeline/reports/night-2-observed-metadata.json
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
to match the fingerprinted plan. It exits unsuccessfully if any of the 24
planned artifacts is absent, unexpected, duplicated, fixture-backed, or
mismatched; if a checksum fails; if a source pair is missing; or if the observed
grids cannot map without interpolation. A mismatched receipt is never updated
with observed metadata.

See
[`pipeline/reports/night-2-data-access.md`](./pipeline/reports/night-2-data-access.md)
for the verified catalogue fields, request regions, observed provider
packaging, measured retrieval evidence, and paired-grid result. The complete
machine-readable audit is
[`pipeline/reports/night-2-observed-metadata.json`](./pipeline/reports/night-2-observed-metadata.json).

## Representative normalization path

Night 3 turns the checksum-verified bounded sample into canonical monthly
development products. It:

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
- writes one compact, atomic NetCDF development product per representative
  region below ignored `data/published/`.

Normalization reserves bounded temporary and published space before inspection
updates receipts or opens climate arrays. Its report and NetCDF global metadata
record the daily-source/monthly-serving retention contract.

Run the scientific/unit checks and reproduce all four official sample outputs:

```bash
make normalization-check
```

The machine-readable evidence report is
[`pipeline/reports/night-3-normalization.json`](./pipeline/reports/night-3-normalization.json).
It includes output checksums and eight center-cell golden samples with source
quality state, precision tolerance, and expected class. The tests independently
read the official daily members and monthly source fields to reproduce those
values. All synthetic unit-test NetCDFs are created only in temporary
directories and label themselves as structural tests, not ERA5 observations.

The local development representation is NetCDF because the declared Zarr
dependency could not be installed in this sandbox. Production chunked Zarr
publication remains a later data-volume step; the NetCDF sample is not described
as a global backfill or a production climate release.

## Local aggregation and data service

Night 4 adds a bounded local WSGI service backed by the checksum-verified Night
3 products. One shared implementation selects monthly layers by the canonical
12-bit mask, requires `ceil(selected months × 0.75)` valid values, takes the
median, applies manifest-defined threshold ownership, and carries provider
quality state through both point and development-tile responses.

Validate the service against the local official sample:

```bash
make service-check
```

Start it on loopback:

```bash
pipeline/.venv/bin/python -m thermal_drought.api
```

Then inspect health, availability, a Phoenix point, or the bounded zoom-zero
development tile:

```text
http://127.0.0.1:8000/v1/health
http://127.0.0.1:8000/v1/availability
http://127.0.0.1:8000/v1/sample?x=spei_3&y=utci_daymax_median&year=2024&months=041&lng=-112&lat=34
http://127.0.0.1:8000/v1/tiles/night-3-official-sample-v1/spei_3/utci_daymax_median/2024/041/0/0/0
```

`041` selects January and July. The development tile is sparse JSON over the
four small official sample grids; it is not a global raster or production tile
format. Availability correctly reports that 2024 is incomplete because only
those two months are published in this bounded sample. Missing and
quality-masked SPEI values are returned as `null`, never as zero.

## Global frontend shell

Night 5 replaces the placeholder web page with a manifest-driven TypeScript
application. It uses the checked-in variable entries for labels, units,
classifications, publication versions, and the two-variable cap, then intersects
them with `/v1/availability` before enabling years or months.

Start the bounded service and Vite development server in separate terminals:

```bash
pipeline/.venv/bin/python -m thermal_drought.api
cd web
npm run dev
```

Vite proxies `/api` to the loopback service. The checked-in production build
does not embed a service URL or any climate arrays; deployment routing remains
a later operations decision.

The frontend currently provides:

- a dominant global MapLibre navigation shell with a code-native graticule and
  no unreviewed external basemap assets;
- sparse markers for the four-region official development sample, explicitly
  labeled as bounded rather than global coverage;
- one-variable and two-variable modes, compatibility-aware selectors, an axis
  swap, and a strict maximum of two active variables;
- a twelve-wedge native-button month ring in January-to-December DOM order,
  plus a synchronized checkbox fallback, `aria-pressed`, visible focus,
  final-month protection, and an all-available action;
- URL serialization for both axes, analysis year, three-digit month mask,
  longitude, latitude, and zoom, including reload and Back/Forward restoration;
- an abortable development-tile loader that keeps the last valid map visible
  while a replacement loads or when a request fails;
- a collapsible narrow-screen control sheet that leaves at least half the
  viewport available to the map.

Because the verified sample publishes only January and July 2024, every other
month is truthfully disabled and the center action says `All available`, not
`All year`. The generic state and month logic still covers all 4,095 non-empty
masks, including disjoint selections, and enables them when availability
publishes those months.

Run the frontend unit/type gate and production build:

```bash
cd web
npm run check
npm run build
```

The application chunk is kept separate from the MapLibre vendor chunk so its
own compressed JavaScript size remains measurable. The legacy `docs/`
application is still untouched.

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
Full axe, screen-reader, color-vision-deficiency, Firefox, and WebKit tooling is
not installed; those broader cross-browser and palette gates remain in Night 7.
