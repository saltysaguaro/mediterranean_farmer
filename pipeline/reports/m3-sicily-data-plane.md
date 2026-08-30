# M3 Sicily data-plane status

Date: 2026-08-07
Status: official M3 data plane and M5 second-year reproducibility gates complete

## Release target

The initial release contains the two latest shared complete years, 2025 and
2024. It is a selected-year product; no reference-period SPEI median is
presented or labeled as drought risk.

- scope: `sicily_istat_2026_grid_centers`;
- acquisition box: north 39.00, west 11.75, south 35.25, east 15.75;
- publication mask: 44 exact 0.25-degree provider-grid cell centers;
- requests: 24 monthly UTCI containers of daily maxima, 24 deterministic
  selected-year SPEI-3 containers, and 12 reusable provider-quality containers;
- plan SHA-256:
  `61bbffbe2e6d742148c5d1c0f2ff3aee149bd34a7291736f575898bfe74860f6`.

The provider-quality layers remain separate from the selected-year values.
January SPEI-3 is the provider's three-month index ending in January and is not
recalculated from UI-selected months.

## Acquisition and inspection evidence

The bounded two-year preflight passed with 80.92 GiB free, a 20 GiB reserve,
an 80% volume high-water mark, and a conservative 654,311,424-byte processing
peak. Retrieval then completed serially and atomically:

- 60 artifacts and 60 checksum-bound receipts;
- 29,780,288 artifact bytes and 674,186 receipt bytes;
- 29,023,064 UTCI bytes, 371,184 selected-year SPEI-3 bytes, and 386,040
  provider-quality bytes;
- 14,689,321 selected-year artifact bytes for 2025 and 14,704,927 for 2024,
  plus the shared quality layers;
- retrieval window 2026-08-07 09:05:37–09:39:40 UTC;
- 2,081.108 seconds summed provider retrieval duration, 29.507 seconds median,
  and 55.128 seconds maximum;
- 767 inspected NetCDF archive members and 29,592,142 expanded bytes.

The exact inspection completed in 6.00 seconds. It reports 60/60 artifacts,
24 UTCI/SPEI grid comparisons, 24 SPEI/quality comparisons, official evidence
true, and no missing, unexpected, duplicate, fixture, checksum, provenance, or
grid issue. The machine-readable evidence is
`pipeline/reports/sicily-source-audit-v1.json`.

## Normalized release

Normalization completed in 13.57 seconds and wrote two ignored, atomic,
checksum-bound products:

| Year | Bytes | SHA-256 |
| --- | ---: | --- |
| 2024 | 47,317 | `99aed5cd511054b3b4d5d38bb5a4f320752ac3c86565657680dbaa4e56544fc9` |
| 2025 | 47,362 | `be458e6db12e9048f4c11bd3b302f7a7daef946f73a87e8e58da33f2303ef8e4` |

Each product has 12 monthly layers on the 16 × 17 provider box, preserves only
the 44 configured Sicily cells, and masks every outside cell. The release
report contains 24 golden records at the in-scope 13.75°E, 37.5°N cell. A
regression test prevents the former provider-box midpoint, which lies outside
the Istat mask, from being used as Sicily golden evidence.

The atomic publisher also compares decoded serialized products before replacing
an existing file. A repeat normalization preserved both checksums and file
modification times, including the outside-scope quality sentinels; a regression
test now protects this M5 reproducibility property.

The manifests are now `published`, bind the two complete years to
`sicily-2024-2025-v1`, and carry source-retrieval completion timestamps. The
service rejects an official release paired with a planned manifest, a missing
retrieval timestamp, or mismatched manifest years.

## Local service and preview evidence

The official catalogue reports two products, both complete years, all 12
months, official evidence true, and latest complete year 2025. At the golden
cell, the 2025 all-year response returns SPEI-3 `0.0675170161` and UTCI
`24.1029682159 °C`, with 12/12 valid months for both variables and provider
quality passing for all drought months.

Twenty local calls per year measured 9.997–10.486 ms median for the 44-cell
all-year tile path and 9.665–10.164 ms median for the point path. The WSGI
responses measured 58,258 bytes for 2025 and 58,197 bytes for 2024. These are
single-machine local facts, not production p95 claims.

Real Chromium opened on 2025/all-year, switched to 2024, restored the disjoint
`109` mask (Jan + Apr + Sep), rendered univariate mode, and returned the
official point values and retrieval dates. The session had zero console errors
or warnings.

## Disposition

M3 and M5 are complete. M4 remains open for production container/runtime,
request limits, metrics, cache behavior, and representative production latency.
M6 remains open for a production-shaped hosted preview and its authorization-
controlled routing/deployment gates. Raw archives and published NetCDFs remain
ignored and outside Git; no deployment, DNS/CORS, commit, tag, or push occurred.
