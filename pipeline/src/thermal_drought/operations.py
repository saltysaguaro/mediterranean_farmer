"""Exercise production release, cache, performance, security, and rollback gates."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import tempfile
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from thermal_drought.api.app import create_app
from thermal_drought.api.core import DataService
from thermal_drought.api.runtime import (
    ProductionApplication,
    RuntimeSettings,
    create_production_app,
)
from thermal_drought.months import ALL_MONTHS_MASK, mask_to_hex, months_to_mask
from thermal_drought.release_bundle import (
    ReleasePointer,
    ReleaseStore,
    build_bundle,
    repository_root,
)
from thermal_drought.scope import load_scope

STANDARD_MASKS = tuple(1 << index for index in range(12)) + (
    months_to_mask((12, 1, 2)),
    months_to_mask((3, 4, 5)),
    months_to_mask((6, 7, 8)),
    months_to_mask((9, 10, 11)),
    ALL_MONTHS_MASK,
)
TILE_P95_BUDGET_MS = 2_000.0
WARM_TILE_P95_BUDGET_MS = 500.0
MAXIMUM_TILE_BYTES = 200_000
WARM_POINT_P95_BUDGET_MS = 500.0


def _request(
    application: ProductionApplication,
    path: str,
    *,
    method: str = "GET",
    query: str = "",
    origin: str = "",
    peer: str = "127.0.0.1",
) -> tuple[int, dict[str, str], bytes, float]:
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    started = time.perf_counter()
    body = b"".join(
        application(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "QUERY_STRING": query,
                "REMOTE_ADDR": peer,
                "HTTP_HOST": "localhost",
                "HTTP_ORIGIN": origin,
            },
            start_response,
        )
    )
    elapsed_ms = (time.perf_counter() - started) * 1_000
    return (
        int(str(captured["status"]).split()[0]),
        captured["headers"],  # type: ignore[return-value]
        body,
        elapsed_ms,
    )


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _web_mercator_tile(longitude: float, latitude: float, zoom: int) -> tuple[int, int]:
    scale = 1 << zoom
    tile_x = int((longitude + 180.0) / 360.0 * scale)
    bounded_latitude = max(-85.05112878, min(85.05112878, latitude))
    latitude_radians = math.radians(bounded_latitude)
    tile_y = int((1.0 - math.asinh(math.tan(latitude_radians)) / math.pi) / 2.0 * scale)
    return min(scale - 1, max(0, tile_x)), min(scale - 1, max(0, tile_y))


def _tile_paths(service: DataService) -> tuple[str, ...]:
    scope = load_scope(repository_root() / "config/scope.json")
    version = service.registry.settings.dataset_version
    years = sorted({product.year for product in service.release.products})
    paths: list[str] = []
    for year in years:
        for mask in STANDARD_MASKS:
            for zoom in range(5):
                coordinates = {
                    _web_mercator_tile(longitude, latitude, zoom)
                    for longitude, latitude in scope.included_cell_centers
                }
                for tile_x, tile_y in sorted(coordinates):
                    paths.append(
                        f"/v1/tiles/{version}/spei_3/utci_daymax_median/"
                        f"{year}/{mask_to_hex(mask)}/{zoom}/{tile_x}/{tile_y}"
                    )
    return tuple(paths)


def prewarm(application: ProductionApplication, service: DataService) -> dict[str, object]:
    paths = _tile_paths(service)
    latencies: list[float] = []
    response_bytes = 0
    for path in paths:
        status, _, body, latency = _request(application, path, peer="127.0.0.2")
        if status != 200:
            raise RuntimeError(f"cache prewarm failed with HTTP {status}: {path}")
        latencies.append(latency)
        response_bytes += len(body)
    return {
        "status": "complete",
        "mask_count": len(STANDARD_MASKS),
        "masks": [mask_to_hex(mask) for mask in STANDARD_MASKS],
        "year_count": len({product.year for product in service.release.products}),
        "zoom_levels": [0, 1, 2, 3, 4],
        "request_count": len(paths),
        "response_bytes": response_bytes,
        "p95_ms": round(_percentile(latencies, 0.95), 3),
        "cache": application.cache.inventory(),
    }


def _benchmark_application(root: Path, cache_directory: Path) -> ProductionApplication:
    service = DataService.from_repository(root)
    settings = RuntimeSettings.load(root / "config/app.json", root)
    settings = replace(
        settings,
        cache_directory=cache_directory,
        requests_per_minute=10_000,
    )
    return create_production_app(create_app(service), settings, readiness=lambda: True)


def benchmark(root: Path) -> dict[str, object]:
    service = DataService.from_repository(root)
    year = max(product.year for product in service.release.products)
    version = service.registry.settings.dataset_version
    path = f"/v1/tiles/{version}/spei_3/utci_daymax_median/{year}/fff/0/0/0"
    point_query = f"x=spei_3&y=utci_daymax_median&year={year}&months=fff&lng=13.75&lat=37.5"
    benchmark_parent = repository_root() / "output"
    benchmark_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="m4-benchmark-", dir=benchmark_parent) as tmp:
        application = _benchmark_application(root, Path(tmp) / "cache")
        cold_samples: list[float] = []
        warm_samples: list[float] = []
        point_samples: list[float] = []
        sizes: list[int] = []
        for index in range(20):
            fresh = _benchmark_application(root, Path(tmp) / f"cold-{index}")
            status, _, body, latency = _request(fresh, path, peer=f"198.51.100.{index + 1}")
            if status != 200:
                raise RuntimeError(f"cold benchmark failed with HTTP {status}")
            cold_samples.append(latency)
            sizes.append(len(body))
        status, _, body, _ = _request(application, path)
        if status != 200:
            raise RuntimeError(f"warm benchmark seed failed with HTTP {status}")
        for _ in range(40):
            status, _, body, latency = _request(application, path)
            if status != 200:
                raise RuntimeError(f"warm benchmark failed with HTTP {status}")
            warm_samples.append(latency)
            sizes.append(len(body))
        status, _, _, _ = _request(application, "/v1/sample", query=point_query)
        if status != 200:
            raise RuntimeError(f"point benchmark seed failed with HTTP {status}")
        for _ in range(40):
            status, _, _, latency = _request(
                application,
                "/v1/sample",
                query=point_query,
            )
            if status != 200:
                raise RuntimeError(f"point benchmark failed with HTTP {status}")
            point_samples.append(latency)
    cold_p95 = _percentile(cold_samples, 0.95)
    warm_p95 = _percentile(warm_samples, 0.95)
    point_p95 = _percentile(point_samples, 0.95)
    maximum_bytes = max(sizes)
    return {
        "status": "complete",
        "cold_samples": len(cold_samples),
        "warm_samples": len(warm_samples),
        "warm_point_samples": len(point_samples),
        "cold_p50_ms": round(statistics.median(cold_samples), 3),
        "cold_p95_ms": round(cold_p95, 3),
        "warm_p50_ms": round(statistics.median(warm_samples), 3),
        "warm_p95_ms": round(warm_p95, 3),
        "warm_point_p50_ms": round(statistics.median(point_samples), 3),
        "warm_point_p95_ms": round(point_p95, 3),
        "maximum_response_bytes": maximum_bytes,
        "budgets": {
            "cold_p95_ms": TILE_P95_BUDGET_MS,
            "warm_p95_ms": WARM_TILE_P95_BUDGET_MS,
            "warm_point_p95_ms": WARM_POINT_P95_BUDGET_MS,
            "maximum_response_bytes": MAXIMUM_TILE_BYTES,
        },
        "passed": (
            cold_p95 <= TILE_P95_BUDGET_MS
            and warm_p95 <= WARM_TILE_P95_BUDGET_MS
            and point_p95 <= WARM_POINT_P95_BUDGET_MS
            and maximum_bytes <= MAXIMUM_TILE_BYTES
        ),
    }


def parity_and_distributions(service: DataService) -> dict[str, object]:
    scope = load_scope(repository_root() / "config/scope.json")
    years = sorted({product.year for product in service.release.products})
    distributions: dict[str, dict[str, int]] = {}
    comparisons = 0
    for year in years:
        tile, _ = service.tile(
            service.registry.settings.dataset_version,
            ("spei_3", "utci_daymax_median"),
            year,
            ALL_MONTHS_MASK,
            0,
            0,
            0,
        )
        cells = tile["cells"]
        if not isinstance(cells, list):
            raise RuntimeError("tile response cells are invalid")
        counts: Counter[str] = Counter()
        for cell in cells:
            if not isinstance(cell, Mapping):
                raise RuntimeError("tile response cell is invalid")
            variables = cell["variables"]
            if not isinstance(variables, list):
                raise RuntimeError("tile variables are invalid")
            point, _ = service.sample(
                ("spei_3", "utci_daymax_median"),
                year,
                ALL_MONTHS_MASK,
                float(cell["latitude"]),
                float(cell["longitude"]),
            )
            if point["variables"] != variables:
                raise RuntimeError("tile and point values diverged")
            labels = [str(item.get("class_label")) for item in variables if isinstance(item, dict)]
            counts[" × ".join(labels)] += 1
            comparisons += 1
        if len(cells) != len(scope.included_cell_centers):
            raise RuntimeError("tile response did not cover the full Sicily scope")
        distributions[str(year)] = dict(sorted(counts.items()))
    return {
        "status": "complete",
        "comparisons": comparisons,
        "scope_cells_per_year": len(scope.included_cell_centers),
        "all_year_class_distributions": distributions,
    }


def security_probes(application: ProductionApplication, version: str) -> dict[str, object]:
    probes = {
        "method": _request(application, "/v1/health", method="POST")[0],
        "origin": _request(
            application,
            "/v1/health",
            origin="https://attacker.invalid",
        )[0],
        "invalid_mask": _request(
            application,
            f"/v1/tiles/{version}/spei_3/utci_daymax_median/2025/000/0/0/0",
        )[0],
        "invalid_zoom": _request(
            application,
            f"/v1/tiles/{version}/spei_3/utci_daymax_median/2025/fff/99/0/0",
        )[0],
        "unknown_dataset": _request(
            application,
            "/v1/tiles/unknown/spei_3/utci_daymax_median/2025/fff/0/0/0",
        )[0],
    }
    expected = {
        "method": 405,
        "origin": 403,
        "invalid_mask": 400,
        "invalid_zoom": 400,
        "unknown_dataset": 404,
    }
    return {"status": "complete", "probes": probes, "passed": probes == expected}


def rollback_rehearsal(store: ReleaseStore) -> dict[str, object]:
    before = store.pointer()
    if before is None:
        raise RuntimeError("rollback rehearsal requires a promoted release")
    rehearsal_id = f"rollback-rehearsal-{before.current[:16]}"
    rehearsal_root = store.releases / rehearsal_id
    if not rehearsal_root.is_dir():
        shutil.copytree(store.current_root(), rehearsal_root)
    store.promote(rehearsal_id)
    rolled_back = store.rollback()
    if rolled_back.current != before.current:
        raise RuntimeError("rollback did not restore the starting release")
    restored = ReleasePointer(before.current, before.previous, before.promoted_at)
    store._write_pointer(restored)
    return {
        "status": "complete",
        "starting_release": before.current,
        "rehearsal_release": rehearsal_id,
        "rolled_back_to": rolled_back.current,
        "releases_retained": sorted(
            path.name for path in store.releases.iterdir() if path.is_dir()
        ),
    }


def complete_runtime_gate(root: Path, report_path: Path) -> dict[str, object]:
    root = root.resolve()
    output = root / "output/m4-runtime/sicily-2024-2025-v1.zip"
    bundle = build_bundle(root, output)
    store = ReleaseStore(root / "output/m4-runtime/release-store")
    digest = str(bundle["bundle_sha256"])
    installed = store.install(output.as_uri(), digest)
    store.promote(digest)
    service = DataService.from_repository(installed)
    settings = RuntimeSettings.load(installed / "config/app.json", installed)
    settings = replace(
        settings,
        cache_directory=root / f"output/m4-runtime/cache/{digest}",
        requests_per_minute=10_000,
    )
    application = create_production_app(create_app(service), settings, readiness=lambda: True)
    warming = prewarm(application, service)
    performance = benchmark(installed)
    parity = parity_and_distributions(service)
    security = security_probes(application, service.registry.settings.dataset_version)
    rollback = rollback_rehearsal(store)
    metrics_status, _, metrics_body, _ = _request(application, "/v1/metrics")
    if metrics_status != 200:
        raise RuntimeError("metrics endpoint failed")
    passed = bool(performance["passed"] and security["passed"])
    report: dict[str, object] = {
        "status": "complete" if passed else "blocked",
        "schema_version": "1.0",
        "milestone": "M4-production-service",
        "official_evidence": True,
        "dataset_version": service.registry.settings.dataset_version,
        "bundle": bundle,
        "installed_release": digest,
        "runtime_limits": RuntimeSettings.load(
            installed / "config/app.json", installed
        ).public_metadata(),
        "prewarm": warming,
        "performance": performance,
        "parity": parity,
        "security": security,
        "rollback": rollback,
        "metrics": json.loads(metrics_body),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=repository_root())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("pipeline/reports/m4-production-runtime.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repository_root.resolve()
    report_path = args.report if args.report.is_absolute() else root / args.report
    try:
        report = complete_runtime_gate(root, report_path)
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}, indent=2))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
