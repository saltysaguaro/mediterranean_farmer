# Seven-Day Sicily Bivariate Map Build

Execution window: July 23–29, 2026  
Nightly start: 2:00 AM America/Phoenix  
Source of truth: `PROJECT_PLAN.md`

## Post-sprint continuation

Nights 1–6 produced the bounded official-data vertical slice documented in
`progress.md`; Night 7 remains incomplete. After the Night 7 beta handoff, work
continues through milestones M2–M8 in
[`COMPLETION_FOUNDATION.md`](./COMPLETION_FOUNDATION.md). The calendar no longer
determines progress: the earliest unmet acceptance or milestone gate remains
active until evidence closes it. Historical backfill and legacy cleanup are M9
and do not begin before the replacement completes the release and rollback
gates.

The user changed the geographic product scope to Sicilia on 6 August 2026.
References below to the original global sprint describe historical work only;
all continuing implementation and acceptance gates use `config/scope.json`.

## Sprint outcome

At the end of the seventh nightly session, the repository should contain a working, production-shaped vertical slice of the Sicily Human Thermal Comfort × Drought map:

- a maintainable source layout rather than hand-edited generated files;
- validated, variable-neutral UTCI and SPEI-3 registry entries;
- reproducible source-acquisition and normalization code;
- median, missing-data, classification, month-mask, and compatibility logic;
- a Sicily-bounded map shell with an accessible circular month selector;
- univariate and 3 × 3 bivariate legends;
- point inspection, URL state, and clear source/methodology information;
- a local sample/tile path backed by real source data when credentials and download capacity permit;
- a visibly labeled deterministic test fixture when source access is unavailable;
- automated scientific, contract, logic, UI, accessibility, and build checks;
- a generated preview build in `docs/`;
- an explicit list of work still required for production data backfill, hosting, monitoring, and launch.

This sprint does not silently weaken the scientific specification to meet the date. It must not fabricate climate observations, call suitability scores UTCI or SPEI, or present synthetic fixtures as real data.

## Operating rules for every night

1. Read `README.md`, `PROJECT_PLAN.md`, this file, and `progress.md`.
2. Inspect Git status and preserve all user changes.
3. Resume the earliest incomplete night; do not skip a failed acceptance gate merely because the calendar advanced.
4. Complete one coherent, reviewable slice. If blocked, finish independent work and record the exact blocker.
5. Add or update tests alongside behavioral changes.
6. Run the relevant tests, type checks, lint checks, builds, and smoke checks available in the repository.
7. Update `progress.md` with files changed, checks run, decisions, blockers, and the next action.
8. Leave the working tree coherent. Do not delete legacy rasters, rewrite unrelated work, push, deploy, purchase services, contact people, or expose credentials.

## Day 1 — Thursday, July 23: foundation and contracts

### Objective

Create the source-controlled foundation that every later night can build on.

### Work

- Record the pre-sprint Git state and legacy-app behavior in `progress.md`.
- Create the planned `config/`, `pipeline/`, `services/`, `web/`, and `tests/` structure.
- Add reproducible Python and web dependency manifests and lockfiles when the installed tooling permits.
- Configure standard test, type-check, lint, and production-build commands.
- Define and validate the public variable-manifest JSON Schema.
- Add initial registry entries for:
  - `utci_daymax_median`;
  - `spei_3`.
- Implement the shared 12-bit month-mask representation and period formatter.
- Add test fixtures for valid and invalid manifests.
- Extend `.gitignore` for raw downloads, credentials, canonical arrays, caches, generated tiles, and local environments.

### Acceptance gate

- Both real variable entries validate.
- Deliberately invalid entries fail with actionable errors.
- Every month mask from 1 through 4095 round-trips between selected months, integer mask, hexadecimal URL value, and period label.
- An empty selection is rejected.
- One documented command runs the foundation checks.

## Day 2 — Friday, July 24: official-data access proof

### Objective

Prove that the selected official products can be acquired and aligned without beginning an uncontrolled full-history backfill.

### Work

- Check for usable CDS credentials without printing or committing them.
- Implement restartable acquisition request builders for:
  - ERA5-HEAT daily maximum UTCI;
  - deterministic ERA5-Drought SPEI-3 and its quality fields.
- Store request metadata, dataset/product version, retrieval time, checksum, units, coordinates, licence, DOI, and citation.
- Acquire a small representative subset covering at least:
  - one hot/arid region;
  - one temperate region;
  - one cold region;
  - one UTCI no-data edge if the provider permits.
- Use at least two months with different seasons.
- If source access is blocked, keep request generation fully testable and create a conspicuously labeled deterministic fixture under `tests/fixtures/`; do not invent a “sample from ERA5.”
- Produce a data-access report documenting download sizes, latency, dimensions, coordinate order, time frequency, quality variables, and any provider changes from the planning assumptions.

### Acceptance gate

- Acquisition is restartable and does not redownload a verified file.
- Credentials and raw downloads are ignored by Git.
- Source metadata and checksums are retained.
- The UTCI and SPEI sample coordinates can be mapped to the common grid or the mismatch is precisely documented.
- No test fixture can be mistaken for production climate data.

## Day 3 — Saturday, July 25: normalization and monthly products

### Objective

Turn the acquisition proof into a reproducible canonical-data path.

### Work

- Normalize longitude, latitude order, CRS, time, calendar, units, nodata, and coordinate names.
- Convert UTCI units according to source metadata and fail on unexpected units.
- Select daily maximum UTCI and calculate the monthly median per grid cell.
- Select provider SPEI with the three-month accumulation without recomputing its window.
- Preserve and apply the provider’s SPEI quality information.
- Implement the documented 75% selected-month validity rule.
- Write a compact local published representation suitable for service and frontend development.
- Produce golden samples with source references, expected values, precision, class, and quality status.

### Acceptance gate

- Clean input produces deterministic normalized output.
- Re-running the pipeline is idempotent.
- Coordinate, unit, nodata, time, valid-range, and shape assertions pass.
- UTCI monthly medians and SPEI sample values match an independent calculation within documented tolerance.
- Invalid or low-quality cells remain no data or flagged; they never become zero.

## Day 4 — Sunday, July 26: aggregation, classification, and data service

### Objective

Provide one shared implementation for map tiles and point values.

### Work

- Implement median aggregation across selected monthly layers.
- Implement fixed UTCI and SPEI-3 classifications from the registry.
- Implement variable compatibility and one- or two-variable selection rules.
- Add versioned cache keys covering data, variables, year, month mask, statistic, thresholds, palette, and software version.
- Build the local service endpoints described in `PROJECT_PLAN.md`:
  - availability;
  - health;
  - point sample;
  - a development raster/tile response.
- Bound year, month-mask, coordinate, tile, and zoom inputs.
- Add deterministic no-data, quality-warning, and error responses.

### Acceptance gate

- All 4095 month masks match a simple reference median implementation.
- Odd, even, one-month, all-year, missing-value, and threshold-boundary tests pass.
- Point sampling and the corresponding raster cell return the same values and classes.
- January SPEI-3 remains the source’s three-month index ending in January.
- Invalid input cannot trigger an unbounded read or computation.

## Day 5 — Monday, July 27: map and circular month interaction

### Objective

Deliver the core user experience against the local data path.

### Work

- Build the TypeScript frontend and map shell.
- Keep the map visually dominant on desktop and narrow screens.
- Render variable selectors from the public manifest.
- Support:
  - one selected variable as a univariate map;
  - two compatible variables as a bivariate map;
  - axis swap;
  - no more than two active variables.
- Implement the twelve-wedge circular selector with:
  - native buttons;
  - January-to-December DOM order;
  - pointer, touch, and keyboard operation;
  - `aria-pressed`;
  - visible focus;
  - a non-circular fallback;
  - final-month protection;
  - center “All year” action;
  - adjacent text period summary.
- Serialize variables, year, month mask, map location, and zoom to the URL.

### Acceptance gate

- Arbitrary disjoint months such as January + April + September work.
- Reload and browser back/forward restore the same state.
- The final selected month cannot be cleared.
- The control works without a pointer.
- Month changes preserve the last valid map until replacement data is ready.
- Mobile and desktop layouts retain a useful map area without overlap.

## Day 6 — Tuesday, July 28: bivariate explanation and integration

### Objective

Make the map interpretable, inspectable, extensible, and resilient.

### Work

- Implement the fixed 3 × 3 bivariate legend with correct axis orientation, thresholds, units, and paired text labels.
- Add no-data treatment outside the nine-color matrix.
- Link map inspection to the relevant legend cell.
- Add a point readout with exact values, classes, valid-month count, quality state, source version, update date, and grid-cell limitation.
- Add sources, methodology, temporal semantics, and limitations panels.
- Add loading, stale-data, empty, no-data, service-error, and retry states.
- Add a clearly labeled artificial third variable fixture to prove that registry configuration, not hard-coded names, drives selection and rendering.
- Run automated accessibility checks and manual keyboard review.

### Acceptance gate

- All nine bivariate states can be identified through text as well as color.
- Swapping axes consistently changes selector, legend, tile request, and readout orientation.
- The artificial compatible variable requires no change to generic selector, median, legend, or sampling code.
- Source and quality information is visible at the point of interpretation.
- Failure states never replace missing data with zero or leave a silently stale title.

## Day 7 — Wednesday, July 29: hardening and beta handoff

### Objective

Leave a verified beta and an honest production-readiness report.

### Work

- Run the complete scientific, schema, unit, integration, UI, accessibility, visual, and production-build suite.
- Exercise at least:
  - hot/arid;
  - tropical;
  - temperate;
  - cold;
  - coastal;
  - mountain;
  - quality-warning;
  - no-data cases.
- Check responsive layouts in current Chromium, Firefox, and WebKit when available.
- Measure bundle size, tile size, cached and uncached updates, sample latency, layout shift, and local interaction latency.
- Fix high-severity regressions within the sprint’s scope.
- Generate the preview frontend into `docs/` without deleting the legacy assets until routing and rollback are verified.
- Update setup, acquisition, development, test, build, data-refresh, and preview instructions.
- Produce a final gap report separating:
  - complete beta capabilities;
  - source-access or data-volume blockers;
  - production service/storage decisions;
  - historical backfill;
  - scientific review;
  - palette comprehension study;
  - monitoring, refresh, deployment, and rollback work.

### Acceptance gate

- A fresh checkout can follow the documented setup and run the supported checks.
- The preview build completes and core flows pass a smoke test.
- No P0 scientific, data-integrity, accessibility, or security defect is knowingly left open.
- `progress.md` records every check and any unmet performance target.
- The legacy data remains recoverable and no production deployment or push occurs without explicit authorization.

## Daily status format

Append one section per run to `progress.md`:

```text
## YYYY-MM-DD — Night N

Goal:
Completed:
Files changed:
Checks:
Decisions:
Blockers:
Next:
```

## Seven-day definition of done

The sprint is successful if the repository contains a coherent beta vertical slice and trustworthy evidence about what works. It is not successful merely because seven scheduled runs occurred.

Any of the following must remain clearly labeled as incomplete if not actually achieved:

- official-data access and sample verification;
- full-history production data backfill;
- production tile/storage deployment;
- independent climate-science review;
- bivariate-palette comprehension testing;
- performance budgets on production infrastructure;
- operational refresh and rollback rehearsal.
