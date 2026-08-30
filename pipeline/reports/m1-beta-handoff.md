# M1 bounded beta handoff

Status: official local preview complete; M1 remains active for unavailable validation gates
Measured: 2026-08-07 America/Phoenix
Scope: complete official 2025 and 2024 Sicily release

## Completed slice

One loopback origin serves the ignored replacement bundle at `/preview/`, the
unchanged legacy tree at `/legacy/`, and the official service at `/api/v1/`.
Stopping the process or opening `/legacy/` is the local rollback. No source-
controlled release pointer, deployment route, DNS, CORS, climate product, or
legacy asset is changed.

`make beta-preview-check` verifies every generated file, rejects source maps
and symbolic links, enforces transfer budgets, inventories the legacy boundary,
and writes only ignored output. Five routing/inventory tests cover preview,
legacy, API, cache headers, `HEAD`, traversal, unsafe methods, source maps, and
symbolic links.

## Build and route evidence

The current build has five files, 1,180,118 raw bytes, and 311,137 deterministic
gzip bytes including MapLibre.

| Budget | Measured | Target | Result |
| --- | ---: | ---: | --- |
| Application JavaScript, MapLibre excluded | 14,683 gzip bytes | < 256,000 | Pass |
| Initial application data, MapLibre excluded | 18,842 gzip bytes | < 1,048,576 | Pass |

MapLibre remains separate at 1,053,029 JavaScript bytes / 282,253 gzip and
69,918 CSS bytes / 10,042 gzip. The legacy route serves all 753 files and 744
rasters in place.

The API reports two checksum-verified official products, 2025 as the latest
complete year, all twelve months for both years, official evidence true, and
fixture false. The 44-cell all-year WSGI payloads are 58,197–58,258 bytes.

## Chromium evidence

Real Chromium exercised the replacement through the same-origin preview:

- the initial URL, title, period, and controls restored 2025 and all 12 months;
- switching to 2024 updated the URL, title, map, and readout;
- `months=109` restored Jan + Apr + Sep exactly;
- clearing Axis Y produced the univariate SPEI-3 legend and request path;
- the 2025 in-scope all-year point returned SPEI-3 `0.0675` / `No drought`
  and UTCI `24.103 °C` / `No thermal stress`, with 12/12 valid months and
  provider drought quality passing 12/12;
- source panels and the point readout displayed the 7 August 2026 retrieval
  date, products, versions, DOI, units, and limitations;
- 390 × 844 and 1280 × 800 visual inspection retained a useful map and readable
  controls without overlap;
- the DOM audit found zero duplicate IDs, unnamed controls, or hidden
  focusables, with one H1 and two status regions;
- the console reported zero errors and zero warnings;
- DOM content loaded in 51.0 ms and the load event in 52.1 ms.

Screenshots remain ignored below `output/playwright/`. Browser and service
measurements are local observations, not representative-device or production
p95 evidence.

## Open M1 and production gaps

- Tropical and cold cases cannot be official Sicily observations. Tropical,
  cold, mountain, coastal, urban-adjacent, and broader no-data interface cases
  still need conspicuously labeled structural golden fixtures or an explicitly
  scoped external evidence set.
- Firefox, WebKit, axe, live screen-reader, grayscale, and color-vision tools
  are unavailable. Current evidence is Chromium semantics, keyboard behavior,
  deterministic text contrast, and responsive visual inspection.
- The palette remains developmental. Independent climate/licensing review and
  the palette-comprehension study are external gates.
- Production container/runtime limits, metrics, cache behavior, hosted preview,
  monitoring, refresh, and rollback rehearsal remain M4–M8 work.
- The recoverable legacy tag remains pending explicit authorization.

M1 is not closed. The next independent M1 slice should add the conspicuously
structural location matrix and exercise it through the unchanged aggregation,
service, point, legend, and browser paths without publishing it as observation.
