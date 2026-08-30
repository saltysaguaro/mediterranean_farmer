from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from thermal_drought.api.app import StartResponse
from thermal_drought.api.runtime import ProductionApplication, RuntimeSettings


def _settings(tmp_path: Path, **overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "request_timeout_seconds": 1.0,
        "maximum_response_bytes": 200_000,
        "maximum_concurrency": 2,
        "requests_per_minute": 100,
        "cache_directory": tmp_path / "cache",
        "maximum_cache_entries": 16,
        "cache_maximum_bytes": 1_000_000,
        "allowed_origins": ("same-origin", "https://preview.example"),
    }
    values.update(overrides)
    return RuntimeSettings(**values)  # type: ignore[arg-type]


def _stub(counter: dict[str, int], *, delay: float = 0, body_bytes: int = 0) -> Any:
    def application(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        counter["calls"] = counter.get("calls", 0) + 1
        if delay:
            time.sleep(delay)
        body = b"x" * body_bytes or json.dumps({"path": environ["PATH_INFO"]}).encode()
        start_response(
            "200 OK",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "public, max-age=31536000, immutable"),
                ("ETag", '"fixture-etag"'),
            ],
        )
        return [body]

    return application


def _request(
    application: ProductionApplication,
    path: str,
    *,
    method: str = "GET",
    query: str = "",
    origin: str = "",
    if_none_match: str = "",
    peer: str = "127.0.0.1",
    host: str = "localhost",
) -> tuple[int, dict[str, str], bytes]:
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(
        application(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "QUERY_STRING": query,
                "REMOTE_ADDR": peer,
                "HTTP_HOST": host,
                "HTTP_ORIGIN": origin,
                "HTTP_IF_NONE_MATCH": if_none_match,
            },
            start_response,
        )
    )
    return (
        int(str(captured["status"]).split()[0]),
        captured["headers"],  # type: ignore[return-value]
        body,
    )


def test_runtime_caches_supports_head_and_conditional_requests(tmp_path: Path) -> None:
    counter: dict[str, int] = {}
    application = ProductionApplication(
        _stub(counter),
        _settings(tmp_path),
        readiness=lambda: True,
    )

    first = _request(application, "/v1/tiles/version/x/y/2025/fff/0/0/0")
    second = _request(application, "/v1/tiles/version/x/y/2025/fff/0/0/0")
    head = _request(
        application,
        "/v1/tiles/version/x/y/2025/fff/0/0/0",
        method="HEAD",
    )
    conditional = _request(
        application,
        "/v1/tiles/version/x/y/2025/fff/0/0/0",
        if_none_match='"fixture-etag"',
    )

    assert first[0] == second[0] == head[0] == 200
    assert first[2] == second[2]
    assert head[2] == b""
    assert conditional[0] == 304
    assert conditional[2] == b""
    assert counter["calls"] == 1
    assert application.cache.inventory()["entries"] == 1


def test_runtime_enforces_origin_rate_timeout_and_response_limits(tmp_path: Path) -> None:
    denied = ProductionApplication(_stub({}), _settings(tmp_path), readiness=lambda: True)
    status, _, _ = _request(
        denied,
        "/v1/sample",
        origin="https://attacker.example",
    )
    assert status == 403

    limited = ProductionApplication(
        _stub({}),
        _settings(tmp_path / "rate", requests_per_minute=1),
        readiness=lambda: True,
    )
    assert _request(limited, "/v1/health", peer="198.51.100.1")[0] == 200
    assert _request(limited, "/v1/health", peer="198.51.100.1")[0] == 429

    timed = ProductionApplication(
        _stub({}, delay=0.05),
        _settings(tmp_path / "timeout", request_timeout_seconds=0.01),
        readiness=lambda: True,
    )
    assert _request(timed, "/v1/health")[0] == 504

    oversized = ProductionApplication(
        _stub({}, body_bytes=4096),
        _settings(tmp_path / "size", maximum_response_bytes=1024),
        readiness=lambda: True,
    )
    status, _, body = _request(oversized, "/v1/health")
    assert status == 507
    assert json.loads(body)["error"]["code"] == "response_too_large"


def test_runtime_health_metrics_readiness_cors_and_security_headers(tmp_path: Path) -> None:
    application = ProductionApplication(
        _stub({}),
        _settings(tmp_path),
        readiness=lambda: True,
    )

    live = _request(application, "/v1/live")
    ready = _request(application, "/v1/ready")
    cors = _request(
        application,
        "/v1/availability",
        origin="https://preview.example",
    )
    metrics = _request(application, "/v1/metrics")

    assert live[0] == ready[0] == cors[0] == metrics[0] == 200
    assert cors[1]["Access-Control-Allow-Origin"] == "https://preview.example"
    assert cors[1]["X-Content-Type-Options"] == "nosniff"
    assert json.loads(metrics[2])["privacy"].startswith("Metrics contain route classes")
