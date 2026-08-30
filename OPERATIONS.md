# Production operations

## Release architecture

The frontend and API run as separate conventional containers behind one origin.
The frontend proxy maps `/api/` to the API, so production does not need broad
CORS and never exposes provider credentials. The API installs an immutable
HTTPS release bundle only when its configured SHA-256 matches, validates every
member and product, and then atomically promotes a small `current.json`
pointer. At least one prior installed release is retained.

Build and exercise the complete local production gate:

```bash
make operations-check
```

Set `THERMAL_DROUGHT_RELEASE_BUNDLE_URL` to a durable HTTPS object and
`THERMAL_DROUGHT_RELEASE_BUNDLE_SHA256` to its exact digest before starting the
stack or validating its resolved configuration:

```bash
export THERMAL_DROUGHT_RELEASE_BUNDLE_URL=https://object.example/releases/sicily-2024-2025-v1.zip
export THERMAL_DROUGHT_RELEASE_BUNDLE_SHA256=replace_with_exact_64_character_sha256
docker compose config
docker compose up --detach
```

Bind the public load balancer to frontend port 8080; keep API port 8000 private.
Terminate TLS at the load balancer and allow only HTTPS.

## Promotion and rollback

Build and inspect a candidate with `thermal-drought-release build`. Upload it
without overwriting any prior object. Install and validate it in the release
store, prewarm exactly the 17 standard masks, run `operations-check`, then
promote its digest. Do not alter a running release directory.

Rollback is `thermal-drought-release rollback --store <release-store>`. It
atomically swaps the pointer to the retained prior release; restart the API if
the process does not rematerialize pointers dynamically. The automated M4
rehearsal promotes a valid copy, rolls back, verifies the starting digest, and
retains both directories.

## Monitoring and alerts

`thermal-drought-monitor https://host/api` checks liveness, readiness,
official-release identity, latest complete year, source freshness, metrics,
and latency without sending or recording coordinates. Configure the repository
variable `PRODUCTION_API_BASE` to enable the scheduled monitor. Alert on any
nonzero exit, freshness above 120 days, readiness failure, repeated 429/503/504
responses, refresh failures, or a sudden class-distribution change.

The JSON metrics endpoint records route classes, counts, response bytes, cache
inventory, and latency summaries. It deliberately excludes coordinates and
query strings.

## Monthly refresh

The scheduled workflow chooses only the two prior calendar years, downloads
the exact bounded plan, requires all twelve months for both variables and the
provider quality layers, normalizes to a new candidate directory, and uploads
an unpromoted review artifact. Missing provider months or credentials fail the
job; the active release remains unchanged.

Run `make refresh-rehearsal-check` locally. It rebuilds both official years
below ignored `output/`, compares decoded coordinates, variables, attributes,
and values to the active release, and never changes the live pointer. HDF5
container bytes may differ across equivalent writes, so immutable release
checksums identify artifacts while decoded equality proves scientific
reproducibility.

## Incident response

1. Confirm `/api/v1/live`, `/ready`, `/availability`, and `/metrics` from a
   second network and device.
2. Stop promotion. Preserve logs, the active pointer, bundle digest, and
   release report; do not log sample queries or coordinates.
3. If data identity, parity, freshness, or scientific validation failed,
   rollback the release pointer and restart the API.
4. If only the frontend failed, deploy the prior immutable frontend image while
   keeping the data pointer unchanged.
5. Re-run monitor, one point/tile parity check, the 17-mask cache warm, and
   phone/desktop smoke tests.
6. Document the cause and corrective release. Never edit an installed release
   in place or delete the prior release during the incident.
