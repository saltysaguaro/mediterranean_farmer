# Data service

Night 4 provides a dependency-light local WSGI service in
`pipeline/src/thermal_drought/api/`. It consumes the same validated variable
registry and canonical monthly products as the pipeline. Point and development
tile responses call one shared selected-month median, classification, and
quality path.

The checked-in service configuration points to the bounded Night 3 official
sample. It is not a global backfill: only January and July 2024 and four
three-by-three representative regions are available. Availability therefore
reports no complete year.

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
GET /v1/health
GET /v1/availability
GET /v1/sample?x=spei_3&y=utci_daymax_median&year=2024&months=041&lng=-112&lat=34
GET /v1/tiles/night-3-official-sample-v1/spei_3/utci_daymax_median/2024/041/0/0/0
```

The tile endpoint returns bounded sparse JSON grid cells for frontend
development, not a production WebP raster or a claim of global coverage. `-`
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

The service currently writes no tile or composite cache. Future cache writers
must use the checked-in `config/storage-policy.json`: local cache and tile
directories are capped at 2 GiB each, only the 17 standard month masks may be
prewarmed, and arbitrary masks are on demand. Daily UTCI arrays are excluded
from serving storage; the service reads monthly UTCI medians, monthly provider
SPEI-3, and provider quality state only.
