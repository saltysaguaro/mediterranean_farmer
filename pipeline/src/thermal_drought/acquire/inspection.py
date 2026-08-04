"""Inspect verified NetCDF headers and compare representative source grids."""

from __future__ import annotations

import importlib
import json
import math
import os
import shutil
import tempfile
import zipfile
from calendar import monthrange
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from thermal_drought.acquire.requests import (
    SOURCE_METADATA,
    AcquisitionRequest,
    plan_sha256,
)
from thermal_drought.acquire.runner import receipt_path, request_sha256, sha256_file
from thermal_drought.storage import (
    load_storage_policy,
    managed_scope_root,
    preflight_archive_extraction,
    preflight_managed_write,
)

MetadataReader = Callable[[Path], dict[str, Any]]
MAX_COORDINATE_VALUES = 10_000
MAX_ARCHIVE_MEMBERS = 64
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


class InspectionError(RuntimeError):
    """Raised when an acquisition cannot supply trustworthy inspection evidence."""


def _json_scalar(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_scalar(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_scalar(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        converted = tolist()
        if converted is not value:
            return _json_scalar(converted)
    item = getattr(value, "item", None)
    if callable(item):
        try:
            value = item()
        except ValueError:
            return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _attributes(values: Mapping[object, object]) -> dict[str, object]:
    return {str(key): _json_scalar(value) for key, value in values.items()}


def _coordinate_values(variable: Any) -> list[object]:
    shape = tuple(int(value) for value in variable.shape)
    if len(shape) != 1:
        return []
    if shape[0] > MAX_COORDINATE_VALUES:
        raise InspectionError(
            f"coordinate {getattr(variable, 'name', '<unnamed>')} has {shape[0]} "
            f"values; inspection limit is {MAX_COORDINATE_VALUES}"
        )
    raw = variable.values.tolist()
    values = raw if isinstance(raw, list) else [raw]
    return [_json_scalar(value) for value in values]


def _numeric_values(values: Sequence[object]) -> list[float] | None:
    numeric: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        numeric.append(number)
    return numeric


def _coordinate_order(values: Sequence[object]) -> dict[str, object]:
    numeric = _numeric_values(values)
    if numeric is None or not numeric:
        return {
            "first": values[0] if values else None,
            "last": values[-1] if values else None,
            "order": "not-numeric",
            "regular_step": None,
        }
    differences = [right - left for left, right in zip(numeric, numeric[1:])]
    if not differences:
        order = "singleton"
        regular_step: float | None = None
    elif all(value > 0 for value in differences):
        order = "ascending"
        regular_step = (
            differences[0]
            if all(math.isclose(value, differences[0], abs_tol=1e-10) for value in differences)
            else None
        )
    elif all(value < 0 for value in differences):
        order = "descending"
        regular_step = (
            differences[0]
            if all(math.isclose(value, differences[0], abs_tol=1e-10) for value in differences)
            else None
        )
    else:
        order = "unordered"
        regular_step = None
    return {
        "first": numeric[0],
        "last": numeric[-1],
        "order": order,
        "regular_step": regular_step,
    }


def _array_metadata(variable: Any, include_values: bool) -> dict[str, object]:
    attributes = _attributes(variable.attrs)
    metadata: dict[str, object] = {
        "dimensions": [str(value) for value in variable.dims],
        "shape": [int(value) for value in variable.shape],
        "dtype": str(variable.dtype),
        "attributes": attributes,
        "units": attributes.get("units"),
        "nodata": attributes.get("_FillValue", attributes.get("missing_value")),
    }
    if include_values:
        values = _coordinate_values(variable)
        metadata["values"] = values
        metadata["order"] = _coordinate_order(values)
    return metadata


def summarize_dataset(dataset: Any) -> dict[str, Any]:
    """Return header and coordinate evidence without reading climate arrays."""

    return {
        "dimensions": {str(key): int(value) for key, value in dataset.sizes.items()},
        "coordinates": {
            str(name): _array_metadata(variable, include_values=True)
            for name, variable in dataset.coords.items()
        },
        "data_variables": {
            str(name): _array_metadata(variable, include_values=False)
            for name, variable in dataset.data_vars.items()
        },
        "global_attributes": _attributes(dataset.attrs),
    }


def _read_single_netcdf_metadata(path: Path, xr: Any) -> dict[str, Any]:
    try:
        with xr.open_dataset(path, decode_cf=False, mask_and_scale=False) as dataset:
            return summarize_dataset(dataset)
    except Exception as error:
        raise InspectionError(f"{path}: NetCDF inspection failed: {error}") from error


def _member_structure(metadata: Mapping[str, Any]) -> dict[str, Any]:
    coordinates = metadata.get("coordinates")
    coordinate_structures: dict[str, Any] = {}
    if isinstance(coordinates, dict):
        for name, value in coordinates.items():
            if isinstance(name, str) and isinstance(value, dict):
                structure = {
                    key: item for key, item in value.items() if key not in {"values", "order"}
                }
                attributes = structure.get("attributes")
                standard_name = (
                    attributes.get("standard_name") if isinstance(attributes, dict) else None
                )
                if name.lower() == "time" or standard_name == "time":
                    structure.pop("units", None)
                    if isinstance(attributes, dict):
                        structure["attributes"] = {
                            key: item for key, item in attributes.items() if key != "units"
                        }
                coordinate_structures[name] = structure
    return {
        "dimensions": metadata.get("dimensions"),
        "coordinates": coordinate_structures,
        "data_variables": metadata.get("data_variables"),
    }


def safe_netcdf_archive_members(
    archive: zipfile.ZipFile,
    path: Path,
) -> list[zipfile.ZipInfo]:
    """Return bounded, path-safe NetCDF members from a provider ZIP response."""

    members = [member for member in archive.infolist() if not member.is_dir()]
    if not members:
        raise InspectionError(f"{path}: ZIP archive contains no files")
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise InspectionError(
            f"{path}: ZIP archive has {len(members)} files; "
            f"inspection limit is {MAX_ARCHIVE_MEMBERS}"
        )
    names = [member.filename for member in members]
    if len(set(names)) != len(names):
        raise InspectionError(f"{path}: ZIP archive contains duplicate member names")
    total_size = sum(member.file_size for member in members)
    if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise InspectionError(
            f"{path}: ZIP archive expands to {total_size} bytes; "
            f"inspection limit is {MAX_ARCHIVE_UNCOMPRESSED_BYTES}"
        )
    for member in members:
        member_path = PurePosixPath(member.filename)
        if (
            member_path.is_absolute()
            or ".." in member_path.parts
            or member_path.suffix.lower() not in {".nc", ".nc4"}
        ):
            raise InspectionError(
                f"{path}: ZIP archive contains unsafe or non-NetCDF member {member.filename!r}"
            )
        if member.flag_bits & 0x1:
            raise InspectionError(f"{path}: ZIP archive member {member.filename!r} is encrypted")
    return members


def _read_zip_netcdf_metadata(path: Path, xr: Any) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            members = safe_netcdf_archive_members(archive, path)
            preflight_archive_extraction(
                load_storage_policy(),
                sum(member.file_size for member in members),
                operation=f"archive_inspection:{path.name}",
            )
            member_metadata: list[dict[str, Any]] = []
            with tempfile.TemporaryDirectory(prefix="thermal-drought-inspect-") as temp:
                temp_root = Path(temp)
                for index, member in enumerate(members):
                    extracted = temp_root / f"{index:03d}.nc"
                    with archive.open(member) as source, extracted.open("wb") as target:
                        shutil.copyfileobj(source, target)
                    metadata = _read_single_netcdf_metadata(extracted, xr)
                    member_metadata.append(metadata)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise InspectionError(f"{path}: ZIP inspection failed: {error}") from error

    representative = member_metadata[0]
    representative_structure = _member_structure(representative)
    for index, metadata in enumerate(member_metadata[1:], start=1):
        if _member_structure(metadata) != representative_structure:
            raise InspectionError(
                f"{path}: ZIP member {members[index].filename!r} has a different "
                "NetCDF structure from the first member"
            )
        grid = compare_grids(representative, metadata)
        if not grid["compatible"] or grid["required_transformations"]:
            raise InspectionError(
                f"{path}: ZIP member {members[index].filename!r} has a different "
                "spatial grid from the first member"
            )

    result = dict(representative)
    result["archive"] = {
        "format": "zip",
        "member_count": len(members),
        "total_uncompressed_bytes": sum(member.file_size for member in members),
        "member_names": [member.filename for member in members],
        "members": [
            {
                "name": member.filename,
                "compressed_bytes": member.compress_size,
                "uncompressed_bytes": member.file_size,
                "crc32": f"{member.CRC:08x}",
            }
            for member in members
        ],
        "member_structures_consistent": True,
        "spatial_grids_consistent": True,
    }
    return result


def read_netcdf_metadata(path: Path) -> dict[str, Any]:
    """Read direct NetCDF or ZIP-packaged NetCDF headers without climate arrays."""

    try:
        xr = importlib.import_module("xarray")
    except ModuleNotFoundError as error:
        raise InspectionError(
            "xarray is not installed; install the pipeline data extra before inspection"
        ) from error

    if zipfile.is_zipfile(path):
        return _read_zip_netcdf_metadata(path, xr)
    return _read_single_netcdf_metadata(path, xr)


def _safe_artifact_path(raw_root: Path, receipt: Mapping[str, Any]) -> Path:
    file_metadata = receipt.get("file")
    if not isinstance(file_metadata, dict):
        raise InspectionError("receipt has no file metadata object")
    relative_value = file_metadata.get("path")
    if not isinstance(relative_value, str):
        raise InspectionError("receipt file path is missing")
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise InspectionError(f"receipt contains unsafe artifact path: {relative_value}")
    root = raw_root.resolve()
    target = (raw_root / relative).resolve()
    if target != root and root not in target.parents:
        raise InspectionError(f"artifact escapes raw root: {relative_value}")
    return target


def _verify_artifact(raw_root: Path, receipt: Mapping[str, Any]) -> Path:
    target = _safe_artifact_path(raw_root, receipt)
    file_metadata = receipt["file"]
    expected_size = file_metadata.get("byte_size")
    expected_digest = file_metadata.get("sha256")
    if not isinstance(expected_size, int) or not isinstance(expected_digest, str):
        raise InspectionError(f"{target}: receipt checksum metadata is invalid")
    if not target.is_file():
        raise InspectionError(f"{target}: verified artifact is missing")
    if target.stat().st_size != expected_size or sha256_file(target) != expected_digest:
        raise InspectionError(f"{target}: artifact no longer matches its receipt")
    return target


def _receipt_plan_issues(
    raw_root: Path,
    receipt_file: Path,
    receipt: Mapping[str, Any],
    request: AcquisitionRequest,
) -> list[str]:
    """Return every way a receipt diverges from one exact planned request."""

    expected_target = raw_root / request.target_relative_path
    expected_receipt = receipt_path(expected_target).resolve()
    issues: list[str] = []
    if receipt_file.resolve() != expected_receipt:
        issues.append(
            "receipt path does not match planned sidecar "
            f"{expected_receipt.relative_to(raw_root.resolve())}"
        )

    expected_values: dict[str, object] = {
        "schema_version": "1.1",
        "request_id": request.request_id,
        "dataset_id": request.dataset_id,
        "variable_id": request.variable_id,
        "product_version": SOURCE_METADATA[request.dataset_id].product_version,
        "request": request.request,
        "request_sha256": request_sha256(request),
        "period": {"year": request.year, "month": request.month},
        "region": {
            "id": request.region.id,
            "label": request.region.label,
            "purpose": request.region.purpose,
        },
        "source": SOURCE_METADATA[request.dataset_id].as_dict(),
    }
    for field, expected in expected_values.items():
        if receipt.get(field) != expected:
            issues.append(f"{field} does not match the planned request")

    file_metadata = receipt.get("file")
    if not isinstance(file_metadata, dict):
        issues.append("file metadata is not an object")
    elif file_metadata.get("path") != request.target_relative_path.as_posix():
        issues.append("file.path does not match the planned target")
    return issues


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.part")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _axis_coordinate(metadata: Mapping[str, Any], axis: str) -> tuple[str, dict[str, Any]]:
    coordinates = metadata.get("coordinates")
    if not isinstance(coordinates, dict):
        raise InspectionError("observed metadata has no coordinates object")
    aliases = {
        "latitude": {"latitude", "lat"},
        "longitude": {"longitude", "lon"},
    }[axis]
    for name, coordinate in coordinates.items():
        if not isinstance(name, str) or not isinstance(coordinate, dict):
            continue
        attributes = coordinate.get("attributes")
        standard_name = attributes.get("standard_name") if isinstance(attributes, dict) else None
        axis_name = attributes.get("axis") if isinstance(attributes, dict) else None
        if (
            name.lower() in aliases
            or standard_name == axis
            or axis_name == ("Y" if axis == "latitude" else "X")
        ):
            return name, coordinate
    raise InspectionError(f"observed metadata has no identifiable {axis} coordinate")


def _coordinate_numbers(metadata: Mapping[str, Any], axis: str) -> tuple[str, list[float]]:
    name, coordinate = _axis_coordinate(metadata, axis)
    values = coordinate.get("values")
    numeric = _numeric_values(values) if isinstance(values, list) else None
    if numeric is None or not numeric:
        raise InspectionError(f"{name}: {axis} coordinate values are not finite numbers")
    return name, numeric


def _same_cells(left: Sequence[float], right: Sequence[float]) -> bool:
    return len(left) == len(right) and all(
        math.isclose(left_value, right_value, abs_tol=1e-9)
        for left_value, right_value in zip(sorted(left), sorted(right))
    )


def _normalized_longitudes(values: Sequence[float]) -> list[float]:
    return [((value + 180.0) % 360.0) - 180.0 for value in values]


def compare_grids(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare cell centers while documenting harmless coordinate transformations."""

    left_latitude_name, left_latitudes = _coordinate_numbers(left, "latitude")
    right_latitude_name, right_latitudes = _coordinate_numbers(right, "latitude")
    left_longitude_name, left_longitudes = _coordinate_numbers(left, "longitude")
    right_longitude_name, right_longitudes = _coordinate_numbers(right, "longitude")

    latitude_cells_match = _same_cells(left_latitudes, right_latitudes)
    raw_longitude_cells_match = _same_cells(left_longitudes, right_longitudes)
    normalized_longitude_cells_match = _same_cells(
        _normalized_longitudes(left_longitudes),
        _normalized_longitudes(right_longitudes),
    )
    transformations: list[str] = []
    if latitude_cells_match and left_latitudes != right_latitudes:
        transformations.append("reorder latitude")
    if normalized_longitude_cells_match and not raw_longitude_cells_match:
        transformations.append("normalize longitude to [-180, 180)")
    elif raw_longitude_cells_match and left_longitudes != right_longitudes:
        transformations.append("reorder longitude")

    reasons: list[str] = []
    if not latitude_cells_match:
        reasons.append("latitude cell centers differ")
    if not normalized_longitude_cells_match:
        reasons.append("longitude cell centers differ after convention normalization")
    return {
        "compatible": latitude_cells_match and normalized_longitude_cells_match,
        "latitude": {
            "left_name": left_latitude_name,
            "right_name": right_latitude_name,
            "left_values": left_latitudes,
            "right_values": right_latitudes,
            "cell_centers_match": latitude_cells_match,
        },
        "longitude": {
            "left_name": left_longitude_name,
            "right_name": right_longitude_name,
            "left_values": left_longitudes,
            "right_values": right_longitudes,
            "raw_cell_centers_match": raw_longitude_cells_match,
            "normalized_cell_centers_match": normalized_longitude_cells_match,
        },
        "required_transformations": transformations,
        "mismatch_reasons": reasons,
    }


def _artifact_summary(
    receipt_file: Path,
    receipt: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    period = receipt.get("period")
    region = receipt.get("region")
    if not isinstance(period, dict) or not isinstance(region, dict):
        raise InspectionError(f"{receipt_file}: receipt has no period or region metadata")
    region_id = region.get("id")
    year = period.get("year")
    month = period.get("month")
    if not isinstance(region_id, str):
        raise InspectionError(f"{receipt_file}: receipt region id is invalid")
    if year is not None and not isinstance(year, int):
        raise InspectionError(f"{receipt_file}: receipt year is invalid")
    if not isinstance(month, int) or not 1 <= month <= 12:
        raise InspectionError(f"{receipt_file}: receipt month is invalid")
    return {
        "request_id": receipt.get("request_id"),
        "variable_id": receipt.get("variable_id"),
        "dataset_id": receipt.get("dataset_id"),
        "fixture": receipt.get("fixture"),
        "region_id": region_id,
        "year": year,
        "month": month,
        "retrieved_at": receipt.get("retrieved_at"),
        "retrieval_duration_seconds": receipt.get("retrieval_duration_seconds"),
        "file": receipt.get("file"),
        "observed_netcdf_metadata": metadata,
    }


def _observed_plan_issues(
    request: AcquisitionRequest,
    metadata: Mapping[str, Any],
) -> list[str]:
    archive = metadata.get("archive")
    if not isinstance(archive, dict):
        return []
    member_count = archive.get("member_count")
    member_names = archive.get("member_names")
    if not isinstance(member_count, int) or not isinstance(member_names, list):
        return ["observed ZIP metadata has invalid member accounting"]

    issues: list[str] = []
    if request.variable_id == "utci_daymax_median":
        if request.year is None:
            return ["UTCI request has no analysis year"]
        expected_days = monthrange(request.year, request.month)[1]
        if member_count != expected_days:
            issues.append(
                f"UTCI archive has {member_count} daily members; expected {expected_days}"
            )
        for day in range(1, expected_days + 1):
            date_token = f"{request.year:04d}{request.month:02d}{day:02d}"
            matches = [
                name
                for name in member_names
                if isinstance(name, str) and date_token in PurePosixPath(name).name
            ]
            if len(matches) != 1:
                issues.append(
                    f"UTCI archive expected exactly one member for {date_token}; "
                    f"found {len(matches)}"
                )
    elif member_count != 1:
        issues.append(f"{request.variable_id} archive has {member_count} members; expected 1")
    return issues


def _pair_comparisons(
    artifacts: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    indexed = {
        (
            artifact.get("region_id"),
            artifact.get("year"),
            artifact.get("month"),
            artifact.get("variable_id"),
        ): artifact
        for artifact in artifacts
    }
    periods: set[tuple[str, int | None, int]] = set()
    for artifact in artifacts:
        if artifact.get("variable_id") not in {"utci_daymax_median", "spei_3"}:
            continue
        region_id = artifact.get("region_id")
        year = artifact.get("year")
        month = artifact.get("month")
        if (
            isinstance(region_id, str)
            and (year is None or isinstance(year, int))
            and isinstance(month, int)
        ):
            periods.add((region_id, year, month))
    ordered_periods = sorted(
        periods,
        key=lambda value: (value[0], -1 if value[1] is None else value[1], value[2]),
    )
    comparisons: list[dict[str, Any]] = []
    missing: list[str] = []
    for region_id, year, month in ordered_periods:
        utci = indexed.get((region_id, year, month, "utci_daymax_median"))
        spei = indexed.get((region_id, year, month, "spei_3"))
        label = f"{region_id}/{year}/{month:02d}"
        if utci is None or spei is None:
            absent = "UTCI" if utci is None else "SPEI-3"
            missing.append(f"{label}: missing {absent} artifact")
            continue
        utci_metadata = utci["observed_netcdf_metadata"]
        spei_metadata = spei["observed_netcdf_metadata"]
        comparisons.append(
            {
                "region_id": region_id,
                "year": year,
                "month": month,
                "utci_request_id": utci.get("request_id"),
                "spei_request_id": spei.get("request_id"),
                "grid": compare_grids(utci_metadata, spei_metadata),
            }
        )
    return comparisons, missing


def _quality_comparisons(
    artifacts: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    quality_by_region_month = {
        (artifact.get("region_id"), artifact.get("month")): artifact
        for artifact in artifacts
        if artifact.get("variable_id") == "spei_3_quality"
    }
    comparisons: list[dict[str, Any]] = []
    missing: list[str] = []
    for spei in artifacts:
        if spei.get("variable_id") != "spei_3":
            continue
        region_id = spei.get("region_id")
        year = spei.get("year")
        month = spei.get("month")
        if not isinstance(region_id, str) or not isinstance(month, int):
            continue
        quality = quality_by_region_month.get((region_id, month))
        label = f"{region_id}/{year}/{month:02d}"
        if quality is None:
            missing.append(f"{label}: missing SPEI-3 quality artifact")
            continue
        comparisons.append(
            {
                "region_id": region_id,
                "year": year,
                "month": month,
                "spei_request_id": spei.get("request_id"),
                "quality_request_id": quality.get("request_id"),
                "grid": compare_grids(
                    spei["observed_netcdf_metadata"],
                    quality["observed_netcdf_metadata"],
                ),
            }
        )
    return comparisons, missing


def inspect_raw_root(
    raw_root: Path,
    reader: MetadataReader = read_netcdf_metadata,
    *,
    now: Callable[[], datetime] | None = None,
    allow_fixtures: bool = False,
    expected_requests: Sequence[AcquisitionRequest] | None = None,
) -> dict[str, Any]:
    """Verify and inspect all acquisition receipts, then compare UTCI/SPEI grids."""

    receipt_files = sorted(raw_root.rglob("*.nc.receipt.json")) if raw_root.is_dir() else []
    inspected_at = (now or (lambda: datetime.now(timezone.utc)))()
    if inspected_at.tzinfo is None:
        raise ValueError("inspection timestamp must include a timezone")

    expected_by_id: dict[str, AcquisitionRequest] | None = None
    expected_plan_sha256: str | None = None
    if expected_requests is not None:
        expected_plan_sha256 = plan_sha256(expected_requests)
        expected_by_id = {request.request_id: request for request in expected_requests}

    loaded_receipts: list[tuple[Path, dict[str, Any]]] = []
    request_id_counts: dict[str, int] = {}
    for receipt_file in receipt_files:
        try:
            receipt_value = json.loads(receipt_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise InspectionError(f"{receipt_file}: receipt cannot be read: {error}") from error
        if not isinstance(receipt_value, dict):
            raise InspectionError(f"{receipt_file}: receipt must be a JSON object")
        fixture = receipt_value.get("fixture")
        if fixture is not False and not (fixture is True and allow_fixtures):
            raise InspectionError(
                f"{receipt_file}: fixture receipts are not valid official-data evidence"
            )
        request_id = receipt_value.get("request_id")
        if isinstance(request_id, str):
            request_id_counts[request_id] = request_id_counts.get(request_id, 0) + 1
        loaded_receipts.append((receipt_file, receipt_value))

    duplicate_request_ids = sorted(
        request_id for request_id, count in request_id_counts.items() if count > 1
    )
    unexpected_artifacts: list[str] = []
    receipt_plan_issues: list[str] = []
    pending_updates: list[tuple[Path, dict[str, Any]]] = []
    artifacts: list[dict[str, Any]] = []
    for receipt_file, receipt_value in loaded_receipts:
        expected_request: AcquisitionRequest | None = None
        request_id = receipt_value.get("request_id")
        if not isinstance(request_id, str):
            receipt_plan_issues.append(f"{receipt_file}: request_id is missing or invalid")
            continue
        if request_id in duplicate_request_ids:
            receipt_plan_issues.append(f"{receipt_file}: duplicate request_id {request_id!r}")
            continue
        if expected_by_id is not None:
            expected_request = expected_by_id.get(request_id)
            if expected_request is None:
                unexpected_artifacts.append(request_id)
                continue
            issues = _receipt_plan_issues(
                raw_root,
                receipt_file,
                receipt_value,
                expected_request,
            )
            if issues:
                receipt_plan_issues.extend(f"{receipt_file}: {issue}" for issue in issues)
                continue
        target = _verify_artifact(raw_root, receipt_value)
        metadata = reader(target)
        if not isinstance(metadata, dict):
            raise InspectionError(f"{target}: metadata reader did not return an object")
        if expected_request is not None:
            observed_issues = _observed_plan_issues(expected_request, metadata)
            if observed_issues:
                receipt_plan_issues.extend(f"{receipt_file}: {issue}" for issue in observed_issues)
                continue
        updated_receipt = dict(receipt_value)
        updated_receipt["observed_netcdf_metadata"] = metadata
        updated_receipt["inspected_at"] = inspected_at.astimezone(timezone.utc).isoformat()
        updated_receipt["metadata_note"] = (
            "Observed metadata was read from the checksum-verified artifact or its "
            "safely unpacked NetCDF member headers. Coordinate arrays were read for "
            "cell-center comparison; climate arrays were not loaded by this inspection."
        )
        pending_updates.append((receipt_file, updated_receipt))
        artifacts.append(_artifact_summary(receipt_file, updated_receipt, metadata))

    comparisons, missing_pairs = _pair_comparisons(artifacts)
    quality_comparisons, missing_quality_pairs = _quality_comparisons(artifacts)
    expected_request_ids = set(expected_by_id) if expected_by_id is not None else set()
    observed_request_ids = {
        artifact["request_id"]
        for artifact in artifacts
        if isinstance(artifact.get("request_id"), str)
    }
    missing_artifacts = sorted(expected_request_ids - observed_request_ids)
    fixtures_present = any(artifact["fixture"] is True for artifact in artifacts)
    all_grids_compatible = bool(comparisons) and all(
        comparison["grid"]["compatible"] is True for comparison in comparisons
    )
    all_quality_grids_compatible = bool(quality_comparisons) and all(
        comparison["grid"]["compatible"] is True for comparison in quality_comparisons
    )
    complete = (
        bool(artifacts)
        and expected_requests is not None
        and not fixtures_present
        and not missing_artifacts
        and not unexpected_artifacts
        and not duplicate_request_ids
        and not receipt_plan_issues
        and not missing_pairs
        and not missing_quality_pairs
        and all_grids_compatible
        and all_quality_grids_compatible
    )
    if pending_updates:
        policy = load_storage_policy()
        serialized_bytes = sum(
            len((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            for _, value in pending_updates
        )
        preflight_managed_write(
            policy,
            "raw",
            managed_scope_root(policy, "raw", raw_root),
            serialized_bytes,
            operation="inspection_receipt_updates",
        )
    for receipt_file, updated_receipt in pending_updates:
        _write_json_atomic(receipt_file, updated_receipt)
    return {
        "schema_version": "1.0",
        "generated_at": inspected_at.astimezone(timezone.utc).isoformat(),
        "raw_root": str(raw_root),
        "artifact_count": len(artifacts),
        "official_evidence": bool(artifacts) and not fixtures_present,
        "artifacts": artifacts,
        "expected_plan_sha256": expected_plan_sha256,
        "expected_request_count": (
            len(expected_request_ids) if expected_by_id is not None else None
        ),
        "missing_artifacts": missing_artifacts,
        "unexpected_artifacts": sorted(unexpected_artifacts),
        "duplicate_request_ids": duplicate_request_ids,
        "receipt_plan_issues": receipt_plan_issues,
        "pair_comparisons": comparisons,
        "missing_pairs": missing_pairs,
        "quality_comparisons": quality_comparisons,
        "missing_quality_pairs": missing_quality_pairs,
        "complete": complete,
        "completion_note": (
            "Complete requires an explicit fingerprinted request plan, exactly one "
            "checksum-verified non-fixture receipt bound to every planned request and "
            "target, no extra receipts, paired UTCI/SPEI-3/quality periods, and "
            "compatible observed cell centers."
        ),
    }
