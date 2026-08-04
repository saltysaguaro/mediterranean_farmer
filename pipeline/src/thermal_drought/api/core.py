"""Shared aggregation core for point samples and bounded development tiles."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from thermal_drought import __version__
from thermal_drought.acquire.runner import sha256_file
from thermal_drought.aggregation import median_for_month_mask
from thermal_drought.classification import ClassArray, FixedClassification
from thermal_drought.contracts import load_json, validate_targets
from thermal_drought.months import mask_to_hex, mask_to_months, validate_mask

FloatArray = NDArray[np.float64]
CountArray = NDArray[np.int64]


class ServiceError(ValueError):
    """A stable, user-safe service validation or release error."""

    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail

    def response(self) -> dict[str, object]:
        return {
            "status": "error",
            "error": {
                "code": self.code,
                "detail": self.detail,
            },
        }


@dataclass(frozen=True)
class ServiceSettings:
    api_version: str
    dataset_version: str
    palette_version: str
    maximum_active_variables: int
    maximum_zoom: int
    maximum_product_files: int
    maximum_development_cells_per_product: int
    release_report: str


@dataclass(frozen=True)
class VariableSpec:
    id: str
    label: str
    unit: str
    grid_id: str
    calendar: str
    resolution_degrees: float
    coverage_bbox: tuple[float, float, float, float]
    coverage_months: tuple[int, ...]
    statistic: str
    minimum_valid_fraction: float
    classification: FixedClassification
    quality_policy: str
    quality_field: str | None
    quality_pass_values: tuple[int, ...]
    data_version: str
    published_years: tuple[int, ...]
    sample_retrieved_at: str | None
    source: Mapping[str, Any]

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, Any]) -> VariableSpec:
        coverage = manifest["coverage"]
        aggregation = manifest["aggregation"]
        quality = manifest["quality"]
        publication = manifest["publication"]
        field = quality["field"]
        bbox = tuple(float(value) for value in coverage["bbox"])
        if len(bbox) != 4:
            raise ValueError("coverage bbox must contain four values")
        return cls(
            id=str(manifest["id"]),
            label=str(manifest["label"]),
            unit=str(manifest["unit"]),
            grid_id=str(manifest["grid_id"]),
            calendar=str(coverage["calendar"]),
            resolution_degrees=float(coverage["resolution_degrees"]),
            coverage_bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
            coverage_months=tuple(int(value) for value in coverage["months"]),
            statistic=str(aggregation["default"]),
            minimum_valid_fraction=float(aggregation["minimum_valid_fraction"]),
            classification=FixedClassification.from_manifest(manifest),
            quality_policy=str(quality["policy"]),
            quality_field=None if field is None else str(field),
            quality_pass_values=tuple(int(value) for value in quality["pass_values"]),
            data_version=str(publication["data_version"]),
            published_years=tuple(int(value) for value in publication["published_years"]),
            sample_retrieved_at=(
                None
                if publication["sample_retrieved_at"] is None
                else str(publication["sample_retrieved_at"])
            ),
            source=manifest["source"],
        )

    def public_metadata(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "unit": self.unit,
            "grid_id": self.grid_id,
            "statistic": self.statistic,
            "minimum_valid_fraction": self.minimum_valid_fraction,
            "classification": self.classification.cache_signature(),
            "quality_policy": self.quality_policy,
            "data_version": self.data_version,
            "published_years": list(self.published_years),
            "sample_retrieved_at": self.sample_retrieved_at,
            "source": {
                "dataset": str(self.source["dataset"]),
                "provider": str(self.source["provider"]),
                "product_version": str(self.source["product_version"]),
                "reference_period": self.source["reference_period"],
                "doi": str(self.source["doi"]),
            },
        }


@dataclass(frozen=True)
class Registry:
    variables: Mapping[str, VariableSpec]
    settings: ServiceSettings

    @classmethod
    def load(cls, manifests_root: Path, app_path: Path) -> Registry:
        paths = validate_targets([manifests_root])
        specs = {
            manifest["id"]: VariableSpec.from_manifest(manifest)
            for manifest in (load_json(path) for path in paths)
        }
        app = load_json(app_path)
        service = app.get("service")
        if not isinstance(service, dict):
            raise ValueError(f"{app_path}: service settings are missing")
        maximum_active = int(app["maximum_active_variables"])
        if maximum_active != 2:
            raise ValueError("the application must cap active variables at exactly two")
        settings = ServiceSettings(
            api_version=str(service["api_version"]),
            dataset_version=str(service["dataset_version"]),
            palette_version=str(service["palette_version"]),
            maximum_active_variables=maximum_active,
            maximum_zoom=int(service["maximum_zoom"]),
            maximum_product_files=int(service["maximum_product_files"]),
            maximum_development_cells_per_product=int(
                service["maximum_development_cells_per_product"]
            ),
            release_report=str(service["release_report"]),
        )
        if not 0 <= settings.maximum_zoom <= 12:
            raise ValueError("maximum development zoom must be between zero and twelve")
        if settings.maximum_product_files < 1:
            raise ValueError("maximum product files must be positive")
        for spec in specs.values():
            if spec.data_version != settings.dataset_version:
                raise ValueError(
                    f"{spec.id}: data version does not match configured dataset version"
                )
        return cls(variables=specs, settings=settings)

    def selection(self, variable_ids: Sequence[str]) -> tuple[VariableSpec, ...]:
        if not 1 <= len(variable_ids) <= self.settings.maximum_active_variables:
            raise ServiceError(
                400,
                "invalid_variable_count",
                "select one or two variables",
            )
        if len(set(variable_ids)) != len(variable_ids):
            raise ServiceError(
                400,
                "duplicate_variable",
                "selected variables must be different",
            )
        try:
            specs = tuple(self.variables[variable_id] for variable_id in variable_ids)
        except KeyError as error:
            raise ServiceError(
                400,
                "unknown_variable",
                f"unknown variable: {error.args[0]}",
            ) from error
        if len(specs) == 2:
            reason = compatibility_reason(specs[0], specs[1])
            if reason is not None:
                raise ServiceError(422, "incompatible_variables", reason)
        return specs


def compatibility_reason(left: VariableSpec, right: VariableSpec) -> str | None:
    """Return a variable-neutral incompatibility reason, or None."""

    if left.grid_id != right.grid_id:
        return "selected variables do not share a grid"
    if left.resolution_degrees != right.resolution_degrees:
        return "selected variables do not share a grid resolution"
    if left.calendar != right.calendar:
        return "selected variables do not share a calendar"
    if left.statistic != right.statistic:
        return "selected variables do not share an aggregation statistic"
    if not set(left.coverage_months).intersection(right.coverage_months):
        return "selected variables do not share calendar months"
    if not set(left.published_years).intersection(right.published_years):
        return "selected variables do not share a published year"
    west = max(left.coverage_bbox[0], right.coverage_bbox[0])
    south = max(left.coverage_bbox[1], right.coverage_bbox[1])
    east = min(left.coverage_bbox[2], right.coverage_bbox[2])
    north = min(left.coverage_bbox[3], right.coverage_bbox[3])
    if west >= east or south >= north:
        return "selected variables do not share spatial coverage"
    return None


@dataclass(frozen=True)
class ReleaseProduct:
    region_id: str
    year: int
    months: tuple[int, ...]
    path: Path
    latitudes: tuple[float, ...]
    longitudes: tuple[float, ...]

    def contains(self, latitude: float, longitude: float, resolution: float) -> bool:
        half_cell = resolution / 2
        return (
            min(self.latitudes) - half_cell <= latitude <= max(self.latitudes) + half_cell
            and min(self.longitudes) - half_cell <= longitude < max(self.longitudes) + half_cell
        )


@dataclass(frozen=True)
class Release:
    fixture: bool
    official_evidence: bool
    scope: str
    fingerprint: str
    products: tuple[ReleaseProduct, ...]


@dataclass(frozen=True)
class AggregatedVariable:
    spec: VariableSpec
    values: FloatArray
    valid_month_count: CountArray
    required_valid_month_count: int
    class_indices: ClassArray
    quality_pass_month_count: CountArray | None
    selected_month_count: int


@dataclass(frozen=True)
class AggregatedProduct:
    product: ReleaseProduct
    variables: tuple[AggregatedVariable, ...]


def _xarray() -> Any:
    try:
        return importlib.import_module("xarray")
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "xarray is required; install the pipeline service dependency extra"
        ) from error


def _month_from_time(value: Any) -> int:
    rendered = np.datetime_as_string(np.datetime64(value), unit="D")
    return int(rendered[5:7])


def _safe_product_path(repository_root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise ValueError("release product paths must be repository-relative")
    published_root = (repository_root / "data" / "published").resolve()
    candidate = (repository_root / relative_path).resolve()
    try:
        candidate.relative_to(published_root)
    except ValueError as error:
        raise ValueError("release product path escapes data/published") from error
    return candidate


class DataService:
    """Validated release catalogue plus shared point/tile computations."""

    def __init__(self, registry: Registry, release: Release) -> None:
        self.registry = registry
        self.release = release

    @classmethod
    def from_repository(
        cls,
        repository_root: Path,
        *,
        manifests_root: Path | None = None,
        app_path: Path | None = None,
        report_path: Path | None = None,
        allow_fixture: bool = False,
    ) -> DataService:
        root = repository_root.resolve()
        registry = Registry.load(
            manifests_root or root / "config" / "variables",
            app_path or root / "config" / "app.json",
        )
        selected_report = report_path or root / registry.settings.release_report
        release = _load_release(root, selected_report, registry, allow_fixture=allow_fixture)
        return cls(registry, release)

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "api_version": self.registry.settings.api_version,
            "software_version": __version__,
            "dataset_version": self.registry.settings.dataset_version,
            "data_ready": bool(self.release.products),
            "product_count": len(self.release.products),
            "fixture": self.release.fixture,
            "official_evidence": self.release.official_evidence,
            "scope": self.release.scope,
        }

    def availability(self) -> dict[str, object]:
        years = sorted({product.year for product in self.release.products})
        year_records: list[dict[str, object]] = []
        complete_years: list[int] = []
        for year in years:
            products = [product for product in self.release.products if product.year == year]
            common_months = sorted(set.intersection(*(set(item.months) for item in products)))
            complete = common_months == list(range(1, 13))
            if complete:
                complete_years.append(year)
            year_records.append(
                {
                    "year": year,
                    "months": common_months,
                    "complete": complete,
                    "regions": sorted(product.region_id for product in products),
                }
            )
        specs = sorted(self.registry.variables.values(), key=lambda item: item.id)
        pairs = []
        for index, left in enumerate(specs):
            for right in specs[index + 1 :]:
                reason = compatibility_reason(left, right)
                pairs.append(
                    {
                        "variables": [left.id, right.id],
                        "compatible": reason is None,
                        "reason": reason,
                    }
                )
        return {
            "status": "ok",
            "schema_version": "1.0",
            "api_version": self.registry.settings.api_version,
            "dataset_version": self.registry.settings.dataset_version,
            "fixture": self.release.fixture,
            "official_evidence": self.release.official_evidence,
            "scope": self.release.scope,
            "maximum_active_variables": self.registry.settings.maximum_active_variables,
            "latest_complete_year": max(complete_years) if complete_years else None,
            "years": year_records,
            "variables": [spec.public_metadata() for spec in specs],
            "compatibility": pairs,
        }

    def sample(
        self,
        variable_ids: Sequence[str],
        year: int,
        month_mask: int,
        latitude: float,
        longitude: float,
    ) -> tuple[dict[str, object], str]:
        specs = self._validate_request(variable_ids, year, month_mask)
        if not math.isfinite(latitude) or not -90 <= latitude <= 90:
            raise ServiceError(400, "invalid_latitude", "latitude must be between -90 and 90")
        if not math.isfinite(longitude) or not -180 <= longitude < 180:
            raise ServiceError(
                400,
                "invalid_longitude",
                "longitude must be at least -180 and less than 180",
            )
        cache_key, etag = self._cache_identity(
            specs,
            year,
            month_mask,
            "point_sample",
            {"latitude": latitude, "longitude": longitude},
        )
        resolution = _common_resolution(specs)
        candidates = [
            product
            for product in self.release.products
            if product.year == year and product.contains(latitude, longitude, resolution)
        ]
        base: dict[str, object] = {
            "schema_version": "1.0",
            "dataset_version": self.registry.settings.dataset_version,
            "year": year,
            "month_mask": mask_to_hex(month_mask),
            "months": list(mask_to_months(month_mask)),
            "requested_coordinate": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "cache_key": cache_key,
            "fixture": self.release.fixture,
            "official_evidence": self.release.official_evidence,
            "scope": self.release.scope,
        }
        if not candidates:
            base.update(
                {
                    "status": "no_data",
                    "reason": "outside_bounded_sample",
                    "variables": [_empty_variable(spec) for spec in specs],
                }
            )
            return base, etag

        product = sorted(candidates, key=lambda item: item.region_id)[0]
        aggregated = self._aggregate_product(product, specs, month_mask)
        row = int(np.argmin(np.abs(np.asarray(product.latitudes) - latitude)))
        column = int(np.argmin(np.abs(np.asarray(product.longitudes) - longitude)))
        variable_records = [
            _cell_variable(variable, row, column, include_source=True)
            for variable in aggregated.variables
        ]
        statuses = {str(record["status"]) for record in variable_records}
        status = (
            "ok" if statuses == {"ok"} else "no_data" if statuses == {"no_data"} else "partial_data"
        )
        base.update(
            {
                "status": status,
                "region_id": product.region_id,
                "grid_cell": {
                    "latitude": product.latitudes[row],
                    "longitude": product.longitudes[column],
                    "row": row,
                    "column": column,
                },
                "quality_warning": any(
                    record["quality_state"] in {"partial_quality", "low_quality"}
                    for record in variable_records
                ),
                "variables": variable_records,
            }
        )
        return base, etag

    def tile(
        self,
        dataset_version: str,
        variable_ids: Sequence[str],
        year: int,
        month_mask: int,
        zoom: int,
        tile_x: int,
        tile_y: int,
    ) -> tuple[dict[str, object], str]:
        if dataset_version != self.registry.settings.dataset_version:
            raise ServiceError(
                404,
                "unknown_dataset_version",
                "the requested immutable dataset version is unavailable",
            )
        if isinstance(zoom, bool) or not 0 <= zoom <= self.registry.settings.maximum_zoom:
            raise ServiceError(
                400,
                "invalid_zoom",
                f"zoom must be between 0 and {self.registry.settings.maximum_zoom}",
            )
        tile_count = 1 << zoom
        if not 0 <= tile_x < tile_count or not 0 <= tile_y < tile_count:
            raise ServiceError(
                400,
                "invalid_tile_coordinate",
                "tile coordinates must be within the selected zoom",
            )
        specs = self._validate_request(variable_ids, year, month_mask)
        cache_key, etag = self._cache_identity(
            specs,
            year,
            month_mask,
            "development_sparse_json_tile",
            {"zoom": zoom, "tile_x": tile_x, "tile_y": tile_y},
        )
        cells: list[dict[str, object]] = []
        for product in sorted(self.release.products, key=lambda item: item.region_id):
            if product.year != year or not _product_intersects_tile(product, zoom, tile_x, tile_y):
                continue
            aggregated = self._aggregate_product(product, specs, month_mask)
            for row, latitude in enumerate(product.latitudes):
                for column, longitude in enumerate(product.longitudes):
                    if _web_mercator_tile(latitude, longitude, zoom) != (tile_x, tile_y):
                        continue
                    cells.append(
                        {
                            "region_id": product.region_id,
                            "row": row,
                            "column": column,
                            "latitude": latitude,
                            "longitude": longitude,
                            "variables": [
                                _cell_variable(variable, row, column, include_source=True)
                                for variable in aggregated.variables
                            ],
                        }
                    )
        return (
            {
                "status": "ok" if cells else "no_data",
                "schema_version": "1.0",
                "format": "development_sparse_grid_cells",
                "dataset_version": self.registry.settings.dataset_version,
                "year": year,
                "month_mask": mask_to_hex(month_mask),
                "months": list(mask_to_months(month_mask)),
                "tile": {"z": zoom, "x": tile_x, "y": tile_y},
                "cache_key": cache_key,
                "fixture": self.release.fixture,
                "official_evidence": self.release.official_evidence,
                "scope": self.release.scope,
                "variables": [spec.public_metadata() for spec in specs],
                "cells": cells,
            },
            etag,
        )

    def _validate_request(
        self,
        variable_ids: Sequence[str],
        year: int,
        month_mask: int,
    ) -> tuple[VariableSpec, ...]:
        if isinstance(year, bool) or not isinstance(year, int):
            raise ServiceError(400, "invalid_year", "year must be an integer")
        try:
            validate_mask(month_mask)
        except (TypeError, ValueError) as error:
            raise ServiceError(400, "invalid_month_mask", str(error)) from error
        specs = self.registry.selection(variable_ids)
        if any(year not in spec.published_years for spec in specs):
            raise ServiceError(
                422,
                "year_not_available",
                "the selected variables are not published for this year",
            )
        products = [product for product in self.release.products if product.year == year]
        if not products:
            raise ServiceError(422, "year_not_available", "the selected year is unavailable")
        common_months = set.intersection(*(set(product.months) for product in products))
        missing = sorted(set(mask_to_months(month_mask)) - common_months)
        if missing:
            rendered = ", ".join(str(month) for month in missing)
            raise ServiceError(
                422,
                "months_not_available",
                f"selected sample months are unavailable: {rendered}",
            )
        return specs

    def _aggregate_product(
        self,
        product: ReleaseProduct,
        specs: Sequence[VariableSpec],
        month_mask: int,
    ) -> AggregatedProduct:
        xr = _xarray()
        selected_months = mask_to_months(month_mask)
        indexes = [product.months.index(month) for month in selected_months]
        variables: list[AggregatedVariable] = []
        with xr.open_dataset(product.path, decode_cf=True, mask_and_scale=True) as dataset:
            for spec in specs:
                result = median_for_month_mask(
                    np.asarray(dataset[spec.id].values),
                    product.months,
                    month_mask,
                    spec.minimum_valid_fraction,
                )
                quality_pass_count: CountArray | None = None
                if spec.quality_field is not None:
                    quality = np.asarray(dataset[spec.quality_field].values)[indexes]
                    quality_pass_count = np.sum(
                        np.isin(quality, spec.quality_pass_values),
                        axis=0,
                        dtype=np.int64,
                    )
                variables.append(
                    AggregatedVariable(
                        spec=spec,
                        values=result.values,
                        valid_month_count=result.valid_month_count,
                        required_valid_month_count=result.required_valid_month_count,
                        class_indices=spec.classification.indices(result.values),
                        quality_pass_month_count=quality_pass_count,
                        selected_month_count=len(selected_months),
                    )
                )
        return AggregatedProduct(product=product, variables=tuple(variables))

    def _cache_identity(
        self,
        specs: Sequence[VariableSpec],
        year: int,
        month_mask: int,
        response_kind: str,
        spatial_identity: Mapping[str, object],
    ) -> tuple[str, str]:
        payload = {
            "api_version": self.registry.settings.api_version,
            "software_version": __version__,
            "dataset_version": self.registry.settings.dataset_version,
            "release_fingerprint": self.release.fingerprint,
            "variables": [
                {
                    "id": spec.id,
                    "data_version": spec.data_version,
                    "aggregation": {
                        "statistic": spec.statistic,
                        "minimum_valid_fraction": spec.minimum_valid_fraction,
                    },
                    "classification": spec.classification.cache_signature(),
                    "quality": {
                        "policy": spec.quality_policy,
                        "field": spec.quality_field,
                        "pass_values": list(spec.quality_pass_values),
                    },
                }
                for spec in specs
            ],
            "year": year,
            "month_mask": mask_to_hex(month_mask),
            "palette_version": self.registry.settings.palette_version,
            "response_kind": response_kind,
            "spatial_identity": dict(spatial_identity),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        return f"{self.registry.settings.api_version}/{digest}", digest


def _load_release(
    repository_root: Path,
    report_path: Path,
    registry: Registry,
    *,
    allow_fixture: bool,
) -> Release:
    report = load_json(report_path)
    if report.get("status") != "complete":
        raise ValueError(f"{report_path}: release report is not complete")
    fixture = report.get("fixture") is True
    official = report.get("source_official_evidence") is True
    if fixture and not allow_fixture:
        raise ValueError(f"{report_path}: fixture releases are disabled")
    if not fixture and not official:
        raise ValueError(f"{report_path}: non-fixture release lacks official evidence")
    fingerprint = str(report.get("plan_sha256", ""))
    if len(fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in fingerprint
    ):
        raise ValueError(f"{report_path}: invalid release fingerprint")
    raw_outputs = report.get("outputs")
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise ValueError(f"{report_path}: release has no products")
    if len(raw_outputs) > registry.settings.maximum_product_files:
        raise ValueError(f"{report_path}: release exceeds the bounded product-file count")

    xr = _xarray()
    products: list[ReleaseProduct] = []
    expected_variables = set(registry.variables)
    expected_quality = {
        spec.quality_field for spec in registry.variables.values() if spec.quality_field is not None
    }
    for raw_output in raw_outputs:
        if not isinstance(raw_output, dict):
            raise ValueError(f"{report_path}: invalid product record")
        product_path = _safe_product_path(repository_root, str(raw_output["path"]))
        if not product_path.is_file():
            raise ValueError(f"{product_path}: release product is missing")
        if sha256_file(product_path) != str(raw_output["sha256"]):
            raise ValueError(f"{product_path}: release product checksum mismatch")
        with xr.open_dataset(product_path, decode_cf=True, mask_and_scale=True) as dataset:
            product_fixture = str(dataset.attrs.get("fixture", "")).lower() == "true"
            if product_fixture != fixture:
                raise ValueError(f"{product_path}: fixture state does not match release report")
            if str(dataset.attrs.get("grid_id")) not in {
                spec.grid_id for spec in registry.variables.values()
            }:
                raise ValueError(f"{product_path}: product grid is not registered")
            if not expected_variables.issubset(dataset.data_vars) or not expected_quality.issubset(
                dataset.data_vars
            ):
                raise ValueError(f"{product_path}: registered data or quality fields are missing")
            year = int(dataset.attrs["analysis_year"])
            region_id = str(dataset.attrs["region_id"])
            latitudes = tuple(float(value) for value in np.asarray(dataset["latitude"].values))
            longitudes = tuple(float(value) for value in np.asarray(dataset["longitude"].values))
            months = tuple(_month_from_time(value) for value in dataset["time"].values)
            if months != tuple(int(value) for value in raw_output["months"]):
                raise ValueError(f"{product_path}: report months do not match product time")
            if len(set(months)) != len(months):
                raise ValueError(f"{product_path}: duplicate product months")
            cell_count = len(latitudes) * len(longitudes)
            if cell_count > registry.settings.maximum_development_cells_per_product:
                raise ValueError(f"{product_path}: product exceeds the development cell bound")
            if not latitudes or not longitudes:
                raise ValueError(f"{product_path}: product grid is empty")
            if int(raw_output.get("shape", [0, 0, 0])[0]) != len(months):
                raise ValueError(f"{product_path}: report shape does not match product time")
        products.append(
            ReleaseProduct(
                region_id=region_id,
                year=year,
                months=months,
                path=product_path,
                latitudes=latitudes,
                longitudes=longitudes,
            )
        )
    if len({(product.region_id, product.year) for product in products}) != len(products):
        raise ValueError(f"{report_path}: duplicate region-year products")
    return Release(
        fixture=fixture,
        official_evidence=official,
        scope=str(report.get("scope", "unspecified")),
        fingerprint=fingerprint,
        products=tuple(products),
    )


def _common_resolution(specs: Sequence[VariableSpec]) -> float:
    resolutions = {spec.resolution_degrees for spec in specs}
    if len(resolutions) != 1:
        raise ServiceError(
            422,
            "incompatible_variables",
            "selected variables do not share a grid resolution",
        )
    return next(iter(resolutions))


def _empty_variable(spec: VariableSpec) -> dict[str, object]:
    return {
        "id": spec.id,
        "label": spec.label,
        "unit": spec.unit,
        "status": "no_data",
        "value": None,
        "class_index": None,
        "class_label": "No data",
        "valid_month_count": 0,
        "required_valid_month_count": None,
        "selected_month_count": None,
        "quality_state": "not_evaluated",
        "quality_pass_month_count": None,
        "source": {
            "dataset": str(spec.source["dataset"]),
            "product_version": str(spec.source["product_version"]),
            "sample_retrieved_at": spec.sample_retrieved_at,
        },
    }


def _cell_variable(
    variable: AggregatedVariable,
    row: int,
    column: int,
    *,
    include_source: bool,
) -> dict[str, object]:
    raw_value = float(variable.values[row, column])
    value = raw_value if math.isfinite(raw_value) else None
    class_index_value = int(variable.class_indices[row, column])
    class_index = class_index_value if class_index_value >= 0 else None
    quality_count: int | None = None
    if variable.quality_pass_month_count is None:
        quality_state = "not_applicable"
    else:
        quality_count = int(variable.quality_pass_month_count[row, column])
        if quality_count == variable.selected_month_count:
            quality_state = "passes"
        elif quality_count == 0:
            quality_state = "low_quality"
        else:
            quality_state = "partial_quality"
    result: dict[str, object] = {
        "id": variable.spec.id,
        "label": variable.spec.label,
        "unit": variable.spec.unit,
        "status": "ok" if value is not None else "no_data",
        "value": value,
        "class_index": class_index,
        "class_label": (
            variable.spec.classification.labels[class_index]
            if class_index is not None
            else "No data"
        ),
        "valid_month_count": int(variable.valid_month_count[row, column]),
        "required_valid_month_count": variable.required_valid_month_count,
        "selected_month_count": variable.selected_month_count,
        "quality_state": quality_state,
        "quality_pass_month_count": quality_count,
    }
    if include_source:
        result["source"] = {
            "dataset": str(variable.spec.source["dataset"]),
            "provider": str(variable.spec.source["provider"]),
            "product_version": str(variable.spec.source["product_version"]),
            "reference_period": variable.spec.source["reference_period"],
            "doi": str(variable.spec.source["doi"]),
            "sample_retrieved_at": variable.spec.sample_retrieved_at,
        }
    return result


def _web_mercator_tile(latitude: float, longitude: float, zoom: int) -> tuple[int, int]:
    tile_count = 1 << zoom
    clipped_latitude = max(-85.05112878, min(85.05112878, latitude))
    tile_x = min(tile_count - 1, int((longitude + 180.0) / 360.0 * tile_count))
    radians = math.radians(clipped_latitude)
    tile_y = min(
        tile_count - 1,
        max(
            0,
            int((1.0 - math.asinh(math.tan(radians)) / math.pi) / 2.0 * tile_count),
        ),
    )
    return tile_x, tile_y


def _product_intersects_tile(
    product: ReleaseProduct,
    zoom: int,
    tile_x: int,
    tile_y: int,
) -> bool:
    return any(
        _web_mercator_tile(latitude, longitude, zoom) == (tile_x, tile_y)
        for latitude in product.latitudes
        for longitude in product.longitudes
    )
