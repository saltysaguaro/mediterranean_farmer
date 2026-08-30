from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

from thermal_drought.preview import PreviewApplication, PreviewError, inspect_preview


def _write_fixture(root: Path) -> tuple[Path, Path]:
    preview = root / "web" / "dist"
    legacy = root / "docs"
    assets = preview / "assets"
    assets.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (preview / "index.html").write_text(
        '<script type="module" src="./assets/index-abc123.js"></script>\n'
    )
    (assets / "index-abc123.js").write_text("console.log('preview')\n")
    (assets / "maplibre-def456.js").write_text("/* map library */\n")
    (legacy / "index.html").write_text("<h1>Legacy</h1>\n")
    (legacy / "app.js").write_text("console.log('legacy')\n")
    (legacy / "sample.webp").write_bytes(b"legacy raster")
    return preview, legacy


def _api_stub(environ: dict[str, Any], start_response: Any) -> Iterable[bytes]:
    body = json.dumps({"path": environ["PATH_INFO"]}).encode()
    start_response(
        "200 OK",
        [("Content-Type", "application/json"), ("Content-Length", str(len(body)))],
    )
    return [body]


def _request(
    application: PreviewApplication,
    path: str,
    method: str = "GET",
) -> tuple[str, dict[str, str], bytes]:
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(
        application(
            {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": ""},
            start_response,
        )
    )
    return str(captured["status"]), captured["headers"], body  # type: ignore[return-value]


def test_preview_inventory_keeps_map_library_and_legacy_boundaries_separate(
    tmp_path: Path,
) -> None:
    preview, legacy = _write_fixture(tmp_path)

    report = inspect_preview(preview, legacy)

    assert report["status"] == "approved"
    assert report["budgets"]["application_javascript_pass"] is True  # type: ignore[index]
    assert report["budgets"]["map_library_excluded"] is True  # type: ignore[index]
    assert report["legacy"] == {  # type: ignore[comparison-overlap]
        "served_in_place": True,
        "file_count": 3,
        "raster_count": 1,
        "bytes": sum(path.stat().st_size for path in legacy.iterdir()),
    }


def test_preview_inventory_rejects_source_maps_and_symlinks(tmp_path: Path) -> None:
    preview, legacy = _write_fixture(tmp_path)
    (preview / "assets" / "index.js.map").write_text("{}")
    with pytest.raises(PreviewError, match="source maps"):
        inspect_preview(preview, legacy)

    (preview / "assets" / "index.js.map").unlink()
    (preview / "assets" / "linked.js").symlink_to(preview / "assets" / "index-abc123.js")
    with pytest.raises(PreviewError, match="symbolic link"):
        inspect_preview(preview, legacy)


def test_preview_routes_replacement_legacy_and_api_without_copying(tmp_path: Path) -> None:
    preview, legacy = _write_fixture(tmp_path)
    application = PreviewApplication(preview, legacy, _api_stub)

    status, headers, body = _request(application, "/preview/")
    assert status == "200 OK"
    assert headers["Cache-Control"] == "no-store"
    assert b"index-abc123.js" in body

    status, headers, body = _request(application, "/preview/assets/index-abc123.js")
    assert status == "200 OK"
    assert headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert body == b"console.log('preview')\n"

    status, headers, body = _request(application, "/legacy/")
    assert status == "200 OK"
    assert headers["Cache-Control"] == "no-store"
    assert body == b"<h1>Legacy</h1>\n"

    status, _, body = _request(application, "/api/v1/health")
    assert status == "200 OK"
    assert json.loads(body) == {"path": "/v1/health"}


def test_preview_rejects_traversal_and_unsafe_methods(tmp_path: Path) -> None:
    preview, legacy = _write_fixture(tmp_path)
    application = PreviewApplication(preview, legacy, _api_stub)

    assert _request(application, "/preview/../docs/index.html")[0] == "404 Not Found"
    status, headers, _ = _request(application, "/preview/", method="POST")
    assert status == "405 Method Not Allowed"
    assert headers["Allow"] == "GET, HEAD"


def test_preview_head_preserves_content_length_without_a_body(tmp_path: Path) -> None:
    preview, legacy = _write_fixture(tmp_path)
    application = PreviewApplication(preview, legacy, _api_stub)

    status, headers, body = _request(application, "/preview/", method="HEAD")

    assert status == "200 OK"
    assert int(headers["Content-Length"]) > 0
    assert body == b""


def test_replacement_root_mode_serves_preview_and_preserves_legacy(tmp_path: Path) -> None:
    preview, legacy = _write_fixture(tmp_path)
    application = PreviewApplication(preview, legacy, _api_stub, root_mode="replacement")

    root = _request(application, "/")
    asset = _request(application, "/assets/index-abc123.js")
    legacy_response = _request(application, "/legacy/")

    assert root[0] == "200 OK"
    assert b"index-abc123.js" in root[2]
    assert asset[0] == "200 OK"
    assert asset[1]["Cache-Control"].endswith("immutable")
    assert legacy_response[2] == b"<h1>Legacy</h1>\n"
