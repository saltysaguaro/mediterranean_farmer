"""Build inspection and local routing for the recoverable beta preview."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import mimetypes
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any

StartResponse = Callable[[str, list[tuple[str, str]]], Any]
WsgiApplication = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]

APPLICATION_JAVASCRIPT_GZIP_BUDGET = 250 * 1024
INITIAL_APPLICATION_DATA_GZIP_BUDGET = 1024 * 1024


class PreviewError(ValueError):
    """A deterministic preview build or routing failure."""


@dataclass(frozen=True)
class PreviewArtifact:
    """One immutable generated preview artifact."""

    path: str
    bytes: int
    gzip_bytes: int
    sha256: str
    map_library: bool


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _artifact(path: Path, root: Path) -> PreviewArtifact:
    if path.is_symlink():
        raise PreviewError(
            f"preview artifact must not be a symbolic link: {path.relative_to(root)}"
        )
    content = path.read_bytes()
    relative = path.relative_to(root).as_posix()
    return PreviewArtifact(
        path=relative,
        bytes=len(content),
        gzip_bytes=len(gzip.compress(content, compresslevel=9, mtime=0)),
        sha256=_sha256(content),
        map_library="maplibre" in path.name.lower(),
    )


def _preview_artifacts(preview_root: Path) -> tuple[PreviewArtifact, ...]:
    if not preview_root.is_dir():
        raise PreviewError(f"preview build directory is missing: {preview_root}")
    index_path = preview_root / "index.html"
    if not index_path.is_file():
        raise PreviewError(f"preview index is missing: {index_path}")
    paths = sorted(path for path in preview_root.rglob("*") if path.is_file() or path.is_symlink())
    if not paths:
        raise PreviewError("preview build contains no files")
    artifacts = tuple(_artifact(path, preview_root) for path in paths)
    if any(artifact.path.endswith(".map") for artifact in artifacts):
        raise PreviewError("preview build must not publish source maps")
    return artifacts


def inspect_preview(preview_root: Path, legacy_root: Path) -> dict[str, object]:
    """Return a deterministic preview/legacy inventory and enforce local budgets."""

    artifacts = _preview_artifacts(preview_root)
    if not (legacy_root / "index.html").is_file():
        raise PreviewError(f"legacy index is missing: {legacy_root / 'index.html'}")

    application_javascript = [
        artifact
        for artifact in artifacts
        if artifact.path.endswith(".js") and not artifact.map_library
    ]
    initial_application = [artifact for artifact in artifacts if not artifact.map_library]
    application_javascript_gzip_bytes = sum(
        artifact.gzip_bytes for artifact in application_javascript
    )
    initial_application_data_gzip_bytes = sum(
        artifact.gzip_bytes for artifact in initial_application
    )
    application_budget_pass = application_javascript_gzip_bytes < APPLICATION_JAVASCRIPT_GZIP_BUDGET
    initial_data_budget_pass = (
        initial_application_data_gzip_bytes < INITIAL_APPLICATION_DATA_GZIP_BUDGET
    )
    if not application_budget_pass or not initial_data_budget_pass:
        raise PreviewError("generated preview exceeds a checked frontend performance budget")

    legacy_files = sorted(path for path in legacy_root.rglob("*") if path.is_file())
    legacy_rasters = [
        path for path in legacy_files if path.suffix.lower() in {".tif", ".tiff", ".webp"}
    ]
    return {
        "status": "approved",
        "scope": "local Sicily release preview; not a deployment",
        "routes": {
            "preview": "/preview/",
            "legacy": "/legacy/",
            "api": "/api/v1/",
        },
        "preview": {
            "file_count": len(artifacts),
            "bytes": sum(artifact.bytes for artifact in artifacts),
            "gzip_bytes": sum(artifact.gzip_bytes for artifact in artifacts),
            "artifacts": [asdict(artifact) for artifact in artifacts],
        },
        "budgets": {
            "application_javascript_gzip_bytes": application_javascript_gzip_bytes,
            "application_javascript_gzip_limit": APPLICATION_JAVASCRIPT_GZIP_BUDGET,
            "application_javascript_pass": application_budget_pass,
            "initial_application_data_gzip_bytes": initial_application_data_gzip_bytes,
            "initial_application_data_gzip_limit": INITIAL_APPLICATION_DATA_GZIP_BUDGET,
            "initial_application_data_pass": initial_data_budget_pass,
            "map_library_excluded": True,
        },
        "legacy": {
            "served_in_place": True,
            "file_count": len(legacy_files),
            "raster_count": len(legacy_rasters),
            "bytes": sum(path.stat().st_size for path in legacy_files),
        },
    }


def _write_manifest(path: Path, repository: Path, payload: dict[str, object]) -> None:
    output_root = (repository / "output").resolve()
    resolved = path.resolve()
    if not _is_within(resolved, output_root):
        raise PreviewError("generated preview manifests must remain below ignored output/")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_suffix(resolved.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(resolved)


def _status_line(status: int) -> str:
    return f"{status} {HTTPStatus(status).phrase}"


def _respond(
    start_response: StartResponse,
    status: int,
    body: bytes,
    content_type: str,
    *,
    method: str,
    cache_control: str = "no-store",
    extra_headers: Sequence[tuple[str, str]] = (),
) -> Iterable[bytes]:
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", cache_control),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "no-referrer"),
        ("Permissions-Policy", "geolocation=(), microphone=(), camera=()"),
        (
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; worker-src 'self' blob:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        ),
        *extra_headers,
    ]
    start_response(_status_line(status), headers)
    return [] if method == "HEAD" else [body]


def _redirect(start_response: StartResponse, location: str, *, method: str) -> Iterable[bytes]:
    body = f"Continue to {location}\n".encode()
    return _respond(
        start_response,
        308,
        body,
        "text/plain; charset=utf-8",
        method=method,
        extra_headers=(("Location", location),),
    )


def _static_response(
    root: Path,
    relative: str,
    start_response: StartResponse,
    *,
    method: str,
    preview: bool,
) -> Iterable[bytes]:
    normalized = relative or "index.html"
    parts = Path(normalized).parts
    if normalized.startswith("/") or any(part in {".", ".."} for part in parts):
        return _respond(
            start_response,
            404,
            b"Not found\n",
            "text/plain; charset=utf-8",
            method=method,
        )
    candidate = (root / normalized).resolve()
    resolved_root = root.resolve()
    if not _is_within(candidate, resolved_root) or not candidate.is_file():
        return _respond(
            start_response,
            404,
            b"Not found\n",
            "text/plain; charset=utf-8",
            method=method,
        )
    content = candidate.read_bytes()
    media_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    if media_type.startswith("text/") or media_type in {"application/javascript", "image/svg+xml"}:
        media_type = f"{media_type}; charset=utf-8"
    cache_control = "no-store"
    if preview and candidate.name != "index.html":
        cache_control = "public, max-age=31536000, immutable"
    return _respond(
        start_response,
        200,
        content,
        media_type,
        method=method,
        cache_control=cache_control,
    )


class PreviewApplication:
    """Serve the generated preview and legacy tree side by side with one API origin."""

    def __init__(
        self,
        preview_root: Path,
        legacy_root: Path,
        api_application: WsgiApplication,
        *,
        root_mode: str = "handoff",
    ) -> None:
        self.preview_root = preview_root
        self.legacy_root = legacy_root
        self.api_application = api_application
        if root_mode not in {"handoff", "replacement"}:
            raise ValueError("root mode must be handoff or replacement")
        self.root_mode = root_mode

    def __call__(
        self,
        environ: dict[str, Any],
        start_response: StartResponse,
    ) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", ""))
        if path.startswith("/api/"):
            forwarded = dict(environ)
            forwarded["PATH_INFO"] = path.removeprefix("/api")
            return self.api_application(forwarded, start_response)
        if method not in {"GET", "HEAD"}:
            return _respond(
                start_response,
                405,
                b"Only GET and HEAD are supported\n",
                "text/plain; charset=utf-8",
                method=method,
                extra_headers=(("Allow", "GET, HEAD"),),
            )
        if path == "/preview":
            return _redirect(start_response, "/preview/", method=method)
        if path == "/legacy":
            return _redirect(start_response, "/legacy/", method=method)
        if path.startswith("/preview/"):
            return _static_response(
                self.preview_root,
                path.removeprefix("/preview/"),
                start_response,
                method=method,
                preview=True,
            )
        if path.startswith("/legacy/"):
            return _static_response(
                self.legacy_root,
                path.removeprefix("/legacy/"),
                start_response,
                method=method,
                preview=False,
            )
        if self.root_mode == "replacement":
            return _static_response(
                self.preview_root,
                path.removeprefix("/"),
                start_response,
                method=method,
                preview=True,
            )
        if path == "/":
            body = b"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Local beta handoff</title><body><main><h1>Local beta handoff</h1>
<p>The replacement is limited to Sicilia on official 0.25-degree provider grid cells.</p>
<ul><li><a href="/preview/">Open the replacement preview</a></li>
<li><a href="/legacy/">Open the preserved legacy application</a></li></ul>
</main></body></html>"""
            return _respond(
                start_response,
                200,
                body,
                "text/html; charset=utf-8",
                method=method,
            )
        return _respond(
            start_response,
            404,
            b"Not found\n",
            "text/plain; charset=utf-8",
            method=method,
        )


def create_preview_app(
    preview_root: Path,
    legacy_root: Path,
    api_application: WsgiApplication,
    *,
    root_mode: str = "handoff",
) -> WsgiApplication:
    return PreviewApplication(
        preview_root,
        legacy_root,
        api_application,
        root_mode=root_mode,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=repository_root())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--allow-fixture", action="store_true")
    parser.add_argument(
        "--root-mode",
        choices=("handoff", "replacement"),
        default="handoff",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = args.repository_root.resolve()
    preview_root = repository / "web" / "dist"
    legacy_root = repository / "docs"
    try:
        report = inspect_preview(preview_root, legacy_root)
        if args.manifest_output is not None:
            _write_manifest(args.manifest_output, repository, report)
    except (OSError, PreviewError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}, sort_keys=True))
        return 2
    if args.check:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if not 1 <= args.port <= 65535:
        print("Preview startup failed: port must be between 1 and 65535")
        return 2

    from wsgiref.simple_server import make_server

    from thermal_drought.api.app import create_app
    from thermal_drought.api.core import DataService
    from thermal_drought.api.runtime import RuntimeSettings, create_production_app

    try:
        selected_report = args.report
        if selected_report is not None and not selected_report.is_absolute():
            selected_report = repository / selected_report
        service = DataService.from_repository(
            repository,
            report_path=selected_report,
            allow_fixture=args.allow_fixture,
        )
        runtime_settings = RuntimeSettings.load(repository / "config" / "app.json", repository)
        api_application = create_production_app(
            create_app(service),
            runtime_settings,
            readiness=lambda: bool(service.release.products),
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Preview startup failed: {error}")
        return 2
    application = create_preview_app(
        preview_root,
        legacy_root,
        api_application,
        root_mode=args.root_mode,
    )
    with make_server(args.host, args.port, application) as server:
        print(f"Preview: http://{args.host}:{args.port}/preview/")
        print(f"Legacy: http://{args.host}:{args.port}/legacy/")
        if args.root_mode == "replacement":
            print(f"Replacement root: http://{args.host}:{args.port}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Preview stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
