# Sicily Thermal Comfort × Drought Progress

This log is updated by the seven-night implementation sprint defined in `SEVEN_DAY_PLAN.md`.

## Sprint status

- Window: continuous completion after the July 23–29, 2026 beta sprint
- Nightly start: 2:00 AM America/Phoenix
- Active execution plan: `COMPLETION_FOUNDATION.md`
- Current milestone: M0–M6 engineering gates complete; M7 automated hardening and M8 local operations rehearsals complete. M7 independent review and M8 public cutover/monitored-cycle gates remain open; M9 is correctly gated behind them.
- Next scheduled run: configure an owner-supplied production endpoint, durable HTTPS bundle, TLS/DNS, alert target, and reviewers; complete one monitored release cycle and only then authorize M9 backfill/legacy cleanup.
- Completed nights: Nights 1, 2, 3, 4, 5, and 6
- Night 6 status: acceptance gate complete for fixed univariate/3 × 3 legends, text-identifiable bivariate states, point-linked interpretation, source/quality/retrieval metadata, methodology and limitations, truthful loading/stale/empty/no-data/error/retry states, axis orientation, and the artificial third-variable proof
- Current blockers: independent climate/licensing approval, palette-comprehension evidence, and live assistive-technology review; plus an owner-supplied public runtime, DNS/TLS, durable bundle URL, alert receiver, registry release, and monitored production cycle. Automated browser, accessibility, color-vision, performance, monitoring, refresh, security, and rollback rehearsals pass locally.

## Pre-sprint state

- `docs/` contains the legacy Mediterranean Leaflet prototype and generated crop-suitability rasters.
- `PROJECT_PLAN.md` originally defined a global product; the 2026-08-06 scope
  decision below supersedes that target with Sicily only.
- `SEVEN_DAY_PLAN.md` defines the seven-night beta implementation sequence.
- The legacy application and rasters must remain untouched until the replacement has passed its release gates.

## Run log

## 2026-07-23 — Night 1

Goal:

- Recover the missed scheduled run and complete the foundation and contracts gate.

Completed:

- Confirmed that the original automation produced no run artifact, progress entry, or repository change even though the Mac and Codex app were awake.
- Replaced the suspect daily/count recurrence with a bounded weekly-by-day schedule for the six remaining 2:00 AM runs through July 29.
- Added the target `config/`, `pipeline/`, `services/`, `web/`, `tests/`, and CI structure.
- Added a Draft 2020-12 public variable-manifest schema.
- Added validated `utci_daymax_median` and `spei_3` registry entries.
- Added canonical 12-bit month-mask conversion, three-digit hexadecimal URL serialization, and period formatting.
- Added invalid-manifest fixtures and exhaustive round-trip tests for all 4095 non-empty month masks.
- Added pinned Python and web dependency manifests, generated `web/package-lock.json`, and configured test, strict type-check, lint, and production-build commands.
- Expanded `.gitignore` to exclude credentials, raw/canonical climate data, caches, local environments, generated tiles, and dependencies.

Files changed:

- `.github/workflows/checks.yml`
- `.gitignore`
- `Makefile`
- `config/app.json`
- `config/manifest.schema.json`
- `config/variables/*.json`
- `pipeline/pyproject.toml`
- `pipeline/src/thermal_drought/*.py`
- `pipeline/tests/*.py`
- `services/README.md`
- `tests/fixtures/manifests/invalid-missing-id.json`
- `web/index.html`
- `web/package.json`
- `web/package-lock.json`
- `web/tsconfig.json`
- `web/vite.config.ts`
- `web/src/*`

Checks:

- Python tests: 17 passed.
- Variable contracts: 2 manifests validated.
- Month masks: all values 1–4095 round-trip in tests.
- Ruff: passed.
- Mypy strict mode: passed.
- TypeScript type-check: passed.
- Vitest: 1 passed.
- Vite production build: passed.
- Dependency audit: 0 reported npm vulnerabilities.
- `git diff --check`: passed.

Decisions:

- Registry entries remain `planned` with `data_version: unpublished` until official source acquisition is verified.
- The SPEI axis reverses display order while preserving ascending raw-value classification.
- The web build is an intentionally minimal foundation page; map behavior begins on Night 5.

Blockers:

- None for Night 1.

Next:

- Night 2: verify official CDS access without exposing credentials, build restartable request metadata, and acquire or transparently substitute the documented representative test fixtures.

## 2026-07-23 — Night 2

Goal:

- Prove official ERA5-HEAT and ERA5-Drought access on a bounded representative
  sample, or complete every independent acquisition task and record the exact
  access blocker without presenting fixtures as climate observations.

Completed:

- Checked CDS access without reading or printing secrets. No `.cdsapirc`,
  `CDSAPI_URL`, or `CDSAPI_KEY` is present; `cdsapi` is not installed in the
  current pipeline environment.
- Verified the current public Copernicus catalogue, form, and constraint
  contracts for ERA5-HEAT v1.1 and ERA5-Drought v1.0.
- Added bounded request builders for 2024 January and July across hot/arid,
  temperate, cold, and ERA5-HEAT southern-limit regions.
- Added separate requests for provider daily UTCI statistics, deterministic
  year/month SPEI-3, and the month-specific SPEI normality-quality layer.
- Split SPEI-3 values from `test_for_normality_spei` because the official
  constraint metadata exposes the quality field by calendar month and
  accumulation period, not analysis year.
- Added atomic `.part` retrieval, exact request fingerprints, byte counts,
  SHA-256 checksums, UTC timestamps, source/version/licence/DOI/citation
  receipts, and verified-file restart behavior.
- Added corruption recovery, empty-response failure, and a safeguard that a
  fixture receipt can never verify a production-mode acquisition.
- Added a conspicuously labeled deterministic text fixture containing no
  observations or physical climate values.
- Added a data-access report recording provider metadata, the 24-partition
  plan, unmeasured download facts, the unresolved grid-alignment evidence, and
  reproduction commands.

Files changed:

- `README.md`
- `Makefile`
- `pipeline/pyproject.toml`
- `pipeline/src/thermal_drought/acquire/__init__.py`
- `pipeline/src/thermal_drought/acquire/__main__.py`
- `pipeline/src/thermal_drought/acquire/cli.py`
- `pipeline/src/thermal_drought/acquire/requests.py`
- `pipeline/src/thermal_drought/acquire/runner.py`
- `pipeline/tests/test_acquisition.py`
- `pipeline/reports/night-2-data-access.md`
- `tests/fixtures/acquisition/DETERMINISTIC_NOT_ERA5_PAYLOAD.txt`
- `tests/fixtures/acquisition/README.md`
- `progress.md`

Checks:

- Full Python suite: 25 passed.
- Acquisition tests: 8 passed.
- Variable contracts: 2 manifests validated.
- Representative plan: 24 bounded requests covering three source-layer types,
  four regions, and two seasons.
- Secret-safe access status: all credential/client availability fields false;
  no secret values emitted.
- Ruff: passed.
- Mypy strict mode: passed.
- TypeScript type-check: passed.
- Vitest: 1 passed.
- Vite production build: passed.
- npm audit: 0 reported vulnerabilities.
- `git diff --check`: passed.

Decisions:

- Use the consolidated provider products for the reproducible proof rather than
  near-real-time intermediate data.
- Request ERA5-HEAT daily-statistics files and defer daily-maximum field
  selection, K-to-°C conversion, and monthly median calculation to Night 3
  after observed NetCDF metadata is available.
- Request deterministic ERA5-Drought `reanalysis`, accumulation period 3,
  directly; never recalculate January SPEI-3 from selected UI months.
- Keep provider quality layers independent of analysis year while associating
  them by accumulation period, calendar month, and grid cell.
- Treat advertised 0.25° grids as an alignment hypothesis only. Do not
  interpolate or claim matching cell centers until paired official files are
  inspected.
- Keep fixture and production receipt modes distinct so deterministic test
  content cannot satisfy a production verification check.

Blockers:

- Official retrieval is blocked by absent CDS credentials. The authenticated
  account's acceptance of both dataset licences also cannot be confirmed.
- The optional `cdsapi` dependency is not installed in `pipeline/.venv`.
- Therefore download size, latency, returned dimensions, coordinate order,
  cell-center alignment, actual NetCDF variable/unit metadata, no-data
  encoding, quality values, and UTCI coverage-edge behavior remain unverified.
- No ERA5, ERA5-HEAT, or ERA5-Drought file was downloaded, and no fixture is
  represented as one.

Next:

- Remain on Night 2. After CDS credentials and dataset-term acceptance are
  available, install `pipeline[data,dev]`, run the bounded fetch, inspect and
  record observed NetCDF metadata, compare paired cell centers, measure size
  and latency, and close the acceptance gate before starting Night 3.

## 2026-07-24 — Night 2

Goal:

- Continue the earliest incomplete gate by making official sample metadata,
  latency, plan completeness, and paired-grid evidence automatically auditable
  as soon as authenticated retrieval becomes available.

Completed:

- Rechecked secret-safe access state. The CDS client is now installed, but no
  `.cdsapirc`, `CDSAPI_URL`, or `CDSAPI_KEY` is present.
- Added retrieval-duration measurement and explicit year/month metadata to
  acquisition receipts while preserving checksum-based restart behavior.
- Added a structural NetCDF inspector backed by optional
  `xarray`/`h5netcdf`/`h5py` dependencies.
- Made inspection verify receipt paths, byte sizes, and SHA-256 checksums before
  opening an artifact.
- Made production inspection reject fixture receipts by default. An explicit
  test-only fixture path remains labeled non-official and can never complete
  the acceptance audit.
- Added header-only evidence for dimensions, shapes, attributes, units, nodata,
  coordinate names, coordinate values, order, endpoints, and regular step.
  Climate data arrays are not loaded by this audit.
- Added cell-center comparison for every UTCI/SPEI-3 region-year-month pair and
  every SPEI-3/provider-quality pair.
- Distinguished reversible latitude reordering and longitude-convention
  normalization from actual coordinate mismatch; no interpolation is proposed
  or performed.
- Required the exact 24-request plan, every non-fixture artifact, every source
  and quality pairing, and compatible observed cell centers before an audit can
  report completion.
- Added a machine-readable `inspect` CLI and documented the authenticated
  fetch-to-audit workflow.
- Installed and exercised the CDS client plus structural NetCDF reader
  dependencies locally. The NetCDF integration test creates only a
  coordinate-only file conspicuously labeled as non-climate data.

Files changed:

- `README.md`
- `Makefile`
- `pipeline/pyproject.toml`
- `pipeline/src/thermal_drought/acquire/__init__.py`
- `pipeline/src/thermal_drought/acquire/cli.py`
- `pipeline/src/thermal_drought/acquire/inspection.py`
- `pipeline/src/thermal_drought/acquire/runner.py`
- `pipeline/tests/test_acquisition.py`
- `pipeline/reports/night-2-data-access.md`
- `progress.md`

Checks:

- Full Python suite: 31 passed.
- Acquisition suite: 14 passed, including fixture exclusion, plan-completeness
  evidence, grid order/convention comparison, checksum verification, and a
  local structural NetCDF header read.
- Variable contracts: 2 manifests validated.
- Representative plan: 24 requests, 24 unique IDs, and `fixture: false`.
- Secret-safe status: `cdsapi` installed; all credential-presence fields false;
  no secret value read or emitted.
- Fetch preflight: exited 2 before network access with the precise missing
  credential blocker.
- Observed-metadata preflight: exited 2 with `artifact_count: 0`,
  `expected_request_count: 24`, all 24 missing request IDs, and
  `official_evidence: false`.
- Ruff: passed.
- Mypy strict mode: passed across 9 source files.
- TypeScript typecheck: passed.
- Vitest: 1 passed.
- Vite production build: passed.
- npm audit: 0 reported vulnerabilities.
- `git diff --check`: passed.
- No service, end-to-end, visual, or accessibility command exists yet at this
  Night 2 stage; none was skipped.
- Legacy `docs/` application and rasters: unchanged.

Decisions:

- Treat the audit as complete only with an explicit expected request plan.
  A partial official subset cannot accidentally close the Night 2 gate.
- Read full coordinate arrays for the bounded samples but only structural
  metadata for climate variables.
- Permit order and longitude-convention normalization only after equivalent
  cell-center sets are proven; otherwise report an exact mismatch.
- Keep observed metadata in both atomic acquisition receipts and an optional
  machine-readable report so later normalization has reproducible source
  evidence.
- Keep selected-year SPEI-3, reference-period provider quality, and UTCI daily
  statistics as separate artifacts with explicit period semantics.

Blockers:

- Official retrieval remains blocked by absent CDS credentials.
- Acceptance of both dataset terms by the eventual authenticated CDS account
  remains unconfirmed.
- `data/raw` is absent, so 0 of 24 official artifacts have been inspected.
- Returned dimensions, variable names, units, nodata, coordinate order, exact
  cell centers, quality values, download sizes/latencies, and UTCI coverage-edge
  behavior therefore remain unverified. No fixture is used to fill those facts.

Next:

- Remain on Night 2. When credentials and dataset-term acceptance are
  available, run the bounded 24-partition fetch, run the observed-metadata
  audit, record actual sizes and latency, resolve any provider-field changes,
  and close the paired-grid gate only if every official source and quality
  artifact verifies.

## 2026-07-25 — Night 2

Goal:

- Continue the earliest incomplete gate by making the official-data evidence
  set cryptographically identifiable and preventing stale, altered, duplicate,
  or out-of-plan receipts from satisfying the 24-partition acceptance audit.

Completed:

- Re-read the four required project documents in full and inspected the complete
  working-tree, package-script, acquisition, test, configuration, report, and
  legacy-preservation state.
- Rechecked secret-safe access state. `cdsapi` remains installed, but no
  `.cdsapirc`, `CDSAPI_URL`, or `CDSAPI_KEY` is present.
- Added an order-independent SHA-256 fingerprint over the complete acquisition
  plan, including request bodies, regions, periods, canonical targets, and
  source metadata.
- Added the fingerprint to both `plan` output and observed-metadata audit
  reports. The current 24-request plan fingerprint is
  `04989c737e477ab6aba89ee884014c03e3c87cfc8ca91ddbeb4c2e1f4839dee1`.
- Bound every inspected receipt to its exact planned request by checking receipt
  schema, dataset, variable, product version, request body and hash, period,
  region, source metadata, artifact path, and canonical receipt path.
- Made unexpected receipts, duplicate request IDs, and all receipt-to-plan
  mismatches explicit report fields that prevent audit completion.
- Made the inspector skip mismatched receipts without opening their artifacts or
  writing observed metadata into them.
- Added tests for plan-fingerprint stability and coverage, modified receipt
  rejection, unexpected artifacts, duplicate request IDs, exact-plan report
  fields, and the rule that mismatched receipts remain unmodified.

Files changed:

- `README.md`
- `pipeline/src/thermal_drought/acquire/__init__.py`
- `pipeline/src/thermal_drought/acquire/cli.py`
- `pipeline/src/thermal_drought/acquire/inspection.py`
- `pipeline/src/thermal_drought/acquire/requests.py`
- `pipeline/tests/test_acquisition.py`
- `pipeline/reports/night-2-data-access.md`
- `progress.md`

Checks:

- Full Python suite: 34 passed.
- Acquisition suite: 17 passed.
- Variable contracts: 2 manifests validated.
- Representative plan: 24 unique non-fixture requests with the expected stable
  plan fingerprint.
- Secret-safe status: `cdsapi` installed; all credential-presence fields false;
  no secret values read or emitted.
- Fetch preflight: exited 2 before network access with the precise missing
  credential blocker.
- Observed-metadata preflight: exited 2 with `artifact_count: 0`,
  `expected_request_count: 24`, all 24 request IDs missing, no unexpected or
  duplicate receipts, and `official_evidence: false`.
- Ruff: passed.
- Mypy strict mode: passed across 9 source files.
- Python dependency consistency (`pip check`): passed.
- TypeScript typecheck: passed.
- Vitest smoke test: 1 passed.
- Vite production build: passed.
- Local npm dependency tree: valid.
- Offline npm audit: 0 vulnerabilities reported. The live registry audit could
  not be completed because sandbox policy rejected transmitting the dependency
  manifest; no bypass was attempted.
- `git diff --check`: passed on the completed working tree.
- Legacy `docs/` application and rasters: unchanged.
- `data/raw`: still absent.
- No service, end-to-end, visual, or accessibility command exists yet at this
  Night 2 stage; none was skipped.

Decisions:

- Identify the full bounded plan separately from per-request fingerprints so an
  audit can prove both set completeness and individual receipt integrity.
- Treat extra receipts as a failed exact-plan audit rather than silently
  ignoring them.
- Do not inspect or enrich a receipt whose provenance does not exactly match the
  expected plan, even when its referenced artifact checksum is internally
  consistent.
- Keep fixtures usable for structural tests only; fixture evidence still cannot
  close the official-data gate.

Blockers:

- Official retrieval remains blocked by absent CDS credentials.
- Acceptance of both dataset terms by the eventual authenticated CDS account
  remains unconfirmed.
- `data/raw` is absent, so 0 of 24 official artifacts have been inspected.
- Returned dimensions, variables, units, nodata, cell centers, quality values,
  sizes/latencies, and UTCI coverage-edge behavior remain unverified. No fixture
  supplies those facts.
- A live npm registry vulnerability audit was disallowed by sandbox policy;
  only the successful offline audit is evidence for this run.

Next:

- Remain on Night 2. When credentials and dataset-term acceptance are
  available, fetch the fingerprinted 24-partition plan, run the exact-plan
  observed-metadata audit, record actual sizes and latency, resolve any
  provider-field changes, and close the paired-grid gate only if every official
  source and quality artifact verifies.

## 2026-07-26 — Night 2

Goal:

- Resume the earliest incomplete gate, use the newly available CDS
  configuration to test official access, and make any provider access failure
  precise, secret-safe, and independently auditable for both source datasets.

Completed:

- Re-read the four required project documents in full and inspected Git status,
  package scripts, current source, tests, configuration, reports, user changes,
  ignored raw-data state, and legacy preservation state.
- Rechecked secret-safe access status. A non-empty `.cdsapirc` is now present
  and `cdsapi` is installed; no credential value was opened or emitted.
- Reached the official CDS API with the exact first ERA5-HEAT request in the
  fingerprinted plan. CDS returned HTTP 403 because the account has not accepted
  the required ERA5-HEAT licence.
- Independently reached CDS with the exact first ERA5-Drought request. CDS
  returned HTTP 403 because the account has not accepted the required
  ERA5-Drought licence.
- Added dataset-scoped fetching so either official source can be tested or
  resumed without submitting the other source or changing the full acceptance
  plan.
- Added a typed acquisition failure that maps provider licence,
  authentication, access, and other failures to secret-safe reason codes and
  planned request context.
- Changed fetch failures from provider tracebacks to machine-readable JSON with
  the dataset, request ID, reason, and official dataset page.
- Preserved atomic cleanup: a provider denial removes any partial response and
  cannot create a verified artifact or receipt.
- Added tests for secret-safe licence failure handling, partial-file cleanup,
  dataset-scoped plan selection, and machine-readable CLI blockers.
- Updated the setup instructions and Night 2 data-access report with the
  observed authenticated results and exact next step.

Files changed:

- `README.md`
- `pipeline/src/thermal_drought/acquire/cli.py`
- `pipeline/src/thermal_drought/acquire/runner.py`
- `pipeline/tests/test_acquisition.py`
- `pipeline/reports/night-2-data-access.md`
- `progress.md`

Checks:

- Targeted acquisition suite after implementation: 20 passed.
- Full Python suite: 37 passed.
- Variable contracts: 2 manifests validated.
- Representative plan: 24 unique non-fixture requests across both official
  dataset IDs; fingerprint unchanged at
  `04989c737e477ab6aba89ee884014c03e3c87cfc8ca91ddbeb4c2e1f4839dee1`.
- Secret-safe status: `cdsapi` installed and non-empty `.cdsapirc` present;
  environment credential flags false; no secret values emitted.
- Dataset-scoped ERA5-HEAT access: exited 2 with
  `licence_not_accepted` for the exact planned request.
- Dataset-scoped ERA5-Drought access: exited 2 with
  `licence_not_accepted` for the exact planned request.
- Observed-metadata audit: exited 2 as required with 0 of 24 artifacts,
  `official_evidence: false`, no unexpected or duplicate receipts, and the
  expected plan fingerprint.
- Ruff: passed.
- Mypy strict mode: passed across 9 source files.
- Python dependency consistency (`pip check`): passed.
- TypeScript typecheck: passed.
- Vitest smoke test: 1 passed.
- Vite production build: passed.
- Local npm dependency tree: command passed; platform-inapplicable and
  undeclared feature dependencies were reported only as optional.
- Offline npm audit: 0 vulnerabilities reported.
- `git diff --check`: passed.
- Legacy `docs/` application and all 753 files: unchanged.
- No service, end-to-end, visual, or accessibility command exists yet at this
  Night 2 stage; none was skipped.

Decisions:

- Keep the full 24-request plan and its inspection fingerprint authoritative.
  Dataset scoping is only a retrieval/resume aid and cannot close the gate from
  a partial source.
- Report known provider denials with stable reason codes and official dataset
  context without echoing arbitrary provider response bodies.
- Do not advance to normalization while both official source licences remain
  unaccepted and no observed source metadata exists.

Blockers:

- The configured CDS account has not accepted the required licence for
  ERA5-HEAT.
- The same account has not accepted the required licence for ERA5-Drought.
- Therefore 0 of 24 official artifacts exist, and returned dimensions,
  variables, units, nodata, cell centers, quality values, sizes/latencies, and
  UTCI coverage-edge behavior remain unverified. No fixture supplies those
  facts.

Next:

- Remain on Night 2. Accept both licences through the two official CDS dataset
  pages, rerun the restartable fingerprinted fetch, and run the exact-plan
  observed-metadata audit. Close the gate only after all 24 official artifacts,
  source/quality pairs, and cell-center comparisons verify.

## 2026-07-27 — Night 2

Goal:

- Retest official access after both dataset licences were accepted, complete
  the exact 24-partition retrieval, and close the paired-grid evidence gate only
  if every official artifact verifies.

Completed:

- Confirmed the non-empty local CDS configuration without reading or emitting
  any credential value.
- Retrieved all 24 planned official response containers: eight UTCI daily
  statistics partitions, eight deterministic selected-year SPEI-3 partitions,
  and eight separate reference-period SPEI normality-quality partitions.
- Retained a checksum, byte size, duration, exact request, source metadata, and
  UTC retrieval time in every receipt.
- Discovered and documented that CDS returns ZIP containers even when the
  client target uses a `.nc` suffix.
- Added content-detected ZIP inspection with bounded member count and expanded
  size, safe paths, duplicate-name rejection, encryption rejection, NetCDF-only
  members, temporary extraction, and full header inspection.
- Made the archive audit verify identical member structures and spatial grids.
- Made UTCI inspection require exactly one daily member for every requested
  calendar date; January and July each contain all 31 planned days.
- Recorded that `utci_daily_max` and `SPEI3` omit unit attributes in the
  returned NetCDF headers, while the quality field is named `significance` with
  unit `1`.
- Ran the exact-plan audit successfully: 24 of 24 official artifacts, eight
  UTCI/SPEI pairs, and eight SPEI/quality pairs pass with no missing,
  unexpected, duplicate, fixture, checksum, provenance, or grid issue.
- Confirmed identical 0.25° cell centers without transformation in Phoenix,
  Paris, Fairbanks, and the -60° UTCI coverage-edge sample.
- Reran acquisition and verified all 24 existing artifacts locally without
  redownloading.
- Updated the human-readable data-access report and produced the complete
  machine-readable observed-metadata audit.

Files changed:

- `README.md`
- `pipeline/src/thermal_drought/acquire/inspection.py`
- `pipeline/tests/test_acquisition.py`
- `pipeline/reports/night-2-data-access.md`
- `pipeline/reports/night-2-observed-metadata.json`
- `progress.md`

Checks:

- Official retrieval: 24 downloaded response containers and 24 checksum-bound
  receipts; 9,662,880 response bytes total.
- Restart behavior: 24 of 24 reported `verified-existing`; no network retrieval
  was attempted for verified files.
- Exact-plan inspection: `complete: true`, `official_evidence: true`, 24
  artifacts, 8 source pairs, 8 quality pairs, and fingerprint
  `04989c737e477ab6aba89ee884014c03e3c87cfc8ca91ddbeb4c2e1f4839dee1`.
- Archive evidence: 264 safely inspected NetCDF members, including 248 daily
  UTCI files; no member was persisted outside its response container.
- Targeted acquisition suite: 22 passed.
- Full Python suite: 39 passed.
- Variable contracts: 2 manifests validated.
- Ruff: passed.
- Mypy strict mode: passed across 9 source files.
- Python dependency consistency (`pip check`): passed.
- TypeScript typecheck: passed.
- Vitest smoke test: 1 passed.
- Vite production build: passed.
- Local npm dependency tree: command passed; platform-inapplicable and
  undeclared feature dependencies were reported only as optional.
- Offline npm audit: 0 vulnerabilities reported.
- `git diff --check`: passed.
- Legacy `docs/` application and all 753 files: unchanged.
- No service, end-to-end, visual, or accessibility command exists yet at this
  Night 2 stage; none was skipped.

Decisions:

- Close Night 2 because the exact official plan, receipts, source/quality
  pairings, and cell centers now pass the implemented acceptance audit.
- Treat ZIP packaging as a provider response format discovered by content, not
  by a misleading target extension.
- Carry the catalogue's documented UTCI Kelvin and dimensionless SPEI contracts
  into explicit product-versioned Night 3 adapters; never silently accept
  arbitrary unitless source fields.
- Keep source climate arrays unread during this structural audit. Value-level
  unit validation, provider-quality application, daily-max monthly medians, and
  coverage-edge cell validity belong to Night 3.

Blockers:

- None for the Night 2 acceptance gate.
- The returned UTCI and SPEI NetCDF variables lack unit attributes. This is a
  documented Night 3 adapter requirement, not permission to infer or fabricate
  units or values.

Next:

- Begin Night 3 with archive-aware normalization. Select only
  `utci_daily_max`, validate its product-versioned Kelvin contract and sample
  values before converting to °C, calculate monthly medians of daily maxima,
  retain provider `SPEI3` without recomputing its accumulation window, apply the
  `significance` quality field, and verify nodata and -60° edge behavior from
  the official sample arrays.

## 2026-07-27 — Night 3

Goal:

- Turn the exact official acquisition proof into deterministic canonical
  monthly products while preserving the locked UTCI, SPEI-3, time, nodata, and
  provider-quality semantics.

Completed:

- Re-audited the exact 24-artifact, checksum-bound non-fixture plan before
  reading climate arrays.
- Added bounded ZIP-aware normalization that selects only ERA5-HEAT v1.1
  `utci_daily_max` with `cell_methods = "time: maximum"`.
- Added an explicit product/version/variable adapter for the observed missing
  UTCI unit attribute. It accepts the catalogue-bound Kelvin contract, rejects
  unexpected present units, validates plausible source values, converts to °C,
  requires every requested daily member exactly once, and computes the monthly
  median per cell.
- Added the ERA5-Drought v1.0 adapter for deterministic provider `SPEI3`.
  Selected-year monthly values are retained directly and the three-month
  accumulation window is never recomputed.
- Preserved the separate reference-period `significance` array, restricted it
  to provider values 0, 1, or nodata, retained unmasked source SPEI-3, and made
  the published SPEI-3 no data unless quality equals 1.
- Canonicalized coordinate names, EPSG:4326 metadata, Gregorian month-start
  time, north-to-south latitude, and ascending `[-180, 180)` longitude on the
  exact 0.25° cell centers without interpolation.
- Added atomic, semantically idempotent local publication. An existing
  identical dataset is left untouched, preserving its checksum.
- Produced four ignored two-month regional NetCDF products totaling 120,656
  bytes and a checked-in report with their SHA-256 checksums and eight official
  center-cell golden samples.
- Independently reproduced UTCI monthly medians with Python's reference median
  and directly read provider SPEI-3 and quality values at all eight golden
  cells.
- Verified the southern edge: UTCI remains valid at -59.75°, while provider
  SPEI-3 is nodata and quality is 0 in January and July; published drought
  remains no data rather than zero.
- Added the shared `ceil(selected_month_count × 0.75)` validity rule with
  minimum one, including one-month identity and real-zero preservation.
- Added a minimal `normalize` dependency extra and CI coverage for the
  normalization/scientific tests.
- Documented the reproduction command, adapters, canonical contract,
  independent precision evidence, local publication scope, and dependency
  blocker.

Files changed:

- `.github/workflows/checks.yml`
- `Makefile`
- `README.md`
- `pipeline/pyproject.toml`
- `pipeline/src/thermal_drought/acquire/inspection.py`
- `pipeline/src/thermal_drought/aggregation.py`
- `pipeline/src/thermal_drought/normalize/__init__.py`
- `pipeline/src/thermal_drought/normalize/__main__.py`
- `pipeline/src/thermal_drought/normalize/cli.py`
- `pipeline/src/thermal_drought/normalize/core.py`
- `pipeline/tests/test_aggregation.py`
- `pipeline/tests/test_normalization.py`
- `pipeline/reports/night-3-normalization.md`
- `pipeline/reports/night-3-normalization.json`
- `progress.md`

Checks:

- Targeted aggregation and normalization suite: 16 passed, including
  deterministic structural inputs explicitly labeled as non-climate data and
  the bounded official integration path.
- Full Python suite: 55 passed.
- Exact-plan source audit: `complete: true`, `official_evidence: true`, 24
  artifacts, eight UTCI/SPEI pairs, eight SPEI/quality pairs, and fingerprint
  `04989c737e477ab6aba89ee884014c03e3c87cfc8ca91ddbeb4c2e1f4839dee1`.
- Local publication: four 2 × 3 × 3 regional products; a second run retained
  identical output checksums.
- Variable contracts: two manifests validated.
- Ruff lint: passed.
- Ruff format: passed for all new Night 3 Python files. A separate repository-
  wide advisory check identified eight pre-existing unformatted files; they
  were not bulk-rewritten.
- Mypy strict mode: passed across 14 source files.
- Python dependency consistency (`pip check`): passed.
- TypeScript typecheck: passed.
- Vitest smoke test: one passed.
- Vite production build: passed.
- Local npm dependency tree: passed; only platform- or feature-specific
  optional dependencies were reported absent.
- Offline npm audit: zero vulnerabilities reported.
- `git diff --check`: passed.
- Legacy `docs/` application and all 753 files: unchanged.
- No service, end-to-end browser, visual, or accessibility command exists at
  this Night 3 stage; none was skipped.

Decisions:

- Treat absent source unit attributes as a narrow, product-versioned adapter
  case, never as permission to infer units from arbitrary input.
- Keep `spei_3_source`, `spei_3_quality`, and quality-masked `spei_3` separate
  so quality handling remains inspectable and missing data cannot become zero.
- Preserve the provider's common cell centers and use canonical coordinate
  ordering only; do not interpolate.
- Use compressed NetCDF for the bounded local development representation
  because it is supported by the installed reviewed stack. Keep chunked Zarr
  as the production target rather than weakening or mislabeling this sample.
- Close Night 3 because the representative normalization acceptance gate,
  independent value comparisons, idempotence, quality handling, and southern
  edge checks pass. This is not a claim of a global or complete-year backfill.

Blockers:

- `zarr>=2.18,<3` and `numcodecs>=0.15,<1` are declared but absent. The
  sandboxed install could not resolve the package index, and the required
  network escalation was rejected as an unreviewed third-party install. No
  workaround or external asset was used.
- Production Zarr layout, global backfill, overviews, quantization study, and
  object-storage publication remain pending. None blocks the bounded Night 3
  sample gate or local Night 4 service work.

Next:

- Night 4: implement the shared selected-month median/classification library,
  compatibility and two-variable bounds, deterministic versioned cache keys,
  and local availability, health, point-sample, and development raster
  endpoints backed by the canonical Night 3 products.

## 2026-07-28 — Night 4

Goal:

- Provide one scientifically consistent, bounded implementation for selected-
  month point values and development tiles, backed by the verified canonical
  Night 3 products.

Completed:

- Extended the variable contract with explicit ownership for exact
  classification breaks. UTCI now expresses `< 9`, `9–26`, and `> 26`
  precisely, while SPEI-3 expresses `≤ -1.5`, `(-1.5, -1.0]`, and `> -1.0`
  without variable-name branches in the classifier.
- Marked both registry entries as the bounded
  `night-3-official-sample-v1` publication for 2024 and added data-driven
  quality-field/pass-value metadata.
- Added selected-month aggregation by canonical mask, including a structured
  unavailable-month failure and the unchanged
  `ceil(selected months × 0.75)` validity rule.
- Exhaustively compared all 4,095 month masks to a simple independent median
  implementation, including one-month, odd, even, all-year, missing-value,
  ordering, real-zero, and unpublished-month cases.
- Added a registry-driven fixed classifier for scalar and array values. No data
  maps to class index `-1` internally and JSON `null` externally, never zero.
- Added variable-neutral selection and compatibility checks for grid,
  resolution, calendar, statistic, published year, months, and spatial
  coverage. One variable and two different compatible variables are accepted;
  duplicates and more than two are rejected.
- Added a release catalogue that verifies the Night 3 report, every product
  checksum, official/fixture provenance, required data and quality arrays,
  time/month metadata, grid, path containment below `data/published/`, unique
  region/year identity, product count, and development cell bounds before
  serving.
- Added local `health`, `availability`, point-sample, and versioned sparse JSON
  development-tile endpoints through a dependency-light WSGI application.
- Kept the sample scope explicit in every response. Availability reports only
  January and July 2024 across the four representative regions and correctly
  reports no complete year.
- Made point and tile cells use the identical aggregation, provider-quality,
  classification, and source-metadata path. The southern sample returns
  drought `null`, class `null`, zero valid months, and `low_quality`; UTCI
  remains valid.
- Added deterministic cache identities and HTTP ETags covering API, software,
  data/release, ordered variables, year, month mask, statistic,
  minimum-valid fraction, quality rule, classification
  versions/breaks/edge assignments, palette version, response kind, and
  spatial/tile identity.
- Bounded masks, years, latitudes, longitudes, dataset versions, zooms, tile
  coordinates, release paths, file counts, and per-product development cells.
  Tests prove invalid requests fail before a climate data reader is called.
- Added deterministic structural service fixtures that are labeled
  `fixture: true` and `official_evidence: false`. The normal service startup
  rejects them; tests must opt in programmatically.
- Documented local installation, validation, startup, endpoint shapes, mask
  semantics, immutable cache behavior, sample limits, and production gaps.

Files changed:

- `README.md`
- `Makefile`
- `config/app.json`
- `config/manifest.schema.json`
- `config/variables/spei_3.json`
- `config/variables/utci_daymax_median.json`
- `pipeline/pyproject.toml`
- `pipeline/src/thermal_drought/__init__.py`
- `pipeline/src/thermal_drought/aggregation.py`
- `pipeline/src/thermal_drought/classification.py`
- `pipeline/src/thermal_drought/contracts.py`
- `pipeline/src/thermal_drought/normalize/core.py`
- `pipeline/src/thermal_drought/api/__init__.py`
- `pipeline/src/thermal_drought/api/__main__.py`
- `pipeline/src/thermal_drought/api/app.py`
- `pipeline/src/thermal_drought/api/cli.py`
- `pipeline/src/thermal_drought/api/core.py`
- `pipeline/tests/test_aggregation.py`
- `pipeline/tests/test_classification.py`
- `pipeline/tests/test_contracts.py`
- `pipeline/tests/test_service.py`
- `services/README.md`
- `progress.md`

Checks:

- Focused service/scientific gate: 33 passed.
- Full Python suite: 78 passed.
- All 4,095 non-empty month masks matched the independent selected-month
  reference median.
- Night 3 normalization replay: 23 aggregation/normalization tests passed; the
  exact official source audit and four idempotent canonical outputs completed.
- Local service catalogue: four checksum-verified products, 36 cells, official
  evidence true, fixture false, two published months, no falsely complete year.
- Live loopback WSGI smoke: health, Phoenix point sample, and zoom-zero
  development tile each returned HTTP 200.
- Live Phoenix January/July point: SPEI-3 `-0.5169488192`, UTCI
  `31.8961267471 °C`, two valid months each, provider quality passed, classes
  `No drought` and `Heat stress`.
- Live development tile: 36 cells, 43,492 bytes, immutable cache header and
  deterministic ETag. Its Phoenix center values and classes match the point
  response exactly.
- Variable contracts: two manifests validated.
- Ruff lint: passed.
- Ruff format: all 11 Night 4 Python files checked are formatted.
- Strict mypy: passed across 20 source files.
- Python dependency consistency: no broken requirements.
- TypeScript typecheck: passed.
- Vitest smoke: one passed.
- Vite production build: passed; application bundle remains 1.11 kB before
  gzip and 0.62 kB after gzip at this foundation stage.
- Local npm dependency tree: passed.
- Offline npm audit: zero vulnerabilities reported.
- `git diff --check`: passed.
- Legacy `docs/` application and all 753 files: unchanged.
- No browser end-to-end, automated accessibility, or visual-regression command
  exists yet; those remain Night 5–7 work rather than skipped checks.

Decisions:

- Encode exact-break ownership in the versioned registry because UTCI and
  SPEI-3 have different inclusive boundaries that cannot be recovered safely
  from breaks alone.
- Reuse quality-masked canonical `spei_3` values and the separate provider
  quality array. Never aggregate `spei_3_source` into a published drought value
  or infer January from the selected UI months.
- Use the standard-library WSGI server for this local slice so no unreviewed
  dependency is required. Keep the core framework-neutral for a later
  production host.
- Return sparse JSON grid cells as the bounded development tile format. Do not
  describe it as a production WebP raster, CDN cache, or global layer.
- Version the sample in the public manifests but let availability describe its
  actual two-month extent; never imply that the registry's provider coverage
  is published data availability.

Blockers:

- Production Zarr and numcodecs dependencies remain unavailable in the current
  sandbox. The bounded official sample remains compressed NetCDF.
- No global or complete-year canonical backfill exists. The service cannot
  truthfully offer the latest complete year or arbitrary months beyond January
  and July 2024.
- Production raster/WebP rendering, spatial chunk reads, object storage/CDN,
  cache warming, rate limiting, observability, and deployment remain pending.
- The `development-1` palette identifier participates in cache identity, but
  palette design, bivariate rendering, comprehension testing, and
  color-vision/accessibility review belong to Nights 5–7.

Next:

- Night 5: build the global TypeScript map shell against availability and the
  development data path; render variable slots from the registry; support
  univariate/bivariate selection and axis swap; add the accessible circular
  month selector with final-month protection and textual fallback; serialize
  variables, year, mask, location, and zoom to the URL; and preserve the last
  valid map while replacement data loads.

## 2026-07-28 — Night 4 storage-hardening follow-up

Goal:

- Turn the daily-source/monthly-serving design and local disk-safety plan into
  enforced, reviewable safeguards before the next nightly objective.

Completed:

- Added a versioned storage policy with a 20 GiB free-space reserve, 80% volume
  high-water mark, three-times processing-peak estimate, and one-year local
  backfill limit.
- Added managed quotas: 3 GiB raw, 5 GiB canonical, 5 GiB published, 2 GiB
  composite cache, and 2 GiB generated tiles.
- Locked the hybrid temporal contract: provider daily maximum UTCI is reduced
  to monthly medians; provider SPEI-3 stays monthly; daily arrays are forbidden
  in serving storage and are archived externally after checksum and product
  validation.
- Added disk-independent policy validation, managed-directory inventory, and
  conservative annual backfill preflight commands with structured JSON output.
- Made new acquisition writes reserve space before the provider is called,
  retain restartability for verified files, cap every response partition at
  512 MiB, reserve 64 KiB for its receipt, remove oversized partials, and
  record the applied policy in receipts.
- Made ZIP inspection and normalization reserve exact expanded bytes before
  temporary extraction. Inspection preflights the exact serialized receipt
  updates before any sidecar write. Full normalization also reserves 1 GiB
  working space plus 512 MiB output space before inspection can update receipts.
- Made normalization reports and published NetCDF metadata state the source and
  published temporal frequencies and daily-source retention rule.
- Bounded cache prewarming to exactly 17 masks: 12 single months, DJF, MAM,
  JJA, SON, and all months. Arbitrary masks remain on demand.
- Kept automatic deletion disabled. Multi-year backfill is rejected until
  reviewed object storage, versioning, and lifecycle rules exist.
- Replaced host-dependent disk preflights in CI with policy-only validation;
  local `make storage-check` still performs real inventory and a one-year
  capacity preflight.

Files changed:

- `.github/workflows/checks.yml`
- `Makefile`
- `README.md`
- `PROJECT_PLAN.md`
- `config/storage-policy.json`
- `pipeline/pyproject.toml`
- `pipeline/src/thermal_drought/storage.py`
- `pipeline/src/thermal_drought/acquire/cli.py`
- `pipeline/src/thermal_drought/acquire/inspection.py`
- `pipeline/src/thermal_drought/acquire/runner.py`
- `pipeline/src/thermal_drought/normalize/cli.py`
- `pipeline/src/thermal_drought/normalize/core.py`
- `pipeline/tests/test_acquisition.py`
- `pipeline/tests/test_normalization.py`
- `pipeline/tests/test_storage.py`
- `services/README.md`
- `progress.md`

Checks:

- Targeted storage, acquisition, and normalization suite: 39 passed.
- Full Python suite: 90 passed.
- Acquisition gate: 25 passed; the secret-safe credential probe found the
  installed client and a non-empty local credential without printing values.
- Normalization replay: 24 passed; four official bounded products and their
  deterministic report were regenerated.
- Service gate: 33 passed; variable contracts and the four-product official
  catalogue validated.
- Ruff lint: passed across pipeline source and tests.
- Ruff format: all 29 Python source and test files are formatted.
- Strict mypy: passed across all pipeline source modules.
- Storage policy validation: approved.
- Local storage inventory: approved at 9.44 MiB raw, 121.83 KiB published,
  85.42 GiB free, and 62.58% volume use.
- One-year local preflight: approved at a conservative 7.51 GiB processing
  peak, leaving an estimated 77.91 GiB free and 65.87% volume use.
- Two-year local preflight: rejected before work with
  `backfill_year_limit` and `managed_quota_exceeded`.
- TypeScript typecheck and Vitest smoke: passed.
- Vite production build: passed at 1.11 kB JavaScript before gzip.
- Python dependency consistency and local npm dependency tree: passed.
- Offline npm audit: zero vulnerabilities.
- `git diff --check`: passed.

Decisions:

- Preserve daily UTCI only where its temporal resolution contributes to the
  monthly statistic and validation. Do not publish or tile daily layers for
  this product.
- Treat annual byte figures as conservative planning estimates, never as
  measured provider compression or climate observations.
- Fail before guarded writes and emit reason codes instead of attempting
  cleanup under pressure. Leave all deletion and external archival decisions
  to reviewed operator workflows.
- Do not run real disk-capacity checks on ephemeral CI hosts; validate the
  policy deterministically there and exercise preflights with injected disk
  states in tests.

Blockers:

- No reviewed object-storage target or lifecycle policy exists, so multi-year
  backfill remains intentionally blocked.
- Production Zarr and numcodecs remain unavailable; the bounded official sample
  stays in compressed NetCDF.
- Cache and tile writers are not implemented yet. Their quotas and allowlist
  are now defined before those write paths exist.

Next:

- Night 5 remains the earliest incomplete night: build the global TypeScript
  map shell and accessible circular month interaction against the bounded
  Night 4 service, without widening the published-data claim.

## 2026-07-30 — Night 5

Goal:

- Deliver the manifest-driven global frontend shell, one/two-variable
  interaction, accessible non-empty month selection, URL state, and
  last-valid-map behavior against the bounded Night 4 data path.

Completed:

- Replaced the foundation placeholder with a responsive, map-dominant
  TypeScript application and a collapsible narrow-screen control sheet.
- Added a global MapLibre navigation surface with a code-native globe
  reference, graticule, ERA5-HEAT southern-limit treatment, and sparse
  official-sample cell markers. No external basemap or unreviewed asset is
  requested.
- Imported the checked-in public application and variable manifests at build
  time. Labels, units, default axes, publication versions, classifications,
  service version, and the two-variable maximum now drive the controls.
- Intersected the registry with live service availability. The current
  official sample enables only January and July 2024, labels the year partial,
  says `All available` rather than `All year`, and never widens the sample into
  a global-data claim.
- Added one-variable univariate and two-variable bivariate modes, duplicate
  prevention, data-driven incompatibility disabling, and axis swap.
- Added the twelve-wedge month ring as native buttons in January-to-December
  DOM order, with `aria-pressed`, full month accessible names, visible focus,
  disabled-unavailable styling, pointer/keyboard activation, final-month
  protection with an assertive announcement, and a direct all-available action.
- Added a synchronized native-checkbox fallback that uses the identical
  non-empty selection path.
- Added canonical URL state for X/Y variables, year, three-digit hexadecimal
  month mask, longitude, latitude, and zoom. Invalid values fall back safely
  with one non-blocking message; reload and Back/Forward restore controls,
  title, period, map view, and data request orientation.
- Added an abortable development-tile loader. A pending or failed replacement
  leaves the last successfully rendered map intact and labels its stale state;
  retry uses the current state.
- Added a Vite-only `/api` loopback proxy so the local official service can be
  exercised without adding permissive CORS or embedding a production endpoint.
- Split MapLibre into a separate vendor chunk so the application JavaScript
  remains measurable against the plan's map-library-excluded budget.
- Added exhaustive month-mask tests, disjoint January/April/September state,
  final-month protection, URL round trips and fallbacks, univariate URL state,
  manifest/cap checks, request-path orientation, and last-valid-map failure
  retention.
- Used a real Chromium browser to find and fix an unbound browser fetch, a
  center button that intercepted circular-wedge pointer clicks, a
  style-before-load projection failure, and unnamed focusable development
  markers.

Files changed:

- `.gitignore`
- `README.md`
- `config/app.json`
- `web/index.html`
- `web/tsconfig.json`
- `web/vite.config.ts`
- `web/src/app.ts`
- `web/src/data.ts`
- `web/src/data.test.ts`
- `web/src/main.ts`
- `web/src/map.ts`
- `web/src/months.ts`
- `web/src/months.test.ts`
- `web/src/registry.ts`
- `web/src/registry.test.ts`
- `web/src/state.ts`
- `web/src/state.test.ts`
- `web/src/style.css`
- `web/src/types.ts`
- `web/src/smoke.test.ts` (removed)
- `progress.md`

Checks:

- Full Python suite: 90 passed.
- Acquisition gate: 26 passed; the secret-safe probe found the installed
  client and non-empty local credential without printing values.
- Normalization/aggregation gate: 24 passed; the exact official audit and four
  bounded canonical products replayed.
- Service gate: 33 passed; both manifests and the four-product
  official-evidence catalogue validate.
- Storage gate: seven tests, policy validation, live inventory, and one-year
  preflight passed at 85.23 GiB free and a projected 7.51 GiB peak.
- Frontend typecheck and four Vitest files: 11 passed. The tests enumerate all
  4,095 masks and explicitly cover January + April + September.
- Production build passed. The application JavaScript is 25.40 kB / 9.04 kB
  gzip, separate from the MapLibre vendor chunk at 1,053.03 kB / 283.19 kB
  gzip. Application CSS is 7.56 kB / 2.61 kB gzip.
- Real Chromium smoke against the live bounded official service passed:
  availability/load, January/July pointer selection, Space-key final-month
  protection, all-available action, axis swap, univariate mode, Back, reload,
  and 390 × 844 / 1280 × 800 responsive layouts.
- Browser accessibility-tree review confirmed native labeled selects/buttons,
  January-to-December order, pressed/disabled state, named map controls, no
  unnamed marker controls, and the live final-month announcement.
- Browser console: zero application errors. Chromium emitted only MapLibre
  WebGL read-buffer performance warnings during repeated screenshots.
- Ruff lint and format check passed across 29 Python files.
- Strict mypy passed across 21 Python source files.
- Python dependency consistency, local npm dependency tree, offline npm audit
  with zero vulnerabilities, and `git diff --check` passed.
- Browser QA screenshots were written below ignored `output/playwright/`;
  neither they nor the generated `web/dist/` build are checked in.
- No automated axe, screen-reader, color-vision, Firefox, WebKit, or
  visual-regression command is installed. Those remaining Night 6–7 gates were
  not represented as passing.

Decisions:

- Treat live availability as authoritative. Generic month logic supports every
  non-empty mask, but unavailable official-sample months remain disabled rather
  than provoking known service failures or implying observations exist.
- Use `y=-` as the explicit univariate URL state and preserve ordered X/Y axes
  in service paths so swaps change rendering and cache identity consistently.
- Update visible control state immediately, abort stale network work, and
  replace the rendered sample only after a valid response. Never blank a good
  map during an update.
- Keep the local proxy development-only. Production service origin, CORS,
  raster delivery, basemap, and deployment remain reviewed operations choices.
- Keep the current colors explicitly developmental. The fixed 3 × 3 legend,
  palette review, text alternatives, and point-linked interpretation belong to
  Night 6 rather than being implied by sparse sample markers.

Blockers:

- Only January and July 2024 are present in the verified four-region sample.
  The live UI therefore cannot demonstrate January + April + September with
  observations or offer a latest complete year; the generic tested control
  path is ready when those months are actually published.
- Production Zarr, global/full-year monthly products, raster/WebP tiles,
  object storage/CDN, a reviewed basemap, and deployment remain unavailable.
- The Night 6 legend, point readout, sources/methodology/limitations panels,
  complete empty/error/stale explanations, artificial third-variable proof,
  automated accessibility runner, and manual screen-reader audit remain.

Next:

- Night 6: add the fixed 3 × 3 and univariate legends, text-identifiable
  bivariate states, point inspection tied to legend cells, source/methodology
  and limitations panels, complete loading/stale/error/no-data states, the
  artificial compatible variable fixture, and automated accessibility plus
  manual keyboard/screen-reader review.

## 2026-08-03 — Night 6

Goal:

- Make the bounded map interpretable, inspectable, registry-extensible, and
  resilient without widening its data claim or weakening the locked temporal,
  quality, and missing-data semantics.

Completed:

- Added a manifest-driven univariate scale and fixed 3 × 3 bivariate matrix
  backed by the same palette and raw class indices as the map. Exact threshold
  ownership, axis display order, units, and labels come from configuration.
- Added full paired text labels for all nine bivariate states, focus/pointer
  emphasis of matching sample cells, selected-cell linkage, and a separate
  crosshatched no-data key that states missing or failed-quality values are
  never zero.
- Added click, tap, map-center button, Enter, and Space point inspection through
  the shared `/v1/sample` path. The readout includes grid coordinates, selected
  year/period, values, units, classes, valid/required month counts, provider
  quality, source/product version, sample retrieval date, and the grid-cell and
  personal-exposure limitation.
- Added an abortable point loader. State changes mark the last readout stale,
  errors retain it with explicit copy, and map/readout retry actions recover
  independently. Empty availability, outside-sample no-data, partial data,
  provider-quality failure, loading, ready, stale, and service-error states are
  distinct and never fabricate zero.
- Added source, methodology, temporal-semantics, and limitations panels driven
  by selected manifests. SPEI-3's provider three-month ending-month semantics
  and UTCI's daily-maximum-to-monthly-median order are configuration data, not
  variable-name branches.
- Added checksum-evidence-derived sample retrieval timestamps to both
  manifests, schema validation, service availability, point/tile source
  metadata, and readouts.
- Added a conspicuously labeled artificial interface variable in deterministic
  tests only. Frontend registry and legend tests and a temporary backend
  structural product prove that a third compatible variable uses unchanged
  compatibility, median, classification, URL, legend, and sampling paths while
  remaining `fixture: true` and `official_evidence: false`.
- Added deterministic accessibility coverage for legend text contrast. A real
  browser audit found no duplicate IDs, unnamed buttons/selects, focusable
  content hidden from accessibility APIs, or unlabeled legend/source entries.
- Real Chromium QA found and fixed two invalid composite MapLibre expressions
  before the final clean-console run. Keyboard review confirmed map inspection
  by Space and sequential focus across all labeled legend cells.

Files changed:

- `README.md`
- `config/manifest.schema.json`
- `config/variables/spei_3.json`
- `config/variables/utci_daymax_median.json`
- `pipeline/src/thermal_drought/api/core.py`
- `pipeline/tests/test_service.py`
- `web/src/app.ts`
- `web/src/data.ts`
- `web/src/data.test.ts`
- `web/src/inspection.ts`
- `web/src/inspection.test.ts`
- `web/src/legend.ts`
- `web/src/legend.test.ts`
- `web/src/map.ts`
- `web/src/registry.ts`
- `web/src/style.css`
- `web/src/test-fixtures.ts`
- `web/src/types.ts`
- `progress.md`

Checks:

- Full Python suite: 91 passed.
- Acquisition gate: 26 passed; the secret-safe probe found the installed CDS
  client and non-empty local credential without printing values.
- Normalization/aggregation gate: 24 passed; the exact bounded official sample
  replay and four canonical products completed.
- Service gate: 34 passed; both manifests, official-evidence catalogue, point,
  tile, retrieval metadata, and artificial third-variable path validate.
- Storage gate: seven tests, policy validation, inventory, and one-year
  preflight passed at 86.70 GiB free and a projected 7.51 GiB peak.
- Frontend strict TypeScript and six Vitest files: 18 passed, including all nine
  legend states, exact threshold ownership, swaps, univariate mode, point
  no-data/quality/stale behavior, artificial-variable integration, and WCAG AA
  text contrast for every development legend color.
- Production build passed. Application JavaScript is 41.25 kB / 13.53 kB gzip,
  separate from MapLibre at 1,053.03 kB / 283.19 kB gzip. Application CSS is
  11.42 kB / 3.46 kB gzip.
- Real Chromium passed Phoenix bivariate values, selected-legend linkage,
  southern-limit provider-quality no-data, axis swap, univariate mode, map
  Space-key inspection, offline stale/error/retry recovery, and 390 × 844 plus
  1280 × 800 layouts. The final non-failure session had zero application
  console errors; repeated WebGL readback emitted performance warnings only.
- Automated browser semantics audit: zero duplicate IDs, unnamed buttons,
  unnamed selects, or focusable descendants of `aria-hidden`; one H1, two live
  status regions, nine labeled bivariate buttons, and two HTTPS source links.
- Ruff lint and format passed across 29 Python files; strict mypy passed across
  21 source files; Python dependency consistency, local npm tree, offline npm
  audit with zero vulnerabilities, and `git diff --check` passed.
- Browser screenshots are below ignored `output/playwright/`; the generated
  `web/dist/` build remains ignored. Legacy `docs/` and its 753 files are
  unchanged.

Decisions:

- Keep class indices in raw manifest order for service/map identity and derive
  only visual X/Y ordering from `axis_display_order`. Swapping axes changes the
  request, map color composition, legend, and readout together.
- Use the official acquisition receipt timestamps as bounded-sample retrieval
  dates. Do not present them as provider reference-period dates or as global
  refresh evidence.
- Keep point state separate from map-tile state so either can fail or retry
  without erasing the other's last valid interpretation.
- Keep the artificial variable test-only, conspicuously non-climate, and out of
  the production manifest directory and live availability response.
- Keep the current palette labeled developmental. Passing text contrast is not
  a color-vision or comprehension study.

Blockers:

- Only January and July 2024 in Phoenix, Paris, Fairbanks, and the southern
  coverage edge are published. The UI cannot truthfully offer all-year/global
  observations, and the Night 7 tropical, coastal, and mountain exercises need
  clearly labeled structural fixtures or additional official acquisition.
- Production Zarr, global/full-year backfill, raster/WebP tiles, basemap,
  object storage/CDN, monitoring, deployment, refresh, and rollback rehearsal
  remain unavailable.
- Axe, a live screen reader, color-vision simulation, Firefox, and WebKit are
  not installed. The durable contrast tests, Chromium accessibility tree, and
  keyboard review pass, but those broader Night 7 validation tools are not
  represented as completed.
- Independent climate-science review and palette-comprehension testing require
  external reviewers and remain explicit production-readiness gaps.

Next:

- Night 7: run the complete hardening suite; exercise the required official and
  clearly labeled structural location cases; measure browser, service, and
  bundle budgets; add a recoverable preview alongside rather than over the
  legacy app; document setup, refresh, preview, rollback, and the final gap
  report; then close only the beta gates that have trustworthy evidence.

## 2026-08-04 — Completion foundation and schedule continuation

Goal:

- Replace the expired seven-night calendar as the terminal plan with an
  evidence-gated route from the working Night 1–6 vertical slice to complete
  global data, production serving, preview, validation, cutover, and operations.

Completed:

- Added `COMPLETION_FOUNDATION.md` as the active execution plan without changing
  the locked product or scientific requirements in `PROJECT_PLAN.md`.
- Defined the complete-product gate, immediate source-control checkpoint,
  source/artifact boundary, immutable data-release structure, one-month
  processing unit, recent-year-first backfill order, and post-cutover Git-history
  decision.
- Recorded the measured 112 MiB legacy site, 187 MiB Git pack, ignored 9.7 MiB
  official bounded sample, and regenerable local dependency footprint.
- Turned the storage-policy estimates into a large-file strategy: bounded
  monthly acquisition and reduction, remote raw/canonical/published layers, at
  least 25 percent capacity headroom, and no climate products in Git or Git LFS.
- Added a required production-format benchmark for Zarr/COG layouts,
  quantization tolerance, remote read behavior, and lossless categorical tile
  encoding before full-year acquisition.
- Limited proactive cache warming to 17 approved masks, the default pair, the
  latest three complete years, and zooms 0–4; arbitrary masks and higher zooms
  remain bounded on-demand work.
- Defined milestones M0–M9 with exit gates. M0–M8 complete the initial product;
  M9 handles reverse-chronological history and legacy cleanup only after a
  monitored cutover.
- Updated `README.md`, `PROJECT_PLAN.md`, and `SEVEN_DAY_PLAN.md` to route
  execution through the completion foundation.
- Updated the active 2:00 AM automation to continue from the earliest incomplete
  completion milestone rather than stop after the original seven-night window.

Files changed:

- `COMPLETION_FOUNDATION.md`
- `PROJECT_PLAN.md`
- `SEVEN_DAY_PLAN.md`
- `README.md`
- `progress.md`
- Codex automation `seven-night-global-thermal-drought-build-2-00-am`

Checks:

- `make foundation-check` passed: 91 Python tests, two variable manifests, strict
  TypeScript, and 18 frontend tests.
- `git diff --check` passed; the new completion document has no trailing
  whitespace.
- Documentation links and plan terminology checked locally.
- Repository source, data, dependency, and Git-pack measurements reconciled with
  the completion plan.
- No application behavior, climate data, legacy asset, credential, Git history,
  commit, push, publication, or deployment changed.

Decisions:

- Keep the scientific/product plan authoritative and make the completion
  foundation authoritative for execution order and operational architecture.
- Require two complete recent years for initial completion, then backfill
  history independently toward 1991.
- Use a canonical scientific array plus measured published spatial format,
  rather than assuming one representation is optimal for both processing and
  tile-serving workloads.
- Keep nightly work autonomous for safe local implementation and validation,
  while retaining explicit approval gates for commits, pushes, purchases,
  external resources, deployment, DNS/CORS changes, external contact, legacy
  deletion, and history rewriting.

Blockers:

- The current Night 1–6 work remains uncommitted; the automation may prepare a
  checkpoint but cannot commit or tag without explicit authorization.
- Production object storage, runtime, basemap, external climate review, palette
  study, and deployment authority remain undecided or external.

Next:

- M0/Night 7: prepare the reviewable checkpoint inventory, add the missing
  browser/accessibility/performance hardening that can run locally, create a
  recoverable preview build without replacing the legacy site, and publish an
  evidence-based beta gap report.

## 2026-08-05 — M0 baseline safety

Goal:

- Close every independent M0 baseline-safety action with a reproducible
  source/artifact/secret audit and a complete supported check report, while
  leaving the authorization-controlled legacy tag untouched.

Completed:

- Re-read the automation memory and all five required repository documents in
  full; inspected Git state, all user changes, package scripts, source/test
  inventory, ignored artifacts, legacy files, local dependencies, and current
  milestone gates before editing.
- Confirmed that `main` and `origin/main` now both point to checkpoint
  `30596c27616f62e1cd56598e8970225ecc1a8118`, which contains the Night 1–6
  source, tests, manifests, evidence, and unchanged legacy app. The prior
  legacy-only commit is `3d5b600839669cb81d953394359a046378eb7e5c`.
- Added a deterministic repository audit over Git-tracked files and non-ignored
  untracked commit candidates. It never opens ignored credentials or climate
  data, reports path/line/type without secret values, checks high-confidence
  private-key and service-token patterns, and exits nonzero on a violation.
- Made the audit verify 16 representative ignore paths for credentials, raw,
  canonical, published, tile, cache, runtime, dependency, build, coverage, and
  browser artifacts. Expanded the browser-output ignore from one subdirectory
  to the complete `output/` boundary.
- Pinned the raster exception to the 744 already tracked legacy files below
  `docs/data/crops/`. Any new TIFF or WebP, including one placed in that legacy
  tree, now fails the audit.
- Added four behavioral tests, a Makefile command, a Python entry point, and CI
  enforcement. Documented the command and its no-value-echo behavior.
- Added `pipeline/reports/m0-baseline-safety.md` with the recoverable source
  state, logical review groups, exact audit and check evidence, local budgets,
  remaining controlled action, and M0 disposition.
- Used the Playwright workflow against the live bounded official service.
  Phoenix inspection reproduced SPEI-3 `-0.5169` / `No drought` and UTCI
  `31.8961 °C` / `Heat stress`, with two of two valid months and provider
  drought quality passing. Desktop and phone views remained readable.
- Updated the status summary. The independent M0 engineering gate is complete;
  the legacy tag remains visible as an authorization blocker while Night 7 / M1
  becomes the next independent work.

Files changed:

- `.github/workflows/checks.yml`
- `.gitignore`
- `COMPLETION_FOUNDATION.md`
- `Makefile`
- `README.md`
- `pipeline/pyproject.toml`
- `pipeline/reports/m0-baseline-safety.md`
- `pipeline/src/thermal_drought/repository_audit.py`
- `pipeline/tests/test_repository_audit.py`
- `progress.md`

Checks:

- `make foundation-check`: 95 Python tests, both manifests, strict TypeScript,
  and 18 frontend tests passed.
- Acquisition gate: 26 tests passed; the status probe confirmed the installed
  client and a non-empty local credential without reading or printing it.
- Normalization/aggregation gate: 24 tests and the exact bounded official
  sample replay passed.
- Service gate: 34 tests, both manifests, the four-product official catalogue,
  and live service self-check passed.
- Storage gate: seven tests, policy validation, inventory, and one-year
  preflight passed with 82.23 GiB free, 63.9783% volume use, and a conservative
  7.51 GiB processing peak. The projected post-operation use is 67.27%.
- Repository audit: approved 830 source candidates, comprising 826 tracked and
  four non-ignored untracked files; scanned 86 text files; skipped 744 known
  legacy binary rasters; verified all 16 ignore probes; found zero candidate
  path violations and zero high-confidence secret findings.
- Ruff lint and format passed across 31 Python files; strict mypy passed across
  22 source modules; Python dependency consistency passed.
- Vite build passed: application JavaScript 41.25 kB / 13.53 kB gzip,
  MapLibre JavaScript 1,053.03 kB / 283.19 kB gzip separately, application CSS
  11.42 kB / 3.46 kB gzip, and MapLibre CSS 69.92 kB / 10.10 kB gzip.
- Local npm tree passed; offline npm audit reported zero vulnerabilities;
  `git diff --check` passed before the final documentation append and again in
  the final tree audit.
- Live service measurements: health 277 bytes / 0.530 ms; three Phoenix samples
  1,731 bytes / 9.607–11.564 ms; three zoom-zero development tiles 47,858 bytes
  / 35.636–36.323 ms.
- Chromium local navigation load event: 69.8 ms. Browser semantics found zero
  duplicate IDs, unnamed buttons, unnamed selects, or focusable descendants of
  `aria-hidden`; one H1 and three live regions were present. Console review
  found zero errors and four MapLibre/WebGL readback performance warnings.
- Visual inspection at 1280 × 800 and 390 × 844 passed for the bounded-data
  label, map, controls, and point readout. Generated screenshots and browser
  session files remain ignored below `output/`.

Measurements:

- Legacy boundary: 248 TIFFs plus 496 WebPs, 112,292,952 bytes, all already
  tracked and preserved.
- Candidate source boundary: 116,348,088 bytes; 4,055,136 text bytes scanned.
- The 47,858-byte response is development sparse JSON and is below the 200 kB
  size target, but it is not production raster-tile evidence.
- Browser and service timings are localhost development measurements, not
  production p95 claims. Production cached/uncached, CLS, INP, load, and remote
  latency targets remain unmet.

Decisions:

- Treat `30596c2` as the current source checkpoint and the legacy-only parent
  `3d5b600` as the proposed recoverable legacy-tag target. Do not rewrite the
  large existing checkpoint merely to recreate the foundation's logical commit
  groups.
- Enforce the artifact boundary against both tracked and commit-candidate files
  so an untracked secret or climate raster cannot disappear from the local M0
  report merely because it has not been staged.
- Keep the audit no-value-echo and high-confidence. It complements ignored-path
  enforcement without claiming a dedicated external secret-scanning product is
  installed.
- Preserve every locked science and service/frontend contract. No climate
  value, quality rule, month mask, legacy asset, service route, or UI behavior
  changed in this M0 slice.

Blockers:

- Creating the recoverable legacy tag is prohibited without explicit
  authorization; no tag was created. This is the only remaining M0 controlled
  action.
- Firefox, WebKit, axe, live screen-reader, color-vision, palette-comprehension,
  and external climate/licensing review tools or reviewers remain unavailable.
- Only January and July 2024 across four official regions exist. No global or
  complete-year data, production Zarr/COG benchmark, lossless raster service,
  object storage, deployment, monitoring, refresh, or rollback rehearsal exists.

Next:

- Begin Night 7 / M1 independently: exercise the required official and clearly
  labeled structural location cases, add durable browser/accessibility and
  performance evidence where local tools permit, produce a recoverable preview
  alongside the untouched legacy app, and finish the beta gap/refresh/rollback
  handoff without implying global or production readiness.

## 2026-08-06 — Night 7 / M1 recoverable beta preview

Goal:

- Create and validate a recoverable local beta route beside the untouched
  legacy application, add durable preview preflight and routing coverage, and
  measure the bounded replacement in a real browser without implying global or
  production readiness.

Completed:

- Re-read the automation memory and all five required repository documents in
  full; inspected Git/user changes, package scripts, source/test inventory,
  ignored artifacts, legacy files, local dependencies, and milestone gates.
- Kept M0's recoverable legacy tag visible as an explicit-authorization action
  and resumed the earliest independent milestone, Night 7 / M1.
- Added a dependency-light local beta router that serves the generated
  replacement from `/preview/`, the existing `docs/` tree in place from
  `/legacy/`, and the bounded data service from the same origin at `/api/v1/`.
- Added a deterministic preview inspector over every generated file. It records
  bytes, deterministic gzip bytes, and SHA-256, separates MapLibre from the
  application budget, rejects source maps and symbolic links, and fails when
  checked frontend budgets are exceeded.
- Restricted generated manifest writes to ignored `output/`; the checked
  command produces `output/m1-beta-preview/manifest.json` and leaves
  `web/dist/`, browser output, climate products, and caches outside Git.
- Added path-contained static routing with no directory listing, `GET`/`HEAD`
  bounds, traversal and unsafe-method rejection, `no-store` HTML/legacy
  responses, immutable fingerprinted preview assets, and clean Ctrl-C shutdown.
- Added five preview tests covering inventory/budget separation, preview and
  legacy routes, same-origin API forwarding, cache headers, `HEAD`, traversal,
  methods, source maps, and symbolic links. Added `make beta-preview-check` and
  a Python entry point.
- Documented build, serve, local refresh, and rollback commands in the README
  and service notes. Added `pipeline/reports/m1-beta-handoff.md` with measured
  browser/bundle evidence and an explicit beta/production gap report.
- Used the Playwright CLI workflow against the combined preview route. Exercised
  the official Phoenix hot/arid, Paris temperate, Fairbanks cold, and southern
  provider-quality cases, plus phone, tablet, laptop, and wide layouts.
- Verified Phoenix SPEI-3 `-0.5169` / `No drought` and UTCI `31.8961 °C` /
  `Heat stress`; the southern case kept drought as no data after provider
  quality failed while preserving UTCI `-14.1558 °C` / `Cold stress`.

Files changed:

- `Makefile`
- `README.md`
- `pipeline/pyproject.toml`
- `pipeline/reports/m1-beta-handoff.md`
- `pipeline/src/thermal_drought/preview.py`
- `pipeline/tests/test_preview.py`
- `services/README.md`
- `progress.md`

Checks:

- `make foundation-check`: 100 Python tests, both manifests, strict TypeScript,
  and 18 Vitest tests passed.
- Acquisition gate: 26 tests passed; the secret-safe status probe confirmed the
  installed CDS client and non-empty local credential without printing values.
- Normalization/aggregation gate: 24 tests and the exact bounded official
  replay passed.
- Service gate: 34 tests, both manifests, the four-product official catalogue,
  and service self-check passed.
- Storage gate: seven tests, policy validation, inventory, and one-year
  preflight passed at 82.00 GiB free and 64.0792% volume use; the conservative
  7.51 GiB peak projects 67.3709% use.
- Preview gate: the build and generated manifest passed; five focused preview
  tests also passed independently.
- Ruff lint and format passed across 33 Python files; strict mypy passed across
  23 source modules; Python dependency consistency passed.
- Vite production build, local npm tree, and offline npm audit with zero
  vulnerabilities passed. Platform- and feature-specific npm packages remain
  optional and were not installed.
- Repository audit approved 833 source candidates: 826 tracked and seven
  non-ignored untracked. It scanned 89 text files / 4,090,769 bytes, skipped
  the 744 grandfathered legacy rasters, verified all 16 ignore probes, and
  found zero path or high-confidence secret violations.
- `git diff --check` passed. All 753 legacy files remained in place; generated
  preview, browser, dependency, cache, and climate artifacts remained ignored.
- Live route checks returned HTTP 200 for preview, legacy, health, and
  availability. The API remained official evidence true, fixture false, four
  products, January/July only, and no complete year.
- Chromium accessibility-oriented DOM audit: zero duplicate IDs, unnamed
  controls, or hidden focusables; one H1, two status regions, and nine labeled
  legend buttons.
- Chromium console: zero errors. Nineteen cumulative MapLibre/WebGL readback
  warnings followed repeated navigation, resizing, and screenshots; one
  deprecation warning came from the layout-shift measurement probe.
- Visual review passed at 390 × 844, 768 × 1024, 1280 × 800, and 1600 × 1000.
  Screenshots remain ignored below `output/playwright/`.

Measurements:

- Generated preview: five files, 1,176,887 bytes raw and 309,916 deterministic
  gzip bytes including MapLibre.
- Application JavaScript: 41,251 bytes / 13,508 deterministic gzip bytes versus
  the 256,000-byte limit. Initial application data excluding MapLibre: 17,621
  gzip bytes versus the 1,048,576-byte limit.
- MapLibre remains separate at 1,053,029 JavaScript bytes / 282,253 gzip and
  69,918 CSS bytes / 10,042 gzip.
- Legacy route inventory: 753 files, 744 rasters, and 115,454,861 bytes served
  in place; no file was copied, moved, or modified.
- Local Chromium DOM content loaded: 51.4 ms; load event: 59.4 ms; cumulative
  layout shift: `0`.
- Uncached single-month development JSON tile: 47,819 bytes / 64.3 ms. Cached
  Jan/Jul development JSON tile: 47,858 encoded bytes / 0.3 ms with zero
  transfer bytes. Southern point response: 14.3 ms.
- Month-control feedback reached the next animation frame in 4.6 ms when
  deselecting January and 26.1 ms when restoring it.
- Browser and service timings are local single-run observations, not
  representative-device or production p95 evidence. Development JSON is not a
  production raster tile.

Decisions:

- Keep the beta build generated and ignored. Serve it alongside, rather than
  copy it over, the legacy root until later release gates authorize cutover.
- Use one loopback origin for preview/API behavior so M1 can validate real
  same-origin requests without adding permissive CORS or embedding a production
  endpoint.
- Treat `/legacy/` and process shutdown as the local rollback. Do not present
  this as immutable remote release promotion, production rollback, or a
  deployed preview.
- Keep M1 active. The preview/build portion is complete, but missing structural
  locations and unavailable browser/accessibility tools prevent the Night 7
  exit gate from closing.
- Preserve all locked UTCI, SPEI-3, selected-month median, 75% validity,
  provider-quality, missing-data, and one/two-variable behavior. This slice
  changes routing and validation only, not climate semantics.

Blockers:

- Tropical, coastal, mountain, urban-adjacent, and broader no-data cases are not
  in the bounded official sample. They need conspicuously structural fixtures
  or additional official acquisition; no observation was fabricated.
- Firefox, WebKit, axe, live screen-reader, grayscale, and color-vision tooling
  remains unavailable. Current evidence is Chromium, semantic DOM checks,
  keyboard behavior, deterministic text contrast, and responsive visuals.
- The palette remains developmental; external climate/licensing review and the
  required palette-comprehension study remain open.
- No complete/global year, production Zarr/COG benchmark, raster tile, remote
  store, runtime, basemap, CDN/CORS, monitoring, deployment, refresh, rollback,
  or production performance evidence exists.
- Creating the recoverable legacy tag remains prohibited without explicit
  authorization.

Next:

- Continue M1 with deterministic, conspicuously non-climate structural
  golden-location coverage for tropical, coastal, mountain, urban-adjacent,
  and no-data cases. Exercise them through the unchanged aggregation, service,
  point interpretation, legend, and browser paths, then update the beta gap
  report without publishing the fixtures as observations.

## 2026-08-06 — Sicily-only scope transition and completion push

Active milestone:

- Scope reset, M2 format architecture, and the independent implementation
  portions of M3, M4, M5, and M6. Official M3 evidence is the first blocking
  gate; later official-data gates remain fail-closed behind it.

Goal:

- Replace the global target with Sicily only and carry out every remaining
  in-scope task that does not require unavailable provider data, external
  review, deployment authority, or a prohibited release action.

Completed:

- Re-read the five required project documents and automation memory in full;
  inspected Git status and diffs, all user changes, package scripts, repository
  inventory, ignored-artifact boundaries, dependencies, credentials without
  values, storage, and milestone gates before editing.
- Made `config/scope.json` the geographic contract using Istat's generalized
  1 January 2026 Sicilia region boundary (`COD_REG=19`). Recorded the official
  archive URL and SHA-256, source CRS, WGS84 bounds, provider-aligned acquisition
  box, constrained map view, limitations, and the 44 exact 0.25° ERA5 cell
  centers whose centers fall inside the multipolygon.
- Changed the authoritative product, execution foundation, sprint notes,
  README, storage/service notes, app identity, package identities, schema title,
  coverage, navigation, and release target from global to Sicily. Historical
  evidence reports and the untouched legacy app remain explicitly historical.
- Added strict scope loading and membership validation. Normalization now
  requires every configured center, writes a `sicily_scope_mask`, masks all
  other climate cells to no data, preserves quality/count semantics, and emits
  one checksum-bound product for each of 2024 and 2025 with 24 golden samples.
- Replaced the current acquisition defaults with an exact 60-request plan: 24
  UTCI monthly daily-maximum containers, 24 deterministic selected-year SPEI-3
  containers, and 12 calendar-month provider-quality containers. Capped CDS
  retries at three attempts, ten seconds maximum delay, and 120 seconds per
  request while preserving atomic, restartable receipts and exact plan audit.
- Added the Sicily local-storage policy and two-year preflight. The policy
  permits only the initial two years locally, blocks a third, keeps every
  managed directory quota, forbids automatic deletion, and preserves the
  standard-mask-only prewarm policy.
- Added and measured a conspicuously structural format benchmark. Selected one
  compressed NetCDF product per Sicily year plus lossless sparse JSON delivery;
  Zarr/COG/raster tiles remain future scale triggers, not prerequisites for 44
  cells. Added the M2 architecture and M3 data-plane reports.
- Made the service scope-aware: outside-mask cells never enter tiles and points
  outside the Sicily mask return explicit no data. It validates release mask
  count and checksum/provenance bindings before serving.
- Constrained MapLibre to Sicily bounds with no world copies or external
  basemap, replaced the globe-like empty reference with a regional grid,
  retained variable-neutral one/two-variable behavior and all 4095 masks, and
  added Sicily-specific source, methodology, limitation, and accessibility
  copy. Planned manifests now fail closed instead of presenting target years as
  partial observations.
- Exercised authenticated bounded provider probes for Sicily UTCI January 2025
  and 2024, the previously proven Phoenix UTCI control, and Sicily SPEI-3
  January 2025. Every probe returned HTTP 500 after the capped retries. No
  partial response, receipt, official report, or fabricated substitute was
  accepted.

Files changed:

- Product and execution documents: `PROJECT_PLAN.md`,
  `COMPLETION_FOUNDATION.md`, `SEVEN_DAY_PLAN.md`, `README.md`, `progress.md`,
  and `services/README.md`.
- Contracts and policy: `config/scope.json`, `config/app.json`,
  `config/manifest.schema.json`, both variable manifests,
  `config/storage-policy.json`, `.gitignore`, CI, Makefile, and package metadata.
- Pipeline/service: scope, acquisition, storage, normalization, API, format
  benchmark, preview/repository audit foundations, M2/M3 reports, and their
  tests.
- Frontend: app, data, inspection, map, registry, state, styles, types, HTML,
  package lock, and tests.

Checks:

- `make foundation-check`: 107 Python tests passed and one official-release
  integration test skipped because the ignored Sicily products are absent; two
  manifests validated; TypeScript passed; all 18 Vitest tests passed.
- Acquisition: 29 tests and secret-safe credential/client status passed. Exact
  inspection correctly failed with 0 of 60 artifacts and plan SHA-256
  `61bbffbe2e6d742148c5d1c0f2ff3aee149bd34a7291736f575898bfe74860f6`.
- Normalization: all 25 scientific/unit tests passed; the production command
  correctly stopped before creating a report because the exact non-fixture
  acquisition plan is incomplete.
- Service: 34 tests passed and one official-release integration test skipped;
  contract validation passed; startup correctly failed because
  `pipeline/reports/sicily-release-v1.json` does not exist.
- Storage: seven tests, validation, status, and two-year preflight passed.
  Repository audit approved 840 source candidates, scanned 96 text files and
  4,137,478 bytes, skipped 744 grandfathered legacy rasters, verified all 16
  ignore probes, and found zero path or high-confidence secret violations.
- Format benchmark, beta preview inspection, Ruff lint/format, strict mypy over
  25 modules, Python dependency consistency, npm dependency tree, offline npm
  audit with zero vulnerabilities, production build, and `git diff --check`
  passed.
- Chromium at 1280 × 800 and 390 × 844 showed the bounded regional grid,
  constrained controls, visible structural-fixture disclosure, correct planned
  source copy, and zero console warnings/errors under a conspicuously labeled
  no-observation browser response. The production no-service state separately
  showed no analysis year and no substituted climate value.

Measurements:

- Scope: Istat WGS84 bbox `11.926367598, 35.493451470,
  15.653298694, 38.817700907`; acquisition grid 16 × 17; 44 included centers.
- Storage: 81.90 GiB free; 64.1236% current volume use; conservative two-year
  peak 654,311,424 bytes; projected 64.3906% use with 81.33 GiB free.
- Structural format benchmark: 28,629-byte compressed NetCDF; 22,594-byte
  sparse JSON / 5,610-byte deterministic gzip; exact round-trip parity; 53.233
  ms local write and 12.285 ms point open/read/close. These are structural local
  timings, not climate observations or production p95 evidence.
- Preview: five files, 1,180,050 bytes raw / 311,100 deterministic gzip;
  application JavaScript 44,210 / 14,647 gzip; initial application data 18,805
  gzip; MapLibre measured separately at
  1,053,029 / 282,253 gzip JavaScript and
  69,918 / 10,042 gzip CSS.

Decisions:

- Sicily is the sole active product scope. Historical global/representative
  evidence remains labeled and is not reused as Sicily observations.
- Two complete target years, one NetCDF per year, and sparse JSON are sufficient
  for the 44-cell release; object storage and raster delivery are not required
  until measured scale triggers or a third year.
- Keep manifests `planned`, retrieval timestamps null, service startup
  fail-closed, and the frontend's production fallback empty until official
  checksummed products exist.
- Preserve all locked UTCI, SPEI-3, equal-weight median, 75% validity,
  provider-quality, no-missing-to-zero, one/two-variable, and month-mask
  semantics. Do not begin M9, deployment, cutover, or legacy cleanup.

Blockers:

- Copernicus CDS processing returned HTTP 500 for both products and the proven
  control. This leaves 0/60 official artifacts, 0/24 source pairs, and 0/2
  complete year products, blocking official M3, M5, service, and preview gates.
- M0's recoverable legacy tag still requires explicit authorization.
- Climate/licensing signoff, palette-comprehension research, axe/live
  screen-reader, color-vision, Firefox/WebKit, representative production
  performance, deployment authority, monitoring, and rollback rehearsal require
  unavailable tools, external people, or user authorization.

Next:

- Retry `thermal_drought.acquire fetch`; if CDS succeeds, run
  `make sicily-release-check`, record exact official bytes/timings and golden
  values, exercise the official two-year preview, and resume the earliest
  remaining external/release gate. If CDS still fails, keep the release planned
  and continue only independent validation work.

## 2026-08-07 — M3/M5 official Sicily release

Active milestone:

- M3 official Sicily data plane and M5 second-year reproducibility. M2's
  measured format decision is now confirmed with official payloads. M1 remains
  the earliest independently actionable incomplete milestone because M0's tag
  and several M1 review/tool gates require authorization or unavailable tools.

Goal:

- Resume the exact bounded provider plan, publish both complete official Sicily
  years without weakening the scientific or artifact boundaries, validate the
  release through the service and real browser, and leave one coherent M3/M5
  handoff rather than advancing to historical backfill.

Completed:

- Re-read the automation memory and all five required project documents in
  full. Inspected Git state, repository files, scripts, ignores, storage,
  credential availability without values, and every existing dirty change;
  no post-run user change was found and all prior work was preserved.
- Re-ran the conservative two-year capacity preflight before retrieval. The
  first sandboxed provider attempt stopped after capped DNS failures; the
  authorized network retry resumed the exact plan and completed all 60 serial,
  atomic partitions without changing the plan fingerprint.
- Acquired 24 UTCI monthly containers of daily maxima, 24 deterministic
  selected-year SPEI-3 containers, and 12 shared reference-period provider-
  quality containers. Wrote checksum-bound receipts and retained all provider
  archives below ignored `data/raw/`.
- Completed the exact source audit with 60/60 artifacts, 24 UTCI/SPEI grid
  comparisons, 24 SPEI/quality comparisons, official evidence true, and no
  missing, unexpected, duplicate, fixture, checksum, provenance, coordinate,
  or unit issue.
- Normalized one compressed, atomically published NetCDF for each of 2024 and
  2025. Both contain all 12 monthly layers on the provider box, preserve only
  the 44 Istat-admitted Sicily cell centers, mask outside cells to no data, and
  retain daily-valid counts and provider quality state.
- Found that the first official golden records used the provider-box midpoint,
  which is outside the Istat mask. Changed Sicily golden selection to the
  in-scope cell nearest the configured initial map center, added a regression
  test, regenerated all 24 golden records at 13.75°E / 37.5°N, and isolated the
  historical representative replay test from the new Sicily raw root.
- Found a second M5 issue during the final composite rerun: unchanged Sicily
  products were replaced because decoded fill sentinels made the in-memory and
  on-disk datasets compare differently. The atomic writer now compares the
  serialized candidate with the serialized current product before replacement.
  A repeat-run regression test confirms unchanged checksums and modification
  times even with outside-scope quality sentinels.
- Published both variable manifests against `sicily-2024-2025-v1`, their exact
  2024/2025 coverage, provider retrieval-completion timestamps, and licences.
  Added a service gate that rejects official products paired with planned
  manifests, missing retrieval timestamps, or mismatched published years.
- Exercised the official release locally in Chromium. Verified 2025 and 2024,
  all-year and disjoint `109` masks, univariate and bivariate modes, source
  retrieval metadata, official point values, responsive phone/desktop layouts,
  semantic control names, status regions, and a clean console. Screenshots and
  browser output remain ignored.
- Updated the README, service handoff, M1 beta report, M2 architecture record,
  and M3 data-plane record. M3 and M5 are complete; no deployment, release
  pointer, DNS/CORS, tag, commit, push, legacy mutation, or M9 work occurred.

Files changed in this run:

- `config/manifest.schema.json`, `config/variables/spei_3.json`, and
  `config/variables/utci_daymax_median.json`.
- `pipeline/src/thermal_drought/api/core.py`,
  `pipeline/src/thermal_drought/normalize/core.py`,
  `pipeline/tests/test_normalization.py`, `pipeline/tests/test_service.py`, and
  `web/src/registry.test.ts`.
- `pipeline/reports/sicily-source-audit-v1.json`,
  `pipeline/reports/sicily-release-v1.json`, and the M1–M3 reports.
- `README.md`, `services/README.md`, and `progress.md`.

Checks:

- `make foundation-check`: 111 Python tests, both published manifests, strict
  TypeScript, and all 18 Vitest tests passed.
- `make acquisition-check`: 29 tests passed; the secret-safe status probe
  confirmed the installed CDS client and non-empty credential file. A restart
  fetch checksum-verified all 60 partitions as `verified-existing` without a
  new provider request.
- `make sicily-release-check`: the 60-artifact inspection, 27 normalization and
  aggregation tests, official normalization, 36 service/aggregation/
  classification tests, manifest validation, and service self-check passed.
- Storage: seven tests, policy validation, live inventory, and the two-year
  preflight passed. Format parity: one structural benchmark test and its exact
  value/nodata/quality/mask round trip passed.
- Preview: TypeScript and Vite production build, artifact inspection, legacy
  inventory, route contract, source-map/symlink rejection, and both transfer
  budgets passed. Repository audit approved 842 source candidates, skipped the
  744 grandfathered legacy rasters, verified all 16 ignore probes, and found no
  path or high-confidence secret violation.
- Ruff lint and format passed across 37 Python files; strict mypy passed across
  25 source modules; Python dependency consistency, local npm tree, offline npm
  audit with zero vulnerabilities, and `git diff --check` passed.
- Real Chromium returned HTTP 200 for availability and tiles; its console had
  zero errors and warnings. The DOM audit found zero duplicate IDs, unnamed
  controls, or hidden focusables, with one H1 and two status regions.

Measurements:

- Acquisition plan SHA-256:
  `61bbffbe2e6d742148c5d1c0f2ff3aee149bd34a7291736f575898bfe74860f6`.
  Raw artifacts total 29,780,288 bytes and receipts 674,186 bytes. The provider
  retrieval window was 09:05:37–09:39:40 UTC; summed retrieval duration was
  2,081.108 seconds, median 29.507 seconds, and maximum 55.128 seconds.
- Inspection covered 767 archive members / 29,592,142 expanded bytes and took
  6.00 seconds. Normalization took 13.57 seconds. The final 2024 product is
  47,317 bytes with SHA-256
  `99aed5cd511054b3b4d5d38bb5a4f320752ac3c86565657680dbaa4e56544fc9`;
  2025 is 47,362 bytes with SHA-256
  `be458e6db12e9048f4c11bd3b302f7a7daef946f73a87e8e58da33f2303ef8e4`.
  A subsequent normalization preserved both hashes and mtimes.
- The 2025 all-year golden point returned SPEI-3 `0.06751701608300209`
  and UTCI `24.102968215942383 °C`, 12/12 valid months each, and provider
  drought quality passing 12/12. The 2024 values were `-0.7856411337852478`
  and `25.4141788482666 °C`.
- Across 20 calls per year, compact all-year tile medians were 9.997–10.486 ms
  and point medians 9.665–10.164 ms. WSGI all-year tile bodies were
  58,197–58,258 bytes; compact deterministic gzip was 2,772–2,791 bytes. These
  are local measurements, not production p95 evidence.
- The final preview has five files, 1,180,118 raw bytes / 311,137 deterministic
  gzip. Application JavaScript is 44,278 bytes / 14,683 gzip and initial
  application data is 18,842 gzip; both pass their budgets. MapLibre remains
  separate at 1,053,029 / 282,253 gzip JavaScript bytes and 69,918 / 10,042
  gzip CSS bytes.
- Storage reported 80.89 GiB free and 64.5657% volume use. The conservative
  two-year peak remains 654,311,424 bytes and projects 64.8327% use. The final
  structural benchmark was 28,629-byte NetCDF, 22,594-byte sparse JSON /
  5,610-byte gzip, 63.827 ms write, and 13.645 ms point open/read/close.
- Chromium DOM content loaded in 51.0 ms and the load event in 52.1 ms at the
  local preview. Phone and desktop screenshots showed readable controls and a
  useful map without overlap.

Decisions:

- Close M3 and M5. The complete official release confirms M2's one-compressed-
  NetCDF-per-year plus lossless sparse JSON architecture; no measured scale
  trigger justifies Zarr, COG, raster tiles, CDN, or object storage for two
  years and 44 cells.
- Keep conservative pre-acquisition estimates in the safety policy despite the
  smaller measured release. They are guardrails, not storage forecasts.
- Treat the source timestamp as retrieval completion, keep quality layers
  separate from selected-year SPEI-3, and require published manifests before
  an official service can start.
- Preserve official and structural evidence as separate paths. Do not invent
  tropical or cold Sicily observations, weaken the 75% rule, substitute zero
  for missing data, reinterpret the SPEI reference period, or start M9.

Blockers:

- M0's recoverable legacy tag still requires explicit authorization.
- M1 still lacks conspicuously structural tropical, cold, mountain, coastal,
  urban-adjacent, and broader no-data golden cases. Firefox, WebKit, axe, a live
  screen reader, grayscale/color-vision tools, independent climate/licensing
  review, and palette-comprehension research remain unavailable or external.
- M4 and M6–M8 still require production container/runtime limits, metrics,
  cache and representative-device performance evidence, hosted artifact
  authority, deployment/routing decisions, monitoring, refresh, security and
  rollback rehearsal. No unavailable gate is claimed complete.

Next:

- Resume M1 with a conspicuously labeled structural golden-location matrix and
  exercise it through the unchanged aggregation, service, point, legend, and
  browser paths without publishing it as climate observation. If external M1
  tools remain unavailable, continue the next independent M4 runtime/security
  slice while preserving the official release and all authorization limits.

## 2026-08-30 — Completion engineering, production readiness, and honest cutover boundary

Goal:

- Execute every remaining engineering and rehearsal step without making a
  Codex Site, preserve the legacy recovery boundary, and distinguish completed
  local evidence from production infrastructure and independent human gates.

Completed:

- Created and verified the annotated local tag `legacy-mediterranean-v1` at the
  last legacy-only commit `3d5b600`; the legacy tree remains unchanged.
- Added 11 explicitly structural, non-observational scenarios covering all nine
  bivariate class pairs plus quality failure and no data. The same aggregation,
  point, map-response, mask, and class paths pass parity without presenting the
  scenarios as Sicily observations.
- Reconfirmed the compressed one-NetCDF-per-year and lossless sparse JSON
  architecture from measured official payloads; no scale trigger justifies
  Zarr, COG, raster tiles, or a CDN for 44 cells and two years.
- Added deterministic immutable release bundles; bounded HTTPS/file download;
  checksum and archive safety validation; versioned install, atomic promote,
  and rollback; and environment-driven container materialization.
- Wrapped the WSGI API with bounded concurrency, rate, timeout, response size,
  cache entries/bytes, atomic file caching, conditional ETags, same-origin or
  allowlisted CORS, security headers, `/live`, `/ready`, and privacy-safe
  `/metrics`.
- Added separate non-root API and Vite/nginx frontend containers, read-only
  filesystems, capability drops, CPU/memory/PID/temp bounds, same-origin `/api/`
  proxying, health checks, CSP and browser security headers. No Codex Site was
  created or used.
- Rehearsed the exact 17-mask × two-year × zoom-0–4 cache warm; cold/warm tile
  and point budgets; all-cell map/point parity; invalid method, origin, mask,
  zoom, and dataset rejection; privacy-safe metrics; and promote/rollback/
  restore behavior.
- Added current official dataset/licence links, Istat transformed-boundary
  attribution, visible Copernicus attribution/disclaimer, methodology, data
  dictionary, operations runbook, security policy, incident response, and M6–M8
  evidence reports.
- Reworked the circular month interaction into twelve 48-pixel native buttons,
  retained the ordered checklist fallback, made data freshness visible, removed
  duplicate fallback markers after MapLibre readiness, and preserved URL,
  variable, year, point, retry, no-data, and quality semantics.
- Added deterministic protanopia, deuteranopia, tritanopia, grayscale,
  text-alternative, and contrast checks. Chromium, Firefox, and WebKit load the
  final official release on desktop/mobile, switch year, inspect a cell, and
  report zero axe violations. The only axe needs-review result is the map title
  overlay, manually confirmed as dark text on a solid near-white background.
- Added non-promoting monthly refresh, production health/freshness, conventional
  image release, container build/config, dependency audit, SBOM, provenance,
  and frontend-artifact workflows.
- Added a fail-closed monitor and refresh rehearsal. The refresh rebuilds both
  official years below ignored output, proves decoded scientific equivalence,
  and confirms the active release is unchanged; HDF5 byte differences are
  explicitly not misrepresented as scientific differences.

Evidence:

- M4 runtime: 170 prewarm requests / 9,831,875 cache bytes; cold tile p95
  12.483 ms; warm tile p95 0.139 ms; warm point p95 0.119 ms; 58,258-byte
  maximum body; all budgets pass.
- Parity: all 44 cells × two years passed (88 map/point comparisons), including
  class distributions and no-data state.
- Browser: Chromium/Firefox/WebKit core flows passed with zero application
  console errors and zero axe violations. Final Chromium DOMContentLoaded was
  25.0 ms, load 26.9 ms, cached year update 14.7 ms, and observed CLS 0.
- Frontend: 20 Vitest tests pass. Application JS is 46.45 kB / 15.33 kB gzip;
  application CSS is 11.81 kB / 3.52 kB gzip. npm reports zero known
  vulnerabilities.
- Remote checkpoint: completion commit `d3094a6` and annotated
  `legacy-mediterranean-v1` tag were pushed to origin. GitHub Actions run
  `33320274977` completed successfully across pipeline, web, and container
  jobs; both Dockerfiles and Compose validated, and the conventional frontend
  artifact was retained.
- Monitor: official evidence true, latest complete year 2025, source freshness
  23.25 days against a 120-day limit, 5.204 ms maximum local endpoint latency,
  privacy contract present, and zero failures.
- Refresh: 2024 and 2025 each retain 12 months and 44 included cells; both are
  scientifically equivalent to the active release and the active release is
  unchanged.

Decisions:

- Close M0–M6 engineering work and the automated portions of M7 and M8. The
  conventional containers and generated CI artifact replace the earlier
  static-site assumption; production remains one origin with the API private
  behind nginx/load balancing.
- Do not self-approve the explicitly independent climate, licensing,
  palette-comprehension, or live assistive-technology gates.
- Do not claim deployment from a local preview. No public endpoint, durable
  release object, DNS/TLS target, alert receiver, infrastructure credential, or
  monitored release cycle was supplied.
- Do not begin M9 backfill or remove `docs/` until independent M7 approvals and
  a monitored M8 public release are complete.

Remaining:

- Owner/infrastructure: provide the public container target, registry release,
  durable HTTPS release-bundle URL and digest, DNS/TLS, production variable
  `PRODUCTION_API_BASE`, and alert receiver; run and observe one release cycle.
- Independent reviewers: approve climate semantics and golden evidence,
  licensing/attribution, palette comprehension, and live assistive-technology
  use.
- After those gates only: backfill years in reverse chronology, compare each
  release, then remove the active legacy tree and make the repository-size
  decision as independently recoverable M9 changes.
