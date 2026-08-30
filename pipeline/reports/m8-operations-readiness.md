# M8 cutover and operations readiness

Status: operational automation and local rehearsals complete; public cutover
and monitored release cycle pending.

## Completed local production rehearsal

- A deterministic 63,073-byte immutable bundle was checksum-verified,
  installed into a versioned store, promoted atomically, and loaded as official
  evidence. The current digest is recorded in
  `pipeline/reports/m4-production-runtime.json`.
- The cache prewarmed the exact 17 approved masks for both years at zooms 0–4:
  170 requests, 170 entries, and 9,831,875 bytes. Arbitrary masks remain
  on-demand.
- Twenty cold samples passed at 12.483 ms p95; 40 warm tile samples passed at
  0.139 ms p95; 40 warm point samples passed at 0.119 ms p95. The largest body
  was 58,258 bytes. These are local production-runtime measurements.
- Map/point parity passed for all 44 scope cells in both years (88
  comparisons), including class distributions and no-data state.
- Security probes returned the intended 405, 403, 400, 400, and 404 statuses.
  Metrics contain route classes and timings only, never coordinates or query
  strings.
- The release store rehearsed promote, rollback, and restoration while
  retaining both releases.
- Refresh rehearsal rebuilt 2024 and 2025 from official raw inputs. Decoded
  coordinates, variables, attributes, masks, and values were scientifically
  equivalent; the active release and its checksums remained unchanged. HDF5
  container bytes are not treated as a scientific equivalence test.
- A local full-stack monitor confirmed official evidence, latest complete year
  2025, 23.25-day source freshness against the 120-day budget, privacy-safe
  metrics, and 5.204 ms maximum endpoint latency with no failures.
- Scheduled workflows now create unpromoted monthly refresh candidates and run
  production health/freshness checks. Release-tag workflow publication builds
  API and frontend images with SBOM and provenance.

## Cutover boundary

No public production endpoint, DNS/TLS target, container registry release tag,
durable HTTPS bundle object, alert receiver, or infrastructure credentials are
configured in the repository. Therefore the replacement has not completed the
required monitored public release cycle. The legacy `docs/` tree remains in
place, protected by the local annotated `legacy-mediterranean-v1` tag, and M9
history/cleanup must not begin until the public M8 gate and independent M7
approvals are signed off.
