# M2 Sicily format and architecture decision

Date: 2026-08-07
Status: measured format decision complete and confirmed with official data

## Decision

Use one compressed NetCDF product per complete Sicily year and lossless sparse
JSON service responses for the initial product. Keep Zarr, COG, raster tiles,
and a CDN as future scale triggers rather than initial requirements.

The scope has 44 target cells at 0.25°, two variables, one provider quality
layer, twelve monthly layers, and two initial years. At this cardinality a
raster envelope and remotely chunked store add operational failure modes
without adding resolution or reducing a meaningful payload. The shared median,
classification, point, and tile paths remain variable-neutral and versioned.

## Structural benchmark

`make format-benchmark-check` creates only a temporary dataset labeled
`STRUCTURAL FORMAT BENCHMARK — NOT CLIMATE OBSERVATIONS`.

- shape: 12 × 16 × 17 provider grid, 44 included cells;
- compressed NetCDF: 28,629 bytes;
- equivalent lossless sparse JSON: 22,594 bytes raw / 5,610 deterministic gzip;
- exact value, nodata, quality, coordinate, and mask parity: passed;
- 63.827 ms local write and 13.645 ms point open/read/close in the final run.

## Official confirmation

The complete official products are 47,317 bytes for 2024 and 47,362 bytes for
2025. The all-year 44-cell service payloads measured 58,197 and 58,258 WSGI
bytes respectively, both below the 200 kB response target. Compact deterministic
JSON was 54,325–54,386 bytes and 2,772–2,791 gzip bytes.

Across 20 calls per year, the local all-year tile path measured 9.997–10.486 ms
median and the in-scope point path 9.665–10.164 ms median. Values, class indices,
quality counts, mask membership, and coordinates retained exact parity. These
are local development measurements, not production p95 evidence.

The official files remain many orders of magnitude below the per-file, managed-
directory, response, and two-year storage limits. No scale trigger currently
justifies Zarr, COG, raster encoding, or object storage for the initial 44-cell
release.

## Release architecture

- Raw responses and receipts remain ignored under `data/raw/`.
- Each year is atomically published below
  `data/published/sicily-release-v1/v1/{year}/sicily.nc`.
- `pipeline/reports/sicily-release-v1.json` binds the products to the exact
  60-request source fingerprint and Istat boundary checksum.
- The service verifies checksums, variables, months, scope mask, bounds, and
  official/fixture provenance before serving.
- Strong release-scoped ETags preserve cache identity.
- A hosted runtime and persistent artifact location still require explicit
  authorization; neither was created in this milestone.
