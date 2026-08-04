# Night 2 official-data access report

Checked: 2026-07-27 America/Phoenix

## Outcome

Both required dataset licences are now accepted by the configured CDS account.
The exact fingerprinted representative plan retrieved successfully:

- 24 of 24 official response artifacts have checksum-bound receipts;
- the response containers total 9,662,880 bytes (9.22 MiB);
- the containers hold 264 NetCDF members: 248 daily UTCI files, eight monthly
  SPEI-3 files, and eight reference-period quality files;
- all eight UTCI/SPEI-3 pairs and all eight SPEI-3/quality pairs have identical
  sampled cell centers with no reordering, longitude normalization, or
  interpolation required;
- the exact-plan audit reports `complete: true` and
  `official_evidence: true`, with no missing, unexpected, duplicate, fixture, or
  receipt-plan mismatch.

A second fetch verified all 24 existing checksums and receipts locally without
redownloading any artifact. The credential was not opened, printed, copied, or
written to the repository. No deterministic fixture contributed to the
official-data result.

## Verified public provider contracts

### ERA5-HEAT

- Dataset ID: `derived-utci-historical`
- Catalogue state: available
- Provider product version: 1.1
- Catalogue update date observed: 2026-07-23
- Catalogue temporal extent observed: 1939-12-01 through 2026-07-18
- Published coverage: 90°N to 60°S on a regular 0.25° latitude/longitude grid
- Observed delivery: ZIP response container with one NetCDF member per day
- Request variable: `universal_thermal_climate_index_daily_statistics`
- Product type: `consolidated_dataset`
- Required source quantity for this project: daily maximum UTCI in K, to be
  selected from the returned daily-statistics file
- DOI: `10.24381/cds.553b7518`
- Licence: Licence to use Copernicus Products

The request deliberately selects provider daily statistics. It does not request
hourly UTCI and does not substitute the provider's monthly maximum. Night 3 must
identify the daily-maximum NetCDF field from observed metadata, convert K to °C,
and compute the monthly median of those daily maxima.

### ERA5-Drought

- Dataset ID: `derived-drought-historical-monthly`
- Catalogue state: available
- Provider product version: 1.0
- Catalogue update date observed: 2026-07-10
- Catalogue temporal extent observed: 1940-01-01 through 2026-06-01
- Published resolution: regular 0.25° latitude/longitude grid
- Observed delivery: ZIP response container with one NetCDF member per requested
  monthly or quality layer
- Index variable: `standardised_precipitation_evapotranspiration_index`
- Accumulation period: 3 months
- Product type: `reanalysis` (the deterministic product, not ensemble members)
- Dataset type: `consolidated_dataset`
- Quality variable: `test_for_normality_spei`
- Provider constraint: the quality layer is indexed by calendar month and
  accumulation period, not by analysis year, so it is acquired separately from
  the year/month SPEI field
- Quality meaning: 0 indicates the Shapiro-Wilk test rejects normality at
  α = 0.05 and the SPEI estimate is low-quality/unreliable; 1 indicates the
  test does not reject normality
- DOI: `10.24381/9bea5e16`
- Licence: CC-BY-4.0

The provider's January SPEI-3 is requested directly. The acquisition and later
month selector must not recalculate its three-month accumulation window.

## Bounded representative plan

The generated plan partitions each dataset by region, year, and month for 2024
January and July:

| Region | Purpose | Requested bounds (N, W, S, E) |
| --- | --- | --- |
| Phoenix, Arizona | hot/arid | 34.25, -112.25, 33.75, -111.75 |
| Paris, France | temperate | 49.00, 2.00, 48.50, 2.50 |
| Fairbanks, Alaska | cold | 65.00, -148.00, 64.50, -147.50 |
| ERA5-HEAT southern limit | coverage-edge behavior if provider permits | -59.50, 0.00, -60.00, 0.50 |

This creates 24 small request partitions: daily UTCI, year/month SPEI-3, and the
separate reference-period SPEI quality layer × two months × four regions. The
plan intentionally avoids a global or historical backfill.

The exact current plan fingerprint is
`04989c737e477ab6aba89ee884014c03e3c87cfc8ca91ddbeb4c2e1f4839dee1`.
It is an order-independent SHA-256 over all request records, including request
bodies, regions, periods, canonical target paths, and source metadata. The plan
and the post-retrieval audit both expose this value.

## Restart and provenance behavior

Each response is first written to a `.part` path and atomically moved into place
only when it is non-empty. A JSON receipt retains:

- the exact request and its SHA-256 fingerprint;
- dataset ID, product version, provider, dataset URL, DOI, licence, and citation;
- region and purpose;
- UTC retrieval timestamp;
- measured retrieval duration;
- explicit analysis year and month, including a null year for reference-period
  quality layers;
- target path, byte size, and SHA-256 checksum;
- expected units and coordinate names from the public catalogue;
- an observed-NetCDF metadata field that is initially null and populated only
  by the checksum-verifying inspection command after a real download.

On rerun, a file is skipped only when its current byte size and checksum match a
receipt for the same request. Missing, malformed, or mismatched receipts and
corrupt files are not treated as verified downloads.

## Post-retrieval evidence audit

The Night 2 inspection command now:

- discovers receipt-backed `.nc` partitions below the ignored raw-data root;
- refuses fixture receipts as official-data evidence by default;
- rejects missing, path-traversing, size-mismatched, or checksum-mismatched
  artifacts before opening them;
- reads dimensions, shapes, data-variable units and nodata attributes, global
  attributes, and complete coordinate arrays without loading climate arrays;
- records coordinate names, order, endpoints, and regular step;
- compares UTCI and SPEI-3 latitude/longitude cell centers for every requested
  region, year, and month;
- compares each SPEI-3 layer with its month-specific provider quality layer;
- distinguishes harmless latitude reordering and 0–360 to -180–180 longitude
  normalization from incompatible cell centers;
- binds every receipt to the exact fingerprinted plan by checking its schema,
  dataset, variable, product version, request body and hash, period, region,
  source metadata, and canonical artifact and receipt paths;
- reports every missing or unexpected member of the exact 24-request
  representative plan and rejects duplicate request IDs;
- refuses to inspect or write observed metadata into a plan-mismatched receipt;
- detects provider ZIP packaging by content, rejects unsafe, encrypted,
  non-NetCDF, oversized, excessive, or duplicate archive members, and inspects
  members only in a temporary directory;
- verifies every daily UTCI archive contains exactly one structurally and
  spatially consistent NetCDF member for every requested calendar date;
- updates receipts atomically and produces a machine-readable audit.

The audit cannot report completion from a partial subset or a fixture. It
requires exactly one canonical, plan-bound, non-fixture receipt per request, no
extra receipts, all source and quality pairings, and compatible observed grids.

## Observed response measurements

Retrieval was sequential and restartable. The per-type measurements are:

| Planned source layer | Artifacts | Response-container size | Retrieval latency |
| --- | ---: | ---: | ---: |
| UTCI daily statistics | 8 | 1,164,227–1,164,847 bytes; 9,316,048 total | 39.13–59.01 s; 55.36 s mean |
| Deterministic SPEI-3 | 8 | 13,280–13,300 bytes; 106,312 total | 18.96–41.36 s; 33.77 s mean |
| SPEI normality quality | 8 | 30,056–30,076 bytes; 240,520 total | 25.99–55.71 s; 37.04 s mean |

The summed request duration was 1,009.34 seconds (16 minutes 49.34 seconds).
Every response was a ZIP container even though the client target has a `.nc`
suffix:

- each January or July UTCI response contains 31 daily NetCDF members;
- each SPEI-3 response contains one monthly NetCDF member;
- each normality-quality response contains one reference-period NetCDF member.

The inspector reads all archive member headers and rejects inconsistent
structure or spatial grids. It does not persist extracted members.

## Observed variables, dimensions, and nodata

Each representative extraction is a 3 × 3 spatial grid:

- coordinate names are `lat` and `lon`;
- latitude is descending at -0.25° per cell;
- longitude is ascending at +0.25° per cell;
- UTCI members have dimensions `time=1, lat=3, lon=3, bnds=2`;
- SPEI-3 and quality members have dimensions `time=1, lat=3, lon=3`.

Observed data variables:

| Layer | NetCDF variable | dtype | Observed unit attribute | Nodata |
| --- | --- | --- | --- | ---: |
| UTCI daily maximum | `utci_daily_max` | `float32` | absent | `-8.999999873090293e+33` |
| UTCI daily minimum, retained but not selected | `utci_daily_min` | `float32` | absent | `-8.999999873090293e+33` |
| Deterministic SPEI-3 | `SPEI3` | `float64` | absent | `-9999.0` |
| SPEI normality quality | `significance` | `float64` | `1` | `9.969209968386869e+36` |

The missing unit attributes on `utci_daily_max` and `SPEI3` are an observed
provider-contract difference. Night 3 must use an explicit, product-versioned
source adapter grounded in the catalogue contract and validated sample values;
it must not silently infer units from arbitrary unitless input. UTCI remains the
monthly median of provider daily maximum UTCI, converted from the documented
Kelvin source unit to °C. SPEI-3 remains the provider's deterministic
dimensionless standardized index.

## Paired-grid and coverage-edge evidence

All eight UTCI/SPEI-3 comparisons and all eight SPEI-3/quality comparisons are
compatible with no coordinate transformation:

- Phoenix: latitudes 34.25, 34.00, 33.75; longitudes -112.25, -112.00, -111.75;
- Paris: latitudes 49.00, 48.75, 48.50; longitudes 2.00, 2.25, 2.50;
- Fairbanks: latitudes 65.00, 64.75, 64.50; longitudes -148.00, -147.75, -147.50;
- southern edge: latitudes -59.50, -59.75, -60.00; longitudes 0.00, 0.25, 0.50.

The returned headers therefore prove direct common-grid mapping through the
published UTCI southern boundary. The audit records the provider nodata
encodings but intentionally does not load climate arrays, so cell-value
validity, the actual quality flag at each sample cell, and values at the -60°
edge remain Night 3 normalization evidence rather than being inferred here.

The complete machine-readable result is
`pipeline/reports/night-2-observed-metadata.json`.

## Reproduction

Secret-safe access status:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire status
```

Inspect the exact bounded plan without downloading:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire plan
```

With both dataset licences accepted:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire fetch
```

Either dataset can be tested or resumed independently without changing the
full representative plan or its acceptance criteria:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire fetch \
  --dataset-id derived-utci-historical
pipeline/.venv/bin/python -m thermal_drought.acquire fetch \
  --dataset-id derived-drought-historical-monthly
```

Then create the observed-metadata and paired-grid audit:

```bash
pipeline/.venv/bin/python -m thermal_drought.acquire inspect \
  --output pipeline/reports/night-2-observed-metadata.json
```

Raw responses and receipts are written below ignored `data/raw/`. Retrieval is
not run automatically by tests or CI.
