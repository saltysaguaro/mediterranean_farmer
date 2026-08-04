"""Normalize official ZIP-packaged UTCI, SPEI-3, and quality sample arrays."""

from __future__ import annotations

import importlib
import json
import math
import os
import shutil
import tempfile
import warnings
import zipfile
from calendar import monthrange
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from thermal_drought.acquire.inspection import inspect_raw_root, safe_netcdf_archive_members
from thermal_drought.acquire.requests import (
    DROUGHT_DATASET_ID,
    SOURCE_METADATA,
    UTCI_DATASET_ID,
    AcquisitionRequest,
    Region,
    build_representative_requests,
    plan_sha256,
)
from thermal_drought.acquire.runner import sha256_file
from thermal_drought.classification import FixedClassification
from thermal_drought.storage import (
    StoragePolicy,
    load_storage_policy,
    preflight_archive_extraction,
    preflight_normalization,
)

FloatArray = NDArray[np.float64]
CountArray = NDArray[np.uint8]

UTCI_VARIABLE = "utci_daily_max"
SPEI_VARIABLE = "SPEI3"
QUALITY_VARIABLE = "significance"
CANONICAL_CRS = "EPSG:4326"
CANONICAL_GRID = "era5_latlon_0_25"
KELVIN_OFFSET = 273.15


class NormalizationError(RuntimeError):
    """Raised when source values do not satisfy a versioned normalization contract."""


@dataclass(frozen=True)
class CanonicalField:
    """One two-dimensional field on canonical latitude/longitude coordinates."""

    values: FloatArray
    latitudes: FloatArray
    longitudes: FloatArray
    source_date: date


@dataclass(frozen=True)
class NormalizedPeriod:
    """Monthly UTCI, provider SPEI-3, and its provider quality state."""

    region: Region
    year: int
    month: int
    utci_celsius: FloatArray
    utci_valid_day_count: CountArray
    spei_source: FloatArray
    spei_quality: CountArray
    spei_published: FloatArray
    latitudes: FloatArray
    longitudes: FloatArray


def _optional_module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        raise NormalizationError(
            f"{name} is not installed; install the pipeline normalize extra"
        ) from error


@contextmanager
def _materialized_netcdf_members(path: Path) -> Iterator[list[tuple[str, Path]]]:
    if not path.is_file():
        raise NormalizationError(f"{path}: source artifact is missing")
    if not zipfile.is_zipfile(path):
        yield [(path.name, path)]
        return

    try:
        with zipfile.ZipFile(path) as archive:
            members = safe_netcdf_archive_members(archive, path)
            preflight_archive_extraction(
                load_storage_policy(),
                sum(member.file_size for member in members),
                operation=f"archive_normalization:{path.name}",
            )
            with tempfile.TemporaryDirectory(prefix="thermal-drought-normalize-") as temp:
                root = Path(temp)
                extracted: list[tuple[str, Path]] = []
                for index, member in enumerate(members):
                    target = root / f"{index:03d}.nc"
                    with archive.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    extracted.append((member.filename, target))
                yield extracted
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise NormalizationError(f"{path}: ZIP extraction failed: {error}") from error


def _source_date(dataset: Any, path: Path) -> date:
    if "time" not in dataset.coords or dataset.sizes.get("time") != 1:
        raise NormalizationError(f"{path}: expected exactly one source time")
    value = dataset.coords["time"].values[0]
    if isinstance(value, np.datetime64):
        token = np.datetime_as_string(value, unit="D")
        return date.fromisoformat(token)
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    year = getattr(value, "year", None)
    month = getattr(value, "month", None)
    day = getattr(value, "day", None)
    if isinstance(year, int) and isinstance(month, int) and isinstance(day, int):
        return date(year, month, day)
    raise NormalizationError(f"{path}: source time did not decode to a calendar date")


def _axis_name(data_array: Any, axis: str, path: Path) -> str:
    aliases = {
        "latitude": {"lat", "latitude"},
        "longitude": {"lon", "longitude"},
    }[axis]
    expected_axis = "Y" if axis == "latitude" else "X"
    for dimension in data_array.dims:
        if dimension not in data_array.coords:
            continue
        coordinate = data_array.coords[dimension]
        if (
            dimension.lower() in aliases
            or coordinate.attrs.get("standard_name") == axis
            or coordinate.attrs.get("axis") == expected_axis
        ):
            return str(dimension)
    raise NormalizationError(f"{path}: cannot identify the {axis} dimension")


def _canonical_field(data_array: Any, path: Path, source_date: date) -> CanonicalField:
    if "time" in data_array.dims:
        if data_array.sizes["time"] != 1:
            raise NormalizationError(f"{path}: expected one value along the time dimension")
        data_array = data_array.isel(time=0)
    latitude_name = _axis_name(data_array, "latitude", path)
    longitude_name = _axis_name(data_array, "longitude", path)
    if set(data_array.dims) != {latitude_name, longitude_name}:
        raise NormalizationError(
            f"{path}: expected only latitude and longitude after selecting source time"
        )
    data_array = data_array.transpose(latitude_name, longitude_name)
    latitudes = np.asarray(data_array.coords[latitude_name].values, dtype=np.float64)
    source_longitudes = np.asarray(
        data_array.coords[longitude_name].values,
        dtype=np.float64,
    )
    values = np.asarray(data_array.values, dtype=np.float64)
    if (
        values.shape != (latitudes.size, source_longitudes.size)
        or not np.all(np.isfinite(latitudes))
        or not np.all(np.isfinite(source_longitudes))
    ):
        raise NormalizationError(f"{path}: coordinate shape or values are invalid")

    longitudes = ((source_longitudes + 180.0) % 360.0) - 180.0
    latitude_order = np.argsort(-latitudes)
    longitude_order = np.argsort(longitudes)
    latitudes = latitudes[latitude_order]
    longitudes = longitudes[longitude_order]
    values = values[np.ix_(latitude_order, longitude_order)]

    if len(np.unique(latitudes)) != len(latitudes) or len(np.unique(longitudes)) != len(longitudes):
        raise NormalizationError(f"{path}: canonical coordinates are not unique")
    for coordinates, label, expected_step in (
        (latitudes, "latitude", -0.25),
        (longitudes, "longitude", 0.25),
    ):
        differences = np.diff(coordinates)
        if differences.size and not np.allclose(differences, expected_step, atol=1e-9):
            raise NormalizationError(f"{path}: {label} is not on the canonical 0.25 degree grid")
    return CanonicalField(values, latitudes, longitudes, source_date)


def _contract_unit(
    attributes: Mapping[str, object],
    *,
    path: Path,
    dataset_id: str,
    product_version: str,
    variable_name: str,
) -> str:
    observed = attributes.get("units")
    if dataset_id == UTCI_DATASET_ID:
        if product_version != "1.1" or variable_name != UTCI_VARIABLE:
            raise NormalizationError(
                f"{path}: no UTCI unit adapter for {product_version}/{variable_name}"
            )
        if observed is None:
            return "K"
        if str(observed).strip().lower() in {"k", "kelvin"}:
            return "K"
        raise NormalizationError(f"{path}: unexpected UTCI unit {observed!r}")
    if dataset_id == DROUGHT_DATASET_ID and variable_name == SPEI_VARIABLE:
        if product_version != "1.0":
            raise NormalizationError(
                f"{path}: no SPEI-3 unit adapter for product {product_version}"
            )
        if observed is None:
            return "1"
        if str(observed).strip().lower() in {"1", "dimensionless"}:
            return "1"
        raise NormalizationError(f"{path}: unexpected SPEI-3 unit {observed!r}")
    raise NormalizationError(f"{path}: no versioned unit contract for {dataset_id}/{variable_name}")


def _assert_range(
    values: FloatArray,
    minimum: float,
    maximum: float,
    label: str,
    path: Path,
) -> None:
    finite = values[np.isfinite(values)]
    if finite.size and (float(finite.min()) < minimum or float(finite.max()) > maximum):
        raise NormalizationError(f"{path}: {label} values fall outside [{minimum}, {maximum}]")


def _assert_same_grid(left: CanonicalField, right: CanonicalField, path: Path) -> None:
    if not (
        np.array_equal(left.latitudes, right.latitudes)
        and np.array_equal(left.longitudes, right.longitudes)
    ):
        raise NormalizationError(f"{path}: source cell centers do not match exactly")


def _read_utci_month(
    path: Path,
    request: AcquisitionRequest,
) -> tuple[FloatArray, CountArray, CanonicalField]:
    xr = _optional_module("xarray")
    if request.year is None:
        raise NormalizationError(f"{path}: UTCI request has no analysis year")
    expected_dates = {
        date(request.year, request.month, day)
        for day in range(1, monthrange(request.year, request.month)[1] + 1)
    }
    fields: list[CanonicalField] = []
    observed_dates: set[date] = set()
    with _materialized_netcdf_members(path) as members:
        for member_name, member_path in members:
            try:
                with xr.open_dataset(member_path, decode_cf=True, mask_and_scale=True) as dataset:
                    if UTCI_VARIABLE not in dataset.data_vars:
                        raise NormalizationError(
                            f"{path}/{member_name}: required {UTCI_VARIABLE} field is missing"
                        )
                    source_date = _source_date(dataset, path)
                    data_array = dataset[UTCI_VARIABLE]
                    _contract_unit(
                        data_array.attrs,
                        path=path,
                        dataset_id=request.dataset_id,
                        product_version=SOURCE_METADATA[request.dataset_id].product_version,
                        variable_name=UTCI_VARIABLE,
                    )
                    if data_array.attrs.get("cell_methods") != "time: maximum":
                        raise NormalizationError(
                            f"{path}/{member_name}: field is not provider daily maximum UTCI"
                        )
                    field = _canonical_field(data_array, path, source_date)
                    _assert_range(field.values, 150.0, 400.0, "UTCI Kelvin", path)
                    fields.append(field)
                    if source_date in observed_dates:
                        raise NormalizationError(f"{path}: duplicate UTCI date {source_date}")
                    observed_dates.add(source_date)
            except NormalizationError:
                raise
            except Exception as error:
                raise NormalizationError(
                    f"{path}/{member_name}: cannot decode UTCI member: {error}"
                ) from error
    if observed_dates != expected_dates:
        missing = sorted(expected_dates - observed_dates)
        unexpected = sorted(observed_dates - expected_dates)
        raise NormalizationError(
            f"{path}: UTCI daily dates differ from the requested month; "
            f"missing={missing}, unexpected={unexpected}"
        )
    fields.sort(key=lambda field: field.source_date)
    representative = fields[0]
    for field in fields[1:]:
        _assert_same_grid(representative, field, path)
    daily_kelvin = np.stack([field.values for field in fields])
    valid_days = np.sum(np.isfinite(daily_kelvin), axis=0, dtype=np.uint8)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        monthly_kelvin = np.nanmedian(daily_kelvin, axis=0)
    monthly_celsius = np.asarray(monthly_kelvin - KELVIN_OFFSET, dtype=np.float64)
    _assert_range(monthly_celsius, -150.0, 100.0, "monthly UTCI Celsius", path)
    return monthly_celsius, valid_days, representative


def _read_single_field(
    path: Path,
    request: AcquisitionRequest,
    variable_name: str,
) -> CanonicalField:
    xr = _optional_module("xarray")
    with _materialized_netcdf_members(path) as members:
        if len(members) != 1:
            raise NormalizationError(
                f"{path}: expected one {variable_name} NetCDF member; found {len(members)}"
            )
        member_name, member_path = members[0]
        try:
            with xr.open_dataset(member_path, decode_cf=True, mask_and_scale=True) as dataset:
                if variable_name not in dataset.data_vars:
                    raise NormalizationError(
                        f"{path}/{member_name}: required {variable_name} field is missing"
                    )
                source_date = _source_date(dataset, path)
                data_array = dataset[variable_name]
                if variable_name == SPEI_VARIABLE:
                    _contract_unit(
                        data_array.attrs,
                        path=path,
                        dataset_id=request.dataset_id,
                        product_version=SOURCE_METADATA[request.dataset_id].product_version,
                        variable_name=variable_name,
                    )
                elif variable_name == QUALITY_VARIABLE:
                    observed_units = data_array.attrs.get("units")
                    if str(observed_units).strip() != "1":
                        raise NormalizationError(
                            f"{path}: unexpected provider quality unit {observed_units!r}"
                        )
                return _canonical_field(data_array, path, source_date)
        except NormalizationError:
            raise
        except Exception as error:
            raise NormalizationError(
                f"{path}/{member_name}: cannot decode {variable_name}: {error}"
            ) from error


def normalize_period(
    utci_path: Path,
    spei_path: Path,
    quality_path: Path,
    utci_request: AcquisitionRequest,
    spei_request: AcquisitionRequest,
    quality_request: AcquisitionRequest,
) -> NormalizedPeriod:
    """Normalize one official or explicitly labeled structural-test source triple."""

    if (
        utci_request.region != spei_request.region
        or utci_request.region != quality_request.region
        or utci_request.year is None
        or utci_request.year != spei_request.year
        or utci_request.month != spei_request.month
        or utci_request.month != quality_request.month
        or quality_request.year is not None
    ):
        raise NormalizationError("source requests do not describe one paired period")

    utci, valid_days, utci_grid = _read_utci_month(utci_path, utci_request)
    spei = _read_single_field(spei_path, spei_request, SPEI_VARIABLE)
    quality = _read_single_field(quality_path, quality_request, QUALITY_VARIABLE)
    _assert_range(spei.values, -20.0, 20.0, "SPEI-3", spei_path)
    _assert_same_grid(utci_grid, spei, spei_path)
    _assert_same_grid(spei, quality, quality_path)

    if spei.source_date != date(spei_request.year, spei_request.month, 1):
        raise NormalizationError(f"{spei_path}: SPEI-3 time is not its analysis month")
    if quality.source_date.month != quality_request.month:
        raise NormalizationError(
            f"{quality_path}: quality field calendar month does not match SPEI-3"
        )
    finite_quality = quality.values[np.isfinite(quality.values)]
    if not all(value in {0.0, 1.0} for value in finite_quality.tolist()):
        raise NormalizationError(f"{quality_path}: quality values must be 0, 1, or nodata")
    quality_values = np.full(quality.values.shape, 255, dtype=np.uint8)
    quality_values[quality.values == 0.0] = 0
    quality_values[quality.values == 1.0] = 1
    published_spei = np.where(
        (quality_values == 1) & np.isfinite(spei.values),
        spei.values,
        np.nan,
    )
    return NormalizedPeriod(
        region=utci_request.region,
        year=utci_request.year,
        month=utci_request.month,
        utci_celsius=utci,
        utci_valid_day_count=valid_days,
        spei_source=spei.values,
        spei_quality=quality_values,
        spei_published=np.asarray(published_spei, dtype=np.float64),
        latitudes=utci_grid.latitudes,
        longitudes=utci_grid.longitudes,
    )


def _classification_label(manifest: Mapping[str, Any], value: float | None) -> str:
    return FixedClassification.from_manifest(manifest).label(value)


def _dataset_for_region(
    periods: Sequence[NormalizedPeriod],
    plan_fingerprint: str,
) -> Any:
    xr = _optional_module("xarray")
    ordered = sorted(periods, key=lambda period: period.month)
    representative = ordered[0]
    for period in ordered[1:]:
        if not (
            np.array_equal(representative.latitudes, period.latitudes)
            and np.array_equal(representative.longitudes, period.longitudes)
        ):
            raise NormalizationError("monthly periods for one region use different grids")
    times = np.asarray(
        [
            np.datetime64(
                f"{period.year:04d}-{period.month:02d}-01T00:00:00",
                "ns",
            )
            for period in ordered
        ]
    )
    dataset = xr.Dataset(
        data_vars={
            "utci_daymax_median": (
                ("time", "latitude", "longitude"),
                np.stack([period.utci_celsius for period in ordered]).astype(np.float32),
                {
                    "long_name": "Monthly median of daily maximum UTCI",
                    "units": "degree_Celsius",
                    "source_variable": UTCI_VARIABLE,
                    "source_unit_contract": "ERA5-HEAT v1.1 Kelvin",
                },
            ),
            "utci_valid_day_count": (
                ("time", "latitude", "longitude"),
                np.stack([period.utci_valid_day_count for period in ordered]),
                {"long_name": "Valid daily maximum UTCI observations in monthly median"},
            ),
            "spei_3_source": (
                ("time", "latitude", "longitude"),
                np.stack([period.spei_source for period in ordered]).astype(np.float32),
                {
                    "long_name": "Provider deterministic SPEI-3 before quality masking",
                    "units": "1",
                    "source_variable": SPEI_VARIABLE,
                },
            ),
            "spei_3_quality": (
                ("time", "latitude", "longitude"),
                np.stack([period.spei_quality for period in ordered]),
                {
                    "long_name": "Provider SPEI normality quality flag",
                    "flag_values": np.asarray([0, 1, 255], dtype=np.uint8),
                    "flag_meanings": "low_quality passes_normality_test no_data",
                    "source_variable": QUALITY_VARIABLE,
                },
            ),
            "spei_3": (
                ("time", "latitude", "longitude"),
                np.stack([period.spei_published for period in ordered]).astype(np.float32),
                {
                    "long_name": "Provider deterministic SPEI-3 after quality masking",
                    "units": "1",
                    "quality_rule": "publish only where significance equals 1",
                },
            ),
        },
        coords={
            "time": ("time", times, {"standard_name": "time"}),
            "latitude": (
                "latitude",
                representative.latitudes,
                {
                    "standard_name": "latitude",
                    "units": "degrees_north",
                    "axis": "Y",
                },
            ),
            "longitude": (
                "longitude",
                representative.longitudes,
                {
                    "standard_name": "longitude",
                    "units": "degrees_east",
                    "axis": "X",
                },
            ),
        },
        attrs={
            "schema_version": "1.0",
            "fixture": "false",
            "evidence_scope": "bounded representative official sample; not a global backfill",
            "region_id": representative.region.id,
            "analysis_year": representative.year,
            "grid_id": CANONICAL_GRID,
            "crs": CANONICAL_CRS,
            "calendar": "gregorian",
            "latitude_order": "north_to_south",
            "longitude_convention": "[-180, 180)",
            "plan_sha256": plan_fingerprint,
            "temporal_semantics": (
                "UTCI monthly median of provider daily maximum; provider deterministic "
                "SPEI-3 for each selected-year month"
            ),
            "source_temporal_frequency": ("daily maximum UTCI and provider monthly SPEI-3"),
            "published_temporal_frequency": "monthly",
            "daily_source_retention": (
                "archive outside local serving storage after checksum and "
                "monthly-product validation"
            ),
        },
    )
    return dataset


def _write_dataset_atomic(dataset: Any, target: Path) -> None:
    xr = _optional_module("xarray")
    _optional_module("h5netcdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        try:
            with xr.open_dataset(target) as current:
                loaded = current.load()
            if loaded.identical(dataset):
                return
        except Exception:
            pass
    temporary = target.with_suffix(f"{target.suffix}.part")
    temporary.unlink(missing_ok=True)
    encoding = {
        "utci_daymax_median": {"dtype": "float32", "zlib": True, "complevel": 6},
        "spei_3_source": {"dtype": "float32", "zlib": True, "complevel": 6},
        "spei_3": {"dtype": "float32", "zlib": True, "complevel": 6},
        "utci_valid_day_count": {"dtype": "uint8", "_FillValue": 255},
        "spei_3_quality": {"dtype": "uint8", "_FillValue": 255},
    }
    try:
        dataset.to_netcdf(temporary, engine="h5netcdf", encoding=encoding)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NormalizationError(f"{path}: manifest is not an object")
    return value


def _sample_records(
    periods: Sequence[NormalizedPeriod],
    manifests_root: Path,
) -> list[dict[str, Any]]:
    utci_manifest = _load_manifest(manifests_root / "utci_daymax_median.json")
    spei_manifest = _load_manifest(manifests_root / "spei_3.json")
    records: list[dict[str, Any]] = []
    for period in sorted(periods, key=lambda value: (value.region.id, value.month)):
        row = len(period.latitudes) // 2
        column = len(period.longitudes) // 2
        utci_value = float(period.utci_celsius[row, column])
        source_spei_value = float(period.spei_source[row, column])
        published_spei_value = float(period.spei_published[row, column])
        source_spei = source_spei_value if math.isfinite(source_spei_value) else None
        published_spei = published_spei_value if math.isfinite(published_spei_value) else None
        quality = int(period.spei_quality[row, column])
        records.append(
            {
                "region_id": period.region.id,
                "year": period.year,
                "month": period.month,
                "latitude": float(period.latitudes[row]),
                "longitude": float(period.longitudes[column]),
                "utci_daymax_median_celsius": round(utci_value, 6),
                "utci_class": _classification_label(utci_manifest, utci_value),
                "spei_3_source": (round(source_spei, 6) if source_spei is not None else None),
                "spei_3_published": (
                    round(published_spei, 6) if published_spei is not None else None
                ),
                "spei_3_class": _classification_label(spei_manifest, published_spei),
                "spei_quality_flag": quality,
                "spei_quality_state": {
                    0: "low_quality",
                    1: "passes_normality_test",
                    255: "no_data",
                }[quality],
                "precision_tolerance": {
                    "utci_celsius": 1e-5,
                    "spei_3": 1e-6,
                },
            }
        )
    return records


def normalize_representative_sample(
    raw_root: Path,
    output_root: Path,
    year: int = 2024,
    months: tuple[int, ...] = (1, 7),
    *,
    manifests_root: Path = Path("config/variables"),
    storage_policy: StoragePolicy | None = None,
) -> dict[str, Any]:
    """Verify the exact plan, normalize every source triple, and publish local NetCDF."""

    policy = storage_policy or load_storage_policy()
    storage_preflight = preflight_normalization(policy, output_root)
    requests = build_representative_requests(year=year, months=months)
    audit = inspect_raw_root(raw_root, expected_requests=requests)
    if audit["complete"] is not True or audit["official_evidence"] is not True:
        raise NormalizationError(
            "the exact non-fixture acquisition plan must pass before normalization"
        )
    indexed = {
        (request.region.id, request.year, request.month, request.variable_id): request
        for request in requests
    }
    quality = {
        (request.region.id, request.month): request
        for request in requests
        if request.variable_id == "spei_3_quality"
    }
    periods: list[NormalizedPeriod] = []
    for region in sorted({request.region for request in requests}, key=lambda item: item.id):
        for month in sorted(set(months)):
            utci_request = indexed[(region.id, year, month, "utci_daymax_median")]
            spei_request = indexed[(region.id, year, month, "spei_3")]
            quality_request = quality[(region.id, month)]
            periods.append(
                normalize_period(
                    raw_root / utci_request.target_relative_path,
                    raw_root / spei_request.target_relative_path,
                    raw_root / quality_request.target_relative_path,
                    utci_request,
                    spei_request,
                    quality_request,
                )
            )

    fingerprint = plan_sha256(requests)
    outputs: list[dict[str, Any]] = []
    for region in sorted({period.region for period in periods}, key=lambda item: item.id):
        region_periods = [period for period in periods if period.region == region]
        dataset = _dataset_for_region(region_periods, fingerprint)
        target = output_root / "v1" / str(year) / f"{region.id}.nc"
        _write_dataset_atomic(dataset, target)
        outputs.append(
            {
                "region_id": region.id,
                "path": str(target),
                "byte_size": target.stat().st_size,
                "sha256": sha256_file(target),
                "months": sorted(months),
                "shape": [
                    len(region_periods),
                    len(region_periods[0].latitudes),
                    len(region_periods[0].longitudes),
                ],
            }
        )
    return {
        "schema_version": "1.0",
        "status": "complete",
        "fixture": False,
        "scope": "bounded representative official sample; not global observations",
        "year": year,
        "months": sorted(months),
        "plan_sha256": fingerprint,
        "source_audit_complete": True,
        "source_official_evidence": True,
        "storage_preflight": storage_preflight,
        "temporal_retention": dict(policy.temporal_retention),
        "canonical_contract": {
            "grid_id": CANONICAL_GRID,
            "crs": CANONICAL_CRS,
            "latitude_order": "north_to_south",
            "longitude_convention": "[-180, 180)",
            "calendar": "gregorian",
            "time": "calendar month start",
            "utci": "ERA5-HEAT v1.1 utci_daily_max Kelvin to Celsius, then monthly median",
            "spei": "ERA5-Drought v1.0 deterministic provider SPEI3; no recomputation",
            "quality": "mask published SPEI-3 unless provider significance equals 1",
        },
        "outputs": outputs,
        "golden_center_cell_samples": _sample_records(periods, manifests_root),
        "publication_note": (
            "NetCDF is the local development representation for this bounded sample. "
            "Production Zarr publication remains pending its declared dependency."
        ),
    }
