# Security policy

Report suspected vulnerabilities privately to the repository owner rather
than opening an issue that includes credentials, private infrastructure, or
exploit details.

The service accepts only bounded `GET`, `HEAD`, and `OPTIONS` requests. It caps
zoom, variables, years, month masks, coordinates, concurrency, request time,
response bytes, cache entries, cache bytes, and request rate. Release downloads
require HTTPS and an exact SHA-256; archives reject traversal, links,
encryption, duplicates, and excess size. Provider and storage credentials stay
server-side. Production containers drop capabilities, use read-only filesystems
and non-root users, and have CPU, memory, PID, and temporary-storage bounds.

The browser receives only public derived climate values. Runtime metrics never
record precise coordinates or query strings. The frontend sets a restrictive
Content Security Policy, no-referrer policy, permissions policy, and MIME
sniffing protection. Dependency audit, unit/integration checks, container
builds, SBOM/provenance generation, and secret/repository audits run in CI.
