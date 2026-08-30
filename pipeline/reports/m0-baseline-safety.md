# M0 baseline safety report

Recorded: 2026-08-05 02:15 MST (-0700)

## Recoverable source state

- `main` and `origin/main` both point to
  `30596c27616f62e1cd56598e8970225ecc1a8118`.
- That commit contains the Night 1–6 source, manifests, tests, small evidence
  reports, and the unchanged 753-file legacy application.
- Its parent, `3d5b600839669cb81d953394359a046378eb7e5c`, is the last
  legacy-only application commit and is the proposed recoverable legacy-tag
  target.
- No tag was created. Tag creation remains an explicit-authorization action.
- The active completion plan and this M0 slice remain local reviewable changes;
  no commit, tag, push, publication, deployment, or history rewrite occurred.

The existing checkpoint can be reviewed in the completion foundation's logical
groups without rewriting history:

1. Plans, manifests, Makefile, and CI: `PROJECT_PLAN.md`,
   `SEVEN_DAY_PLAN.md`, `.github/`, `Makefile`, and `config/`.
2. Acquisition, normalization, storage, and evidence: `pipeline/src/thermal_drought/acquire/`,
   `pipeline/src/thermal_drought/normalize/`, `pipeline/src/thermal_drought/storage.py`,
   and `pipeline/reports/night-*`.
3. Aggregation, classification, and service: `pipeline/src/thermal_drought/aggregation.py`,
   `pipeline/src/thermal_drought/classification.py`, `pipeline/src/thermal_drought/api/`,
   and `services/`.
4. Frontend: `web/`.
5. Tests and documentation: `pipeline/tests/`, `tests/`, `README.md`, and
   `progress.md`.

## Automated repository boundary

`make repository-check` audits Git-tracked files plus non-ignored untracked
commit candidates. It never enumerates or opens ignored provider data,
credentials, environments, dependencies, builds, caches, or browser output.

The 2026-08-05 audit approved 830 source candidates: 826 tracked files and four
non-ignored untracked candidates. It scanned 86 text files, found no candidate
path violation and no high-confidence secret, and verified all 16 representative
ignore probes. The only generated-raster exception is pinned to the 744 already
tracked legacy files under `docs/data/crops/`: 248 TIFFs and 496 WebPs totaling
112,292,952 bytes. A new raster, even inside that tree, fails the audit.

The no-value-echo secret scan covers private-key headers and high-confidence
AWS, GitHub, Google, Slack, Stripe, OpenAI, CDS, and credentialed-URL patterns.
It complements path and ignore enforcement; it does not claim that a dedicated
external secret-scanning product is installed.

## Complete supported check report

All checks below passed on 2026-08-05:

- 95 full Python tests, including four repository-audit tests;
- 26 acquisition tests and a secret-safe credential/client status probe;
- 24 aggregation/normalization tests plus exact official-sample replay;
- 34 aggregation/classification/service tests, both manifests, and the
  four-product official-evidence catalogue;
- seven storage tests, policy validation, live inventory, and one-year
  preflight;
- Ruff lint and format across 31 Python files and strict mypy across 22 source
  modules;
- Python dependency consistency;
- strict TypeScript and 18 Vitest tests;
- Vite production build, local npm tree, offline npm audit with zero reported
  vulnerabilities, and `git diff --check`;
- the repository boundary and no-value-echo high-confidence secret scan;
- live Chromium Phoenix inspection, accessibility semantics, desktop/phone
  visual review, browser console review, and local timing/size probes.

Measured build output:

- application JavaScript: 41.25 kB / 13.53 kB gzip;
- MapLibre JavaScript: 1,053.03 kB / 283.19 kB gzip, kept separate from the
  application budget;
- application CSS: 11.42 kB / 3.46 kB gzip;
- MapLibre CSS: 69.92 kB / 10.10 kB gzip.

Measured bounded local service and browser evidence:

- Phoenix point: SPEI-3 `-0.5169` / `No drought`; UTCI `31.8961 °C` /
  `Heat stress`; two of two months valid and provider drought quality passed;
- three point requests: 1,731 bytes and 9.607–11.564 ms;
- three zoom-zero development tiles: 47,858 bytes and 35.636–36.323 ms;
- local Vite navigation load event: 69.8 ms;
- Chromium semantics: zero duplicate IDs, unnamed buttons, unnamed selects, or
  focusable descendants of `aria-hidden`; one H1 and three live regions;
- Chromium console: zero errors and four MapLibre/WebGL readback performance
  warnings;
- visual review at 1280 × 800 and 390 × 844 found the map, bounded-data label,
  controls, and point interpretation readable.

These are localhost development measurements, not production p95 evidence.
The 47,858-byte response is sparse JSON, not the planned production lossless
raster tile. Firefox, WebKit, axe, live-screen-reader, color-vision,
comprehension, complete-year/global-data, production load, and production
latency gates remain open for M1 and later milestones.

## M0 disposition

The independent engineering portion of M0 passes: the baseline is checkpointed,
fresh-checkout checks are documented, the artifact boundary is enforced in CI,
and the full supported local suite is green. The recoverable legacy tag remains
the only M0 action blocked on explicit authorization. Night 7 / M1 can proceed
independently without modifying or replacing the legacy application.
