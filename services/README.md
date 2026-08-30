# Data service

The dependency-light WSGI service in
`pipeline/src/thermal_drought/api/`. It consumes the same validated variable
registry and canonical monthly products as the pipeline. Point and lossless map
responses call one shared selected-month median, classification, and
quality path.

The checked-in service configuration points to the two-year Sicily release:
all months in 2025 and 2024, one provider-aligned 16 × 17 acquisition grid, and
only the 44 cell centers admitted by `config/scope.json`. The service will fail
closed until the exact official release report and ignored products exist.
In the verified 7 August 2026 working tree those products exist, and health and
availability report official evidence true, two complete years, and latest
complete year 2025.

Validate the registry, checksums, NetCDF headers, release bounds, and local
service catalogue:

```bash
make service-check
```

Run only deterministic unit and integration tests (these use a release
explicitly marked as a non-climate fixture):

```bash
make service-test
```

Start the local server on loopback:

```bash
pipeline/.venv/bin/python -m thermal_drought.api
```

Implemented endpoints:

```text
GET /v1/live
GET /v1/ready
GET /v1/health
GET /v1/availability
GET /v1/metrics
GET /v1/sample?x=spei_3&y=utci_daymax_median&year=2025&months=fff&lng=13.75&lat=37.5
GET /v1/tiles/sicily-2024-2025-v1/spei_3/utci_daymax_median/2025/fff/0/0/0
```

The tile endpoint returns lossless sparse JSON for the bounded 44-cell Sicily
scope; a raster envelope would add no useful resolution at this scale. `-`
in the Y-variable path selects univariate mode. Its immutable ETag/cache key
includes API, software, data, variable order, year, month mask, statistic,
minimum-valid fraction, quality rule, classification breaks and edge
assignments, palette version, and tile coordinates.

The service rejects unknown, duplicate, incompatible, or more-than-two
variables; unpublished years or months; invalid masks, coordinates, tile
indices, or zooms; excessive release file counts; oversized development
products; checksum changes; fixture/official provenance mismatches; and paths
outside `data/published/`. Invalid requests are rejected before climate arrays
are opened. Missing and low-quality values remain JSON `null` with explicit
status and quality fields; they never become zero.

The production wrapper writes atomic bounded responses into the configured
cache. It limits entries and bytes, and `operations-check` prewarms only the 17
approved masks; arbitrary masks remain on demand. Daily UTCI arrays are
excluded from serving storage. Runtime metrics expose route classes, counts,
bytes, cache inventory, and latency without coordinates or query strings.

Build, install, prewarm, benchmark, probe, and rehearse rollback with:

```bash
make operations-check
```

Production uses the root `Dockerfile`, `compose.yaml`, and an immutable HTTPS
bundle with an exact SHA-256. The separate nginx frontend proxies `/api/` to
this private service. See `OPERATIONS.md` for promotion and incident commands.

## Local beta handoff router

Build and validate the ignored replacement bundle:

```bash
make beta-preview-check
```

Then serve it beside the unmodified legacy tree with the bounded API under one
loopback origin:

```bash
pipeline/.venv/bin/python -m thermal_drought.preview --port 4173
```

The router maps `/preview/` to `web/dist/`, `/legacy/` to `docs/`, and
`/api/v1/` to the existing service. Preview index and legacy responses are
`no-store`; fingerprinted replacement assets are immutable. Static routing is
path-contained, has no directory listing, rejects symbolic-link preview builds
during preflight, and does not add CORS. It is a local recovery and review
surface, not the M4 production service or an M6 deployment.
