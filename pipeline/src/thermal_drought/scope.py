"""Validated Sicily product-scope configuration and provider-grid membership."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SicilyScope:
    scope_id: str
    name: str
    grid_id: str
    resolution_degrees: float
    acquisition_bbox: tuple[float, float, float, float]
    included_cell_centers: frozenset[tuple[float, float]]
    map_bounds: tuple[float, float, float, float]
    initial_center: tuple[float, float]
    initial_zoom: float
    minimum_zoom: float
    maximum_zoom: float
    boundary_archive_sha256: str
    boundary_dataset_url: str
    boundary_license: str
    boundary_license_url: str

    def includes(self, longitude: float, latitude: float) -> bool:
        """Return whether an exact provider-grid cell center belongs to Sicilia."""

        precision = 10
        return (
            round(longitude, precision),
            round(latitude, precision),
        ) in self.included_cell_centers


def _number_tuple(value: Any, length: int, label: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must contain {length} numbers")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise ValueError(f"{label} must contain only numbers")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{label} must contain only finite numbers")
    return result


def _aligned(value: float, origin: float, resolution: float) -> bool:
    return math.isclose((value - origin) / resolution, round((value - origin) / resolution))


def load_scope(path: Path = Path("config/scope.json")) -> SicilyScope:
    """Load and strictly validate the checked-in Sicily scope contract."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: scope configuration cannot be read: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: scope configuration must be an object")
    if payload.get("scope_id") != "sicily_istat_2026_grid_centers":
        raise ValueError(f"{path}: unsupported or missing scope_id")
    analysis_grid = payload.get("analysis_grid")
    map_config = payload.get("map")
    boundary = payload.get("boundary_source")
    if not isinstance(analysis_grid, dict) or not isinstance(map_config, dict):
        raise ValueError(f"{path}: analysis_grid and map must be objects")
    if not isinstance(boundary, dict):
        raise ValueError(f"{path}: boundary_source must be an object")

    bbox = _number_tuple(analysis_grid.get("acquisition_bbox"), 4, "acquisition_bbox")
    west, south, east, north = bbox
    if not -180 <= west < east <= 180 or not -90 <= south < north <= 90:
        raise ValueError(f"{path}: acquisition_bbox is not ordered")
    resolution = float(analysis_grid.get("resolution_degrees", 0))
    if resolution <= 0 or not math.isfinite(resolution):
        raise ValueError(f"{path}: resolution_degrees must be positive")
    raw_centers = analysis_grid.get("included_cell_centers")
    if not isinstance(raw_centers, list) or not raw_centers:
        raise ValueError(f"{path}: included_cell_centers must be a non-empty array")
    centers = [_number_tuple(value, 2, "included_cell_center") for value in raw_centers]
    if len(set(centers)) != len(centers):
        raise ValueError(f"{path}: included_cell_centers contains duplicates")
    for longitude, latitude in centers:
        if not west <= longitude <= east or not south <= latitude <= north:
            raise ValueError(f"{path}: included cell center lies outside acquisition_bbox")
        if not _aligned(longitude, west, resolution) or not _aligned(latitude, south, resolution):
            raise ValueError(f"{path}: included cell center is not provider-grid aligned")

    map_bounds = _number_tuple(map_config.get("bounds"), 4, "map.bounds")
    initial_center = _number_tuple(map_config.get("initial_center"), 2, "map.initial_center")
    if not map_bounds[0] < map_bounds[2] or not map_bounds[1] < map_bounds[3]:
        raise ValueError(f"{path}: map.bounds is not ordered")
    if not (
        map_bounds[0] <= initial_center[0] <= map_bounds[2]
        and map_bounds[1] <= initial_center[1] <= map_bounds[3]
    ):
        raise ValueError(f"{path}: map.initial_center lies outside map.bounds")
    archive_sha256 = boundary.get("archive_sha256")
    if not isinstance(archive_sha256, str) or len(archive_sha256) != 64:
        raise ValueError(f"{path}: boundary archive SHA-256 is invalid")
    dataset_url = boundary.get("dataset_url")
    license_name = boundary.get("license")
    license_url = boundary.get("license_url")
    if not isinstance(dataset_url, str) or not dataset_url.startswith("https://"):
        raise ValueError(f"{path}: boundary dataset_url must use https")
    if not isinstance(license_name, str) or not license_name:
        raise ValueError(f"{path}: boundary license is missing")
    if not isinstance(license_url, str) or not license_url.startswith("https://"):
        raise ValueError(f"{path}: boundary license_url must use https")

    initial_zoom = _number_tuple([map_config.get("initial_zoom")], 1, "map.initial_zoom")[0]
    minimum_zoom = _number_tuple([map_config.get("minimum_zoom")], 1, "map.minimum_zoom")[0]
    maximum_zoom = _number_tuple([map_config.get("maximum_zoom")], 1, "map.maximum_zoom")[0]
    if not 0 <= minimum_zoom <= initial_zoom <= maximum_zoom <= 24:
        raise ValueError(f"{path}: map zoom values are not ordered")

    return SicilyScope(
        scope_id=str(payload["scope_id"]),
        name=str(payload.get("name", "Sicilia")),
        grid_id=str(analysis_grid.get("grid_id")),
        resolution_degrees=resolution,
        acquisition_bbox=(west, south, east, north),
        included_cell_centers=frozenset((round(lon, 10), round(lat, 10)) for lon, lat in centers),
        map_bounds=(map_bounds[0], map_bounds[1], map_bounds[2], map_bounds[3]),
        initial_center=(initial_center[0], initial_center[1]),
        initial_zoom=initial_zoom,
        minimum_zoom=minimum_zoom,
        maximum_zoom=maximum_zoom,
        boundary_archive_sha256=archive_sha256,
        boundary_dataset_url=dataset_url,
        boundary_license=license_name,
        boundary_license_url=license_url,
    )
