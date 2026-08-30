"""Build and verify the non-observational M1 structural scenario matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np

from thermal_drought.api.core import DataService
from thermal_drought.contracts import load_json
from thermal_drought.months import months_to_mask


@dataclass(frozen=True)
class StructuralScenario:
    """One interface case; values are synthetic and never climate evidence."""

    id: str
    interface_case: str
    spei_3: float | None
    utci_daymax_median: float | None
    spei_quality: int
    expected_spei_class: int | None
    expected_utci_class: int | None


SCENARIOS = (
    StructuralScenario("mountain", "cold × severe drought", -1.8, 5.0, 1, 0, 0),
    StructuralScenario("cool_dry", "cold × moderate drought", -1.2, 6.0, 1, 1, 0),
    StructuralScenario("cold", "cold × no drought", -0.3, 3.0, 1, 2, 0),
    StructuralScenario("southern_edge", "neutral × severe drought", -1.7, 18.0, 1, 0, 1),
    StructuralScenario("coastal", "neutral × moderate drought", -1.1, 22.0, 1, 1, 1),
    StructuralScenario("temperate", "neutral × no drought", -0.2, 20.0, 1, 2, 1),
    StructuralScenario("hot_arid", "heat × severe drought", -1.9, 34.0, 1, 0, 2),
    StructuralScenario("urban_adjacent", "heat × moderate drought", -1.3, 31.0, 1, 1, 2),
    StructuralScenario("tropical", "heat × no drought", 0.4, 32.0, 1, 2, 2),
    StructuralScenario("quality_failure", "provider-quality no data", None, 30.0, 0, None, 2),
    StructuralScenario("no_data", "both variables no data", None, None, 0, None, None),
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _xarray() -> Any:
    try:
        import xarray as xr
    except ModuleNotFoundError as error:
        raise RuntimeError("xarray is required for structural validation") from error
    return xr


def build_structural_release(
    root: Path,
    *,
    scope_path: Path,
    output_report: Path,
) -> dict[str, object]:
    """Write an ignored fixture product and its conspicuous release report."""

    scope = load_json(scope_path)
    acquisition_bbox = scope["analysis_grid"]["acquisition_bbox"]
    west, south, east, north = (float(value) for value in acquisition_bbox)
    resolution = float(scope["analysis_grid"]["resolution_degrees"])
    latitudes = np.arange(north, south - resolution / 2, -resolution, dtype=np.float64)
    longitudes = np.arange(west, east + resolution / 2, resolution, dtype=np.float64)
    shape = (12, len(latitudes), len(longitudes))
    utci = np.full(shape, np.nan, dtype=np.float32)
    spei = np.full(shape, np.nan, dtype=np.float32)
    quality = np.zeros(shape, dtype=np.uint8)
    scope_mask = np.zeros((len(latitudes), len(longitudes)), dtype=np.uint8)

    centers = [
        tuple(float(value) for value in item)
        for item in scope["analysis_grid"]["included_cell_centers"]
    ]
    if len(centers) < len(SCENARIOS):
        raise ValueError("scope does not contain enough cells for the structural scenario matrix")

    scenario_records: list[dict[str, object]] = []
    for scenario, (longitude, latitude) in zip(SCENARIOS, centers):
        row = int(np.argmin(np.abs(latitudes - latitude)))
        column = int(np.argmin(np.abs(longitudes - longitude)))
        scope_mask[row, column] = 1
        if scenario.utci_daymax_median is not None:
            utci[:, row, column] = scenario.utci_daymax_median
        if scenario.spei_3 is not None:
            spei[:, row, column] = scenario.spei_3
        quality[:, row, column] = scenario.spei_quality
        scenario_records.append(
            {
                **asdict(scenario),
                "coordinate": {"longitude": longitude, "latitude": latitude},
                "row": row,
                "column": column,
            }
        )

    times = np.asarray(
        [np.datetime64(f"2024-{month:02d}-01T00:00:00", "ns") for month in range(1, 13)]
    )
    xr = _xarray()
    dataset = xr.Dataset(
        data_vars={
            "utci_daymax_median": (("time", "latitude", "longitude"), utci),
            "spei_3": (("time", "latitude", "longitude"), spei),
            "spei_3_quality": (("time", "latitude", "longitude"), quality),
            "sicily_scope_mask": (("latitude", "longitude"), scope_mask),
        },
        coords={
            "time": ("time", times),
            "latitude": ("latitude", latitudes),
            "longitude": ("longitude", longitudes),
        },
        attrs={
            "schema_version": "1.0",
            "fixture": "true",
            "evidence_scope": (
                "DETERMINISTIC STRUCTURAL INTERFACE MATRIX — NOT CLIMATE OBSERVATIONS"
            ),
            "region_id": "structural_sicily_interface_matrix",
            "analysis_year": 2024,
            "grid_id": str(scope["analysis_grid"]["grid_id"]),
            "crs": "EPSG:4326",
        },
    )
    product = (
        root
        / "data"
        / "published"
        / "structural-interface-matrix-v1"
        / "v1"
        / "2024"
        / "structural-sicily.nc"
    )
    product.parent.mkdir(parents=True, exist_ok=True)
    temporary = product.with_suffix(".nc.tmp")
    dataset.to_netcdf(temporary, engine="h5netcdf")
    temporary.replace(product)

    report: dict[str, object] = {
        "schema_version": "1.0",
        "status": "complete",
        "fixture": True,
        "fixture_label": "DETERMINISTIC STRUCTURAL INTERFACE MATRIX — NOT CLIMATE OBSERVATIONS",
        "scope": (
            "Synthetic values placed on selected Sicily grid centers only to exercise interface "
            "states; they do not describe conditions at those coordinates."
        ),
        "source_audit_complete": False,
        "source_official_evidence": False,
        "plan_sha256": hashlib.sha256(b"structural-interface-matrix-v1").hexdigest(),
        "outputs": [
            {
                "region_id": "structural_sicily_interface_matrix",
                "path": str(product.relative_to(root)),
                "sha256": _sha256(product),
                "months": list(range(1, 13)),
                "shape": list(shape),
                "included_scope_cells": len(SCENARIOS),
            }
        ],
        "scenarios": scenario_records,
    }
    output_report.parent.mkdir(parents=True, exist_ok=True)
    temporary_report = output_report.with_suffix(output_report.suffix + ".tmp")
    temporary_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary_report.replace(output_report)
    return report


def validate_structural_release(
    root: Path,
    *,
    report_path: Path,
    manifests_root: Path,
    app_path: Path,
) -> dict[str, object]:
    """Exercise every fixture cell through point and tile production paths."""

    report = load_json(report_path)
    service = DataService.from_repository(
        root,
        manifests_root=manifests_root,
        app_path=app_path,
        report_path=report_path,
        allow_fixture=True,
    )
    mask = months_to_mask(range(1, 13))
    tile, _ = service.tile(
        service.registry.settings.dataset_version,
        ["spei_3", "utci_daymax_median"],
        2024,
        mask,
        0,
        0,
        0,
    )
    raw_tile_cells = cast(list[dict[str, object]], tile["cells"])
    tile_cells = {
        (cast(float, cell["latitude"]), cast(float, cell["longitude"])): cell
        for cell in raw_tile_cells
    }
    results: list[dict[str, object]] = []
    observed_pairs: set[tuple[int, int]] = set()
    for scenario in cast(list[dict[str, object]], report["scenarios"]):
        coordinate = cast(dict[str, object], scenario["coordinate"])
        point, _ = service.sample(
            ["spei_3", "utci_daymax_median"],
            2024,
            mask,
            cast(float, coordinate["latitude"]),
            cast(float, coordinate["longitude"]),
        )
        grid_cell = cast(dict[str, object], point["grid_cell"])
        key = (
            cast(float, grid_cell["latitude"]),
            cast(float, grid_cell["longitude"]),
        )
        matching = tile_cells[key]
        if point["variables"] != matching["variables"]:
            raise ValueError(f"{scenario['id']}: point/tile parity failed")
        variables = cast(list[dict[str, object]], point["variables"])
        classes = tuple(variable["class_index"] for variable in variables)
        expected = (scenario["expected_spei_class"], scenario["expected_utci_class"])
        if classes != expected:
            raise ValueError(f"{scenario['id']}: expected classes {expected}, received {classes}")
        if classes[0] is not None and classes[1] is not None:
            observed_pairs.add((cast(int, classes[0]), cast(int, classes[1])))
        results.append(
            {
                "id": scenario["id"],
                "interface_case": scenario["interface_case"],
                "status": point["status"],
                "classes": list(classes),
                "quality_warning": point.get("quality_warning", False),
                "point_tile_parity": True,
            }
        )
    if observed_pairs != {(x, y) for x in range(3) for y in range(3)}:
        raise ValueError("the structural matrix does not cover all nine bivariate states")
    return {
        "status": "complete",
        "fixture": True,
        "official_evidence": False,
        "fixture_label": report["fixture_label"],
        "scenario_count": len(results),
        "all_nine_bivariate_pairs": True,
        "point_tile_parity": True,
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=repository_root())
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("output/m1-structural/fixture-release.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repository_root.resolve()
    report_path = args.report if args.report.is_absolute() else root / args.report
    try:
        build_structural_release(
            root,
            scope_path=root / "config" / "scope.json",
            output_report=report_path,
        )
        result = validate_structural_release(
            root,
            report_path=report_path,
            manifests_root=root / "config" / "variables",
            app_path=root / "config" / "app.json",
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
