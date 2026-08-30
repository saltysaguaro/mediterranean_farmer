# M7 review and hardening evidence

Status: automated engineering review complete; independent approvals pending.

## Completed gates

- Scientific behavior is shared across map and point paths and is covered by
  11 conspicuously non-observational structural scenarios, all nine class
  pairs, no-data, provider-quality failure, exact threshold ownership, the 75%
  validity rule, and even-month medians.
- Official provenance is checksum-bound to the 60-request plan, 44-cell Istat
  scope, product versions, DOIs, retrieval timestamps, reference period,
  licences, visible Copernicus attribution, and disclaimer. The UI links all
  source and licence records and labels the Istat boundary as transformed.
- The nine palette colors retain a minimum 8-bit RGB distance above 20 under
  deterministic protanopia, deuteranopia, and tritanopia simulations. The
  palette spans more than 0.4 display-luminance units in grayscale, every
  state has a text label and numeric range, and every legend foreground meets
  4.5:1 contrast.
- Chromium, Firefox, and WebKit core flows pass with zero application console
  errors. axe reports zero violations across the three engines; the single
  overlay-background item is manually resolved by computed foreground and
  solid-background inspection.
- Runtime probes cover method, CORS, mask, zoom, and dataset rejection. The API
  enforces request, response, concurrency, rate, cache, zoom, cell, year,
  variable, and release bounds. Archive inspection rejects traversal, links,
  encryption, duplicates, checksum mismatch, and expansion excess.
- Python, TypeScript, manifest, repository/secret, dependency, official-data,
  parity, latency, cache, rollback, refresh, and monitor gates are automated.
  CI also builds both conventional container images with SBOM and provenance
  on an authorized release tag.

## Independent gates that cannot be self-approved

The project plan explicitly requires an independent climate-science review,
licensing/attribution review, and palette-comprehension study. It also calls
for live assistive-technology use beyond automated semantics. No reviewer,
participant panel, or target screen-reader/device was supplied, so these gates
remain open and are not represented as agent approval. There is no known open
automated P0/P1 defect.
