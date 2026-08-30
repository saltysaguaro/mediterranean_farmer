# M6 production frontend evidence

Status: engineering gate complete; public deployment evidence pending.

The replacement is a conventional Vite application served by an unprivileged
nginx container. It uses same-origin `/api/` routing to the bounded Python API;
no Codex Site or hosted-site integration is part of the architecture. The
container is read-only, drops all capabilities, and includes health and
security-header configuration. CI type-checks, tests, audits, builds, uploads
the generated frontend artifact, builds both containers, and validates the
Compose model.

## Final local evidence

- Latest complete year 2025 and all twelve months load by default from the
  official two-year release.
- Chromium, Firefox, and WebKit load official availability and lossless map
  responses, switch years, and inspect the center cell consistently.
- Desktop and 390 × 844 mobile screenshots show usable map and controls. The
  MapLibre-ready state hides the static fallback markers, so data markers are
  not duplicated.
- axe-core 4.10.3 reports zero violations in all three engines. Its only
  needs-review item is `#map-title`, whose computed `rgb(23, 34, 28)` text on
  `rgb(250, 252, 248)` is manually confirmed at high contrast; axe cannot
  infer the background because the heading overlays the map.
- The final local Chromium navigation reached DOMContentLoaded in 25.0 ms and
  load in 26.9 ms. A cached 2025-to-2024 update completed in 14.7 ms. Observed
  layout shift was 0 in the final run.
- Vite emitted a 46.45 kB application JavaScript chunk (15.33 kB gzip) and
  11.81 kB application CSS (3.52 kB gzip). MapLibre remains an independently
  cacheable 1,053.03 kB vendor chunk (283.19 kB gzip).
- Twenty Vitest cases cover state, all 4,095 month masks, registry behavior,
  data failure states, inspection, legend semantics, contrast, grayscale, and
  common color-vision-deficiency simulations. The npm audit reports zero known
  vulnerabilities.
- GitHub Actions run
  [33320274977](https://github.com/saltysaguaro/mediterranean_farmer/actions/runs/33320274977)
  passed the pipeline, web, and container jobs for commit `d3094a6`. It built
  both Dockerfiles, validated the Compose configuration, and retained the
  314,786-byte `sicily-production-frontend` artifact.

## Remaining release evidence

A public URL, TLS/load-balancer target, durable release-bundle URL, and
production environment credentials have not been supplied. Consequently this
report does not claim a hosted preview, public route, representative network
latency, or production device telemetry. Those are M8 deployment inputs, not
missing frontend implementation.
