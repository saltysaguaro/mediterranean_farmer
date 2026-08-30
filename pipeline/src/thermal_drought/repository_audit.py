"""Audit the source-control boundary without reading ignored credentials or data."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

IGNORED_BOUNDARY_PROBES = (
    ".env",
    ".cdsapirc",
    "data/raw/provider-response.nc",
    "data/cache/composite.bin",
    "data/canonical/annual.zarr/chunk",
    "data/published/month.tif",
    "data/tiles/0/0/0.png",
    "pipeline/.venv/bin/python",
    "web/node_modules/package/index.js",
    "web/dist/index.html",
    ".cache/runtime.bin",
    "services/tile/cache/0.png",
    "services/state.sqlite",
    "output/preview/smoke.png",
    ".playwright-cli/page.yml",
    "coverage/index.html",
)

_CACHE_PARTS = {
    ".cache",
    ".mypy_cache",
    ".playwright-cli",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
_BINARY_SUFFIXES = {
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
    ".woff",
    ".woff2",
}
_CLIMATE_SUFFIXES = {".nc", ".nc4", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    kind: str


@dataclass(frozen=True)
class PathViolation:
    path: str
    reason: str


def _secret_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Return high-confidence patterns assembled to avoid matching this source file."""

    return (
        (
            "private_key",
            re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        ),
        ("aws_access_key", re.compile(r"\b(?:AK" + r"IA|AS" + r"IA)[0-9A-Z]{16}\b")),
        (
            "github_token",
            re.compile(
                r"\bgh" + r"[pousr]_[A-Za-z0-9]{36,255}\b|\bgithub_pat_[A-Za-z0-9_]{40,255}\b"
            ),
        ),
        ("google_api_key", re.compile(r"\bAI" + r"za[0-9A-Za-z_-]{35}\b")),
        ("slack_token", re.compile(r"\bxox" + r"[aboprs]-[0-9A-Za-z-]{20,}\b")),
        ("stripe_live_key", re.compile(r"\bsk_" + r"live_[0-9A-Za-z]{16,}\b")),
        (
            "openai_api_key",
            re.compile(r"\bsk-" + r"(?:proj-)?[0-9A-Za-z_-]{32,}\b"),
        ),
        (
            "credentialed_url",
            re.compile(r"https?://[^\s/:@]+:[^\s/@]+@[^\s/]+"),
        ),
        (
            "cds_api_key",
            re.compile(r"^\s*key\s*:\s*[0-9a-f-]{8,}:[0-9A-Za-z_-]{20,}\s*$", re.IGNORECASE),
        ),
    )


def _run_git(repo_root: Path, args: Sequence[str], *, stdin: str | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        input=stdin,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _git_paths(repo_root: Path, *args: str) -> tuple[PurePosixPath, ...]:
    output = _run_git(repo_root, [*args, "-z"])
    return tuple(PurePosixPath(item) for item in output.split("\0") if item)


def _is_legacy_raster(path: PurePosixPath) -> bool:
    return (
        len(path.parts) >= 4
        and path.parts[:3] == ("docs", "data", "crops")
        and path.suffix.lower() in {".tif", ".tiff", ".webp"}
    )


def path_violation(path: PurePosixPath, *, allow_legacy_raster: bool = True) -> str | None:
    """Return the artifact-boundary reason for a commit-candidate path."""

    path_text = path.as_posix()
    name = path.name
    suffix = path.suffix.lower()

    if path_text == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return "credential_path"
    if name == ".cdsapirc" or name.startswith("credentials."):
        return "credential_path"
    if path.parts and path.parts[0] == "data":
        return "climate_data_path"
    if any(part in _CACHE_PARTS for part in path.parts):
        return "dependency_or_cache_path"
    if path.parts[:2] == ("web", "dist"):
        return "generated_web_build"
    if path.parts and path.parts[0] == "output":
        return "generated_browser_output"
    if path.parts and path.parts[0] == "coverage":
        return "generated_coverage_output"
    if "cache" in path.parts and path.parts and path.parts[0] == "services":
        return "runtime_cache_path"
    if path.parts and path.parts[0] == "services" and suffix == ".sqlite":
        return "runtime_state_path"
    if any(part.endswith(".zarr") for part in path.parts):
        return "canonical_array_path"
    if suffix in _CLIMATE_SUFFIXES and not (allow_legacy_raster and _is_legacy_raster(path)):
        return "generated_or_climate_artifact"
    return None


def scan_text(path: PurePosixPath, text: str) -> tuple[SecretFinding, ...]:
    findings: list[SecretFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in _secret_patterns():
            if pattern.search(line):
                findings.append(SecretFinding(path.as_posix(), line_number, kind))
    return tuple(findings)


def _ignored_probe_report(repo_root: Path) -> tuple[list[str], list[str]]:
    probe_input = "\n".join(IGNORED_BOUNDARY_PROBES) + "\n"
    completed = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=repo_root,
        input=probe_input,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(
            completed.returncode,
            completed.args,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    ignored = {line for line in completed.stdout.splitlines() if line}
    return sorted(ignored), sorted(set(IGNORED_BOUNDARY_PROBES) - ignored)


def _unique_paths(paths: Iterable[PurePosixPath]) -> tuple[PurePosixPath, ...]:
    return tuple(sorted(set(paths), key=PurePosixPath.as_posix))


def audit_repository(repo_root: Path) -> dict[str, object]:
    repo_root = repo_root.resolve()
    tracked = _git_paths(repo_root, "ls-files")
    untracked_candidates = _git_paths(repo_root, "ls-files", "--others", "--exclude-standard")
    candidates = _unique_paths((*tracked, *untracked_candidates))

    tracked_set = set(tracked)
    violations = tuple(
        PathViolation(path.as_posix(), reason)
        for path in candidates
        if (
            reason := path_violation(
                path,
                allow_legacy_raster=path in tracked_set,
            )
        )
        is not None
    )

    secret_findings: list[SecretFinding] = []
    scanned_text_files = 0
    scanned_text_bytes = 0
    skipped_binary_files = 0
    candidate_bytes = 0
    legacy_tif_files = 0
    legacy_webp_files = 0
    legacy_bytes = 0

    for path in candidates:
        absolute_path = repo_root / path
        if not absolute_path.is_file():
            continue
        size = absolute_path.stat().st_size
        candidate_bytes += size
        if _is_legacy_raster(path):
            legacy_bytes += size
            if path.suffix.lower() in {".tif", ".tiff"}:
                legacy_tif_files += 1
            elif path.suffix.lower() == ".webp":
                legacy_webp_files += 1
        if path.suffix.lower() in _BINARY_SUFFIXES:
            skipped_binary_files += 1
            continue
        content = absolute_path.read_bytes()
        if b"\0" in content:
            skipped_binary_files += 1
            continue
        text = content.decode("utf-8", errors="replace")
        scanned_text_files += 1
        scanned_text_bytes += len(content)
        secret_findings.extend(scan_text(path, text))

    ignored_probes, missing_ignored_probes = _ignored_probe_report(repo_root)
    head = _run_git(repo_root, ["rev-parse", "HEAD"]).strip()
    approved = not violations and not secret_findings and not missing_ignored_probes

    return {
        "approved": approved,
        "head_commit": head,
        "tracked_file_count": len(tracked),
        "untracked_candidate_file_count": len(untracked_candidates),
        "source_candidate_file_count": len(candidates),
        "source_candidate_bytes": candidate_bytes,
        "text_files_scanned": scanned_text_files,
        "text_bytes_scanned": scanned_text_bytes,
        "binary_files_skipped": skipped_binary_files,
        "legacy_rasters": {
            "root": "docs/data/crops",
            "tif_files": legacy_tif_files,
            "webp_files": legacy_webp_files,
            "bytes": legacy_bytes,
            "treatment": "grandfathered_until_reviewed_cutover",
        },
        "ignored_boundary_probes": ignored_probes,
        "missing_ignored_boundary_probes": missing_ignored_probes,
        "path_violations": [asdict(item) for item in violations],
        "secret_scan": {
            "mode": "high_confidence_no_value_echo",
            "finding_count": len(secret_findings),
            "findings": [asdict(item) for item in secret_findings],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit source candidates, ignored artifacts, legacy rasters, and secrets."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = audit_repository(args.repo_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["approved"] else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
