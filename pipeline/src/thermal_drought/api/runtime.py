"""Production WSGI controls around the framework-neutral climate service."""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from thermal_drought.api.app import StartResponse, WsgiApplication
from thermal_drought.contracts import load_json


@dataclass(frozen=True)
class RuntimeSettings:
    """Bounded, deployment-visible controls for the production adapter."""

    request_timeout_seconds: float
    maximum_response_bytes: int
    maximum_concurrency: int
    requests_per_minute: int
    cache_directory: Path
    maximum_cache_entries: int
    cache_maximum_bytes: int
    allowed_origins: tuple[str, ...]

    @classmethod
    def load(cls, app_path: Path, repository_root: Path) -> RuntimeSettings:
        app = load_json(app_path)
        raw = app.get("service", {}).get("runtime")
        if not isinstance(raw, dict):
            raise ValueError(f"{app_path}: service runtime settings are missing")
        allowed = raw.get("allowed_origins")
        if not isinstance(allowed, list) or not allowed:
            raise ValueError(f"{app_path}: at least one allowed origin is required")
        cache_directory = (repository_root / str(raw["cache_directory"])).resolve()
        settings = cls(
            request_timeout_seconds=float(raw["request_timeout_seconds"]),
            maximum_response_bytes=int(raw["maximum_response_bytes"]),
            maximum_concurrency=int(raw["maximum_concurrency"]),
            requests_per_minute=int(raw["requests_per_minute"]),
            cache_directory=cache_directory,
            maximum_cache_entries=int(raw["maximum_cache_entries"]),
            cache_maximum_bytes=int(raw["cache_maximum_bytes"]),
            allowed_origins=tuple(str(value) for value in allowed),
        )
        if not 0.05 <= settings.request_timeout_seconds <= 30:
            raise ValueError("request timeout must be between 0.05 and 30 seconds")
        if not 1024 <= settings.maximum_response_bytes <= 1024 * 1024:
            raise ValueError("maximum response size must be between 1 KiB and 1 MiB")
        if not 1 <= settings.maximum_concurrency <= 64:
            raise ValueError("maximum concurrency must be between 1 and 64")
        if not 1 <= settings.requests_per_minute <= 10000:
            raise ValueError("requests per minute must be between 1 and 10000")
        if not 1 <= settings.maximum_cache_entries <= 10000:
            raise ValueError("maximum cache entries must be between 1 and 10000")
        if not 1024 <= settings.cache_maximum_bytes <= 2 * 1024 * 1024 * 1024:
            raise ValueError("cache byte limit must be between 1 KiB and 2 GiB")
        return settings

    def public_metadata(self) -> dict[str, object]:
        return {
            "request_timeout_seconds": self.request_timeout_seconds,
            "maximum_response_bytes": self.maximum_response_bytes,
            "maximum_concurrency": self.maximum_concurrency,
            "requests_per_minute": self.requests_per_minute,
            "maximum_cache_entries": self.maximum_cache_entries,
            "cache_maximum_bytes": self.cache_maximum_bytes,
            "allowed_origins": list(self.allowed_origins),
        }


@dataclass(frozen=True)
class CapturedResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


class FileResponseCache:
    """Small atomic on-disk cache for immutable and short-lived JSON responses."""

    def __init__(self, root: Path, maximum_entries: int, maximum_bytes: int) -> None:
        self.root = root
        self.maximum_entries = maximum_entries
        self.maximum_bytes = maximum_bytes
        self._lock = threading.Lock()

    @staticmethod
    def identity(path: str, query: str) -> str:
        return hashlib.sha256(f"{path}?{query}".encode()).hexdigest()

    def get(self, identity: str) -> CapturedResponse | None:
        metadata_path = self.root / f"{identity}.json"
        body_path = self.root / f"{identity}.body"
        with self._lock:
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                body = body_path.read_bytes()
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                return None
            expires_at = metadata.get("expires_at")
            if expires_at is not None and float(expires_at) < time.time():
                return None
            if hashlib.sha256(body).hexdigest() != metadata.get("body_sha256"):
                return None
            try:
                status = int(metadata["status"])
                headers = tuple((str(key), str(value)) for key, value in metadata["headers"])
            except (KeyError, TypeError, ValueError):
                return None
            now = time.time()
            try:
                os.utime(metadata_path, (now, now))
                os.utime(body_path, (now, now))
            except OSError:
                pass
            return CapturedResponse(status=status, headers=headers, body=body)

    def put(self, identity: str, response: CapturedResponse, ttl_seconds: int | None) -> None:
        if len(response.body) > self.maximum_bytes:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        metadata_path = self.root / f"{identity}.json"
        body_path = self.root / f"{identity}.body"
        metadata = {
            "schema_version": "1.0",
            "status": response.status,
            "headers": list(response.headers),
            "body_sha256": hashlib.sha256(response.body).hexdigest(),
            "expires_at": None if ttl_seconds is None else time.time() + ttl_seconds,
        }
        with self._lock:
            temporary_body = body_path.with_suffix(".body.tmp")
            temporary_metadata = metadata_path.with_suffix(".json.tmp")
            temporary_body.write_bytes(response.body)
            temporary_metadata.write_text(
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary_body.replace(body_path)
            temporary_metadata.replace(metadata_path)
            self._prune()

    def inventory(self) -> dict[str, int]:
        if not self.root.is_dir():
            return {"entries": 0, "bytes": 0}
        bodies = list(self.root.glob("*.body"))
        return {
            "entries": len(bodies),
            "bytes": sum(path.stat().st_size for path in bodies if path.is_file()),
        }

    def _prune(self) -> None:
        bodies = sorted(
            (path for path in self.root.glob("*.body") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
        )
        total = sum(path.stat().st_size for path in bodies)
        while bodies and (len(bodies) > self.maximum_entries or total > self.maximum_bytes):
            body = bodies.pop(0)
            size = body.stat().st_size
            metadata = body.with_suffix(".json")
            try:
                body.unlink()
            except FileNotFoundError:
                pass
            try:
                metadata.unlink()
            except FileNotFoundError:
                pass
            total -= size


class SlidingWindowRateLimiter:
    """Bound memory and requests per anonymous network peer."""

    def __init__(self, requests_per_minute: int, maximum_peers: int = 4096) -> None:
        self.requests_per_minute = requests_per_minute
        self.maximum_peers = maximum_peers
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, peer: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            if peer not in self._requests and len(self._requests) >= self.maximum_peers:
                oldest_peer = min(
                    self._requests,
                    key=lambda key: self._requests[key][-1] if self._requests[key] else -math.inf,
                )
                del self._requests[oldest_peer]
            window = self._requests[peer]
            while window and current - window[0] >= 60:
                window.popleft()
            if len(window) >= self.requests_per_minute:
                return False
            window.append(current)
            return True


class RuntimeMetrics:
    """Privacy-safe process metrics with bounded latency history."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self._counts: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=2048))
        self._lock = threading.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[name] += amount

    def observe(self, route: str, milliseconds: float) -> None:
        with self._lock:
            self._latencies[route].append(milliseconds)

    def snapshot(self, cache: Mapping[str, int]) -> dict[str, object]:
        with self._lock:
            counts = dict(sorted(self._counts.items()))
            latencies = {
                route: _latency_summary(values) for route, values in sorted(self._latencies.items())
            }
        return {
            "status": "ok",
            "schema_version": "1.0",
            "uptime_seconds": round(time.monotonic() - self.started, 3),
            "counts": counts,
            "latency_ms": latencies,
            "cache": dict(cache),
            "privacy": (
                "Metrics contain route classes and timings only; coordinates are not recorded."
            ),
        }


def _latency_summary(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "maximum": 0.0}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "p50": round(ordered[max(0, math.ceil(len(ordered) * 0.50) - 1)], 3),
        "p95": round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 3),
        "maximum": round(ordered[-1], 3),
    }


def _route_class(path: str) -> str:
    if path.startswith("/v1/tiles/"):
        return "/v1/tiles"
    if path in {"/v1/sample", "/v1/availability", "/v1/health"}:
        return path
    return "other"


def _capture(application: WsgiApplication, environ: dict[str, Any]) -> CapturedResponse:
    captured_status: int | None = None
    captured_headers: tuple[tuple[str, str], ...] | None = None

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        nonlocal captured_headers, captured_status
        captured_status = int(status.split()[0])
        captured_headers = tuple(headers)

    body = b"".join(application(environ, start_response))
    if captured_status is None or captured_headers is None:
        raise RuntimeError("application did not start a response")
    return CapturedResponse(status=captured_status, headers=captured_headers, body=body)


def _json_response(status: int, code: str, detail: str) -> CapturedResponse:
    body = (
        json.dumps(
            {"status": "error", "error": {"code": code, "detail": detail}},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        + b"\n"
    )
    return CapturedResponse(
        status=status,
        headers=(("Content-Type", "application/json; charset=utf-8"),),
        body=body,
    )


class ProductionApplication:
    """Enforce production limits, caching, CORS, metrics, and conditional requests."""

    def __init__(
        self,
        application: WsgiApplication,
        settings: RuntimeSettings,
        *,
        readiness: Callable[[], bool],
    ) -> None:
        self.application = application
        self.settings = settings
        self.readiness = readiness
        self.cache = FileResponseCache(
            settings.cache_directory,
            settings.maximum_cache_entries,
            settings.cache_maximum_bytes,
        )
        self.rate_limiter = SlidingWindowRateLimiter(settings.requests_per_minute)
        self.metrics = RuntimeMetrics()
        self.executor = ThreadPoolExecutor(
            max_workers=settings.maximum_concurrency,
            thread_name_prefix="climate-api",
        )
        self.capacity = threading.BoundedSemaphore(settings.maximum_concurrency)

    def __call__(
        self,
        environ: dict[str, Any],
        start_response: StartResponse,
    ) -> Iterable[bytes]:
        started = time.perf_counter()
        path = str(environ.get("PATH_INFO", ""))
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        route = _route_class(path)

        if path == "/v1/live":
            response = _plain_json(200, {"status": "ok", "live": True})
            return self._serve(response, environ, start_response, method=method)
        if path == "/v1/ready":
            ready = self.readiness()
            response = _plain_json(
                200 if ready else 503,
                {"status": "ok" if ready else "unavailable", "ready": ready},
            )
            return self._serve(response, environ, start_response, method=method)
        if path == "/v1/metrics":
            response = _plain_json(200, self.metrics.snapshot(self.cache.inventory()))
            return self._serve(response, environ, start_response, method=method)

        origin_error = self._origin_error(environ)
        if origin_error is not None:
            self.metrics.increment("cors_rejected_total")
            return self._serve(origin_error, environ, start_response, method=method)
        if method == "OPTIONS":
            response = CapturedResponse(status=204, headers=(), body=b"")
            return self._serve(response, environ, start_response, method=method)
        if method not in {"GET", "HEAD"}:
            response = _json_response(405, "method_not_allowed", "only GET and HEAD are supported")
            return self._serve(response, environ, start_response, method=method)

        peer = str(environ.get("REMOTE_ADDR", "unknown"))[:128]
        if not self.rate_limiter.allow(peer):
            self.metrics.increment("rate_limited_total")
            response = _json_response(429, "rate_limited", "request rate limit exceeded")
            return self._serve(
                response,
                environ,
                start_response,
                method=method,
                extra_headers=(("Retry-After", "60"),),
            )

        query = str(environ.get("QUERY_STRING", ""))
        cache_identity = self.cache.identity(path, query)
        cacheable = (
            path == "/v1/availability" or path == "/v1/sample" or path.startswith("/v1/tiles/")
        )
        if cacheable:
            cached = self.cache.get(cache_identity)
            if cached is not None:
                self.metrics.increment("cache_hit_total")
                self.metrics.increment("requests_total")
                self.metrics.observe(route, (time.perf_counter() - started) * 1000)
                return self._serve(cached, environ, start_response, method=method)
            self.metrics.increment("cache_miss_total")

        if not self.capacity.acquire(blocking=False):
            self.metrics.increment("concurrency_rejected_total")
            response = _json_response(503, "busy", "service concurrency limit reached")
            return self._serve(
                response,
                environ,
                start_response,
                method=method,
                extra_headers=(("Retry-After", "1"),),
            )

        forwarded = dict(environ)
        forwarded["REQUEST_METHOD"] = "GET"
        future = self.executor.submit(_capture, self.application, forwarded)
        future.add_done_callback(lambda _: self.capacity.release())
        try:
            response = future.result(timeout=self.settings.request_timeout_seconds)
        except FutureTimeoutError:
            self.metrics.increment("timeout_total")
            response = _json_response(504, "request_timeout", "request exceeded the runtime limit")
        except Exception:
            self.metrics.increment("internal_error_total")
            response = _json_response(500, "internal_error", "request failed safely")

        if len(response.body) > self.settings.maximum_response_bytes:
            self.metrics.increment("response_limit_total")
            response = _json_response(
                507,
                "response_too_large",
                "response exceeds the configured byte limit",
            )
        if cacheable and response.status == 200:
            ttl = None if path.startswith("/v1/tiles/") else 300
            self.cache.put(cache_identity, response, ttl)

        elapsed = (time.perf_counter() - started) * 1000
        self.metrics.increment("requests_total")
        self.metrics.increment(f"status_{response.status}_total")
        self.metrics.increment("response_bytes_total", len(response.body))
        self.metrics.observe(route, elapsed)
        return self._serve(response, environ, start_response, method=method)

    def _origin_error(self, environ: Mapping[str, Any]) -> CapturedResponse | None:
        origin = str(environ.get("HTTP_ORIGIN", ""))
        if not origin:
            return None
        if origin in self.settings.allowed_origins:
            return None
        if "same-origin" in self.settings.allowed_origins:
            origin_host = urlsplit(origin).netloc
            request_host = str(environ.get("HTTP_HOST", ""))
            if origin_host and origin_host == request_host:
                return None
        return _json_response(403, "origin_not_allowed", "request origin is not allowed")

    def _serve(
        self,
        response: CapturedResponse,
        environ: Mapping[str, Any],
        start_response: StartResponse,
        *,
        method: str,
        extra_headers: Sequence[tuple[str, str]] = (),
    ) -> Iterable[bytes]:
        headers = {
            key: value
            for key, value in response.headers
            if key.lower() not in {"content-length", "access-control-allow-origin"}
        }
        etag = headers.get("ETag")
        if etag is not None and str(environ.get("HTTP_IF_NONE_MATCH", "")) == etag:
            response = CapturedResponse(status=304, headers=tuple(headers.items()), body=b"")
        origin = str(environ.get("HTTP_ORIGIN", ""))
        if origin and self._origin_error(environ) is None:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"
        if method == "OPTIONS":
            headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
            headers["Access-Control-Allow-Headers"] = "Accept, If-None-Match"
            headers["Access-Control-Max-Age"] = "600"
        headers.update(
            {
                "Content-Length": str(len(response.body)),
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
                "Cross-Origin-Resource-Policy": "same-site",
            }
        )
        headers.update(dict(extra_headers))
        start_response(
            f"{response.status} {HTTPStatus(response.status).phrase}",
            list(headers.items()),
        )
        return [] if method == "HEAD" or response.status in {204, 304} else [response.body]


def _plain_json(status: int, payload: Mapping[str, object]) -> CapturedResponse:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    return CapturedResponse(
        status=status,
        headers=(
            ("Content-Type", "application/json; charset=utf-8"),
            ("Cache-Control", "no-store"),
        ),
        body=body,
    )


def create_production_app(
    application: WsgiApplication,
    settings: RuntimeSettings,
    *,
    readiness: Callable[[], bool],
) -> ProductionApplication:
    return ProductionApplication(application, settings, readiness=readiness)
