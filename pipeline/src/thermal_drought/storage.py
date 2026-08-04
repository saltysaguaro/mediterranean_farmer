"""Fail-closed local storage policy, inventory, and write preflights."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from thermal_drought.months import hex_to_mask


class StoragePolicyError(ValueError):
    """Raised when the checked-in storage policy is invalid."""


class StorageLimitError(RuntimeError):
    """Raised before a write that would violate a storage guardrail."""

    def __init__(
        self,
        operation: str,
        reason_code: str,
        detail: str,
        report: Mapping[str, object],
    ) -> None:
        super().__init__(detail)
        self.operation = operation
        self.reason_code = reason_code
        self.detail = detail
        self.report = dict(report)

    def as_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "storage": self.report,
        }


@dataclass(frozen=True)
class DirectoryPolicy:
    id: str
    path: Path
    maximum_bytes: int
    retention: str


@dataclass(frozen=True)
class DiskCapacity:
    total: int
    used: int
    free: int

    @property
    def used_fraction(self) -> float:
        return self.used / self.total


@dataclass(frozen=True)
class StoragePolicy:
    schema_version: str
    policy_id: str
    minimum_free_reserve_bytes: int
    maximum_volume_used_fraction: float
    processing_peak_multiplier: float
    maximum_local_backfill_years: int
    maximum_acquisition_partition_bytes: int
    acquisition_receipt_reservation_bytes: int
    fixture_partition_reservation_bytes: int
    normalization_working_reservation_bytes: int
    normalization_output_reservation_bytes: int
    directories: Mapping[str, DirectoryPolicy]
    annual_estimates: Mapping[str, int]
    annual_estimate_basis: str
    temporal_retention: Mapping[str, str]
    maximum_precomputed_month_masks: int
    prewarm_month_masks: tuple[str, ...]
    arbitrary_month_masks: str
    automatic_deletion: bool
    object_storage_required_before_multi_year_backfill: bool


def policy_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "storage-policy.json"


def _object(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StoragePolicyError(f"{location} must be an object")
    return value


def _integer(value: object, location: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise StoragePolicyError(f"{location} must be an integer at least {minimum}")
    return value


def _number(value: object, location: str, *, minimum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StoragePolicyError(f"{location} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < minimum:
        raise StoragePolicyError(f"{location} must be at least {minimum}")
    return numeric


def _relative_path(value: object, location: str) -> Path:
    if not isinstance(value, str) or not value:
        raise StoragePolicyError(f"{location} must be a non-empty path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise StoragePolicyError(f"{location} must stay within the repository")
    return Path(*pure.parts)


def load_storage_policy(path: Path | None = None) -> StoragePolicy:
    selected = path or policy_path()
    try:
        raw = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StoragePolicyError(f"{selected}: cannot read storage policy: {error}") from error
    root = _object(raw, str(selected))
    if root.get("schema_version") != "1.0":
        raise StoragePolicyError(f"{selected}: unsupported schema version")
    policy_id = root.get("policy_id")
    if not isinstance(policy_id, str) or not policy_id:
        raise StoragePolicyError("policy_id must be a non-empty string")

    raw_directories = _object(root.get("managed_directories"), "managed_directories")
    directories: dict[str, DirectoryPolicy] = {}
    for directory_id, raw_rule in raw_directories.items():
        if not isinstance(directory_id, str) or not directory_id:
            raise StoragePolicyError("managed directory IDs must be non-empty strings")
        rule = _object(raw_rule, f"managed_directories.{directory_id}")
        retention = rule.get("retention")
        if not isinstance(retention, str) or not retention:
            raise StoragePolicyError(
                f"managed_directories.{directory_id}.retention must be non-empty"
            )
        directories[directory_id] = DirectoryPolicy(
            id=directory_id,
            path=_relative_path(
                rule.get("path"),
                f"managed_directories.{directory_id}.path",
            ),
            maximum_bytes=_integer(
                rule.get("maximum_bytes"),
                f"managed_directories.{directory_id}.maximum_bytes",
                minimum=1,
            ),
            retention=retention,
        )
    required_directories = {"raw", "canonical", "published", "composite_cache", "tiles"}
    if set(directories) != required_directories:
        raise StoragePolicyError(
            "managed_directories must define raw, canonical, published, composite_cache, and tiles"
        )

    raw_estimates = _object(root.get("annual_estimates"), "annual_estimates")
    estimate_names = (
        "daily_utci_source_bytes",
        "monthly_spei_source_bytes",
        "monthly_canonical_utci_spei_bytes",
    )
    annual_estimates = {
        name: _integer(raw_estimates.get(name), f"annual_estimates.{name}", minimum=1)
        for name in estimate_names
    }
    basis = raw_estimates.get("basis")
    if not isinstance(basis, str) or not basis:
        raise StoragePolicyError("annual_estimates.basis must be non-empty")

    raw_retention = _object(root.get("temporal_retention"), "temporal_retention")
    temporal_retention: dict[str, str] = {}
    for key, value in raw_retention.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value:
            raise StoragePolicyError("temporal_retention values must be non-empty strings")
        temporal_retention[key] = value
    required_retention = {
        "utci_source_frequency": "daily maximum",
        "utci_published_frequency": "monthly median of daily maximum",
        "spei_source_frequency": "provider monthly SPEI-3",
        "spei_published_frequency": "monthly",
        "daily_source_policy": (
            "Archive outside local serving storage after checksum and monthly-product validation."
        ),
        "serving_store_policy": "Monthly layers only; selected UI months receive equal weight.",
    }
    if temporal_retention != required_retention:
        raise StoragePolicyError(
            "temporal_retention must preserve the locked daily-source/monthly-serving contract"
        )

    raw_cache = _object(root.get("cache_policy"), "cache_policy")
    raw_masks = raw_cache.get("prewarm_month_masks")
    if not isinstance(raw_masks, list) or not raw_masks:
        raise StoragePolicyError("cache_policy.prewarm_month_masks must be non-empty")
    masks: list[str] = []
    for value in raw_masks:
        if not isinstance(value, str):
            raise StoragePolicyError("prewarm month masks must be strings")
        try:
            hex_to_mask(value)
        except ValueError as error:
            raise StoragePolicyError(f"invalid prewarm month mask {value!r}") from error
        masks.append(value)
    maximum_masks = _integer(
        raw_cache.get("maximum_precomputed_month_masks"),
        "cache_policy.maximum_precomputed_month_masks",
        minimum=1,
    )
    if len(set(masks)) != len(masks) or len(masks) > maximum_masks:
        raise StoragePolicyError("prewarm masks must be unique and within the configured maximum")
    expected_masks = (
        "001",
        "002",
        "004",
        "008",
        "010",
        "020",
        "040",
        "080",
        "100",
        "200",
        "400",
        "800",
        "803",
        "01c",
        "0e0",
        "700",
        "fff",
    )
    if tuple(masks) != expected_masks or maximum_masks != len(expected_masks):
        raise StoragePolicyError(
            "cache prewarming must stay limited to 12 single months, 4 seasons, and all months"
        )
    arbitrary = raw_cache.get("arbitrary_month_masks")
    if arbitrary != "on_demand_only":
        raise StoragePolicyError("arbitrary month masks must be on-demand only")
    automatic_deletion = raw_cache.get("automatic_deletion")
    if automatic_deletion is not False:
        raise StoragePolicyError("automatic cache deletion must remain disabled until reviewed")

    used_fraction = _number(
        root.get("maximum_volume_used_fraction"),
        "maximum_volume_used_fraction",
        minimum=0.01,
    )
    if used_fraction > 1:
        raise StoragePolicyError("maximum_volume_used_fraction cannot exceed one")
    if root.get("object_storage_required_before_multi_year_backfill") is not True:
        raise StoragePolicyError("object storage must be required before a multi-year backfill")
    return StoragePolicy(
        schema_version="1.0",
        policy_id=policy_id,
        minimum_free_reserve_bytes=_integer(
            root.get("minimum_free_reserve_bytes"),
            "minimum_free_reserve_bytes",
            minimum=1,
        ),
        maximum_volume_used_fraction=used_fraction,
        processing_peak_multiplier=_number(
            root.get("processing_peak_multiplier"),
            "processing_peak_multiplier",
            minimum=1,
        ),
        maximum_local_backfill_years=_integer(
            root.get("maximum_local_backfill_years"),
            "maximum_local_backfill_years",
            minimum=1,
        ),
        maximum_acquisition_partition_bytes=_integer(
            root.get("maximum_acquisition_partition_bytes"),
            "maximum_acquisition_partition_bytes",
            minimum=1,
        ),
        acquisition_receipt_reservation_bytes=_integer(
            root.get("acquisition_receipt_reservation_bytes"),
            "acquisition_receipt_reservation_bytes",
            minimum=1,
        ),
        fixture_partition_reservation_bytes=_integer(
            root.get("fixture_partition_reservation_bytes"),
            "fixture_partition_reservation_bytes",
            minimum=1,
        ),
        normalization_working_reservation_bytes=_integer(
            root.get("normalization_working_reservation_bytes"),
            "normalization_working_reservation_bytes",
            minimum=1,
        ),
        normalization_output_reservation_bytes=_integer(
            root.get("normalization_output_reservation_bytes"),
            "normalization_output_reservation_bytes",
            minimum=1,
        ),
        directories=directories,
        annual_estimates=annual_estimates,
        annual_estimate_basis=basis,
        temporal_retention=temporal_retention,
        maximum_precomputed_month_masks=maximum_masks,
        prewarm_month_masks=tuple(masks),
        arbitrary_month_masks=arbitrary,
        automatic_deletion=automatic_deletion,
        object_storage_required_before_multi_year_backfill=True,
    )


def directory_size(path: Path) -> int:
    """Return regular-file bytes without following symlinks."""

    if not path.exists() or path.is_symlink():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    pending = [path]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except FileNotFoundError:
            continue
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
            except FileNotFoundError:
                continue
    return total


def disk_capacity(path: Path) -> DiskCapacity:
    selected = path.resolve()
    while not selected.exists():
        if selected.parent == selected:
            raise StoragePolicyError(f"no existing filesystem anchor for {path}")
        selected = selected.parent
    usage = shutil.disk_usage(selected)
    return DiskCapacity(total=usage.total, used=usage.used, free=usage.free)


def _human_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.2f} {unit}"
        amount /= 1024
    return f"{amount:.2f} TiB"


def _disk_report(disk: DiskCapacity) -> dict[str, object]:
    return {
        "total_bytes": disk.total,
        "used_bytes": disk.used,
        "free_bytes": disk.free,
        "used_fraction": round(disk.used_fraction, 6),
        "free_display": _human_bytes(disk.free),
    }


def storage_status(
    repository_root: Path,
    policy: StoragePolicy,
    *,
    disk: DiskCapacity | None = None,
) -> dict[str, object]:
    root = repository_root.resolve()
    capacity = disk or disk_capacity(root)
    directories: list[dict[str, object]] = []
    violations: list[dict[str, object]] = []
    for rule in policy.directories.values():
        size = directory_size(root / rule.path)
        approved = size <= rule.maximum_bytes
        record = {
            "id": rule.id,
            "path": rule.path.as_posix(),
            "bytes": size,
            "display": _human_bytes(size),
            "maximum_bytes": rule.maximum_bytes,
            "maximum_display": _human_bytes(rule.maximum_bytes),
            "within_quota": approved,
            "retention": rule.retention,
        }
        directories.append(record)
        if not approved:
            violations.append(
                {
                    "reason_code": "managed_quota_exceeded",
                    "directory": rule.id,
                    "detail": f"{rule.id} storage exceeds its configured quota",
                }
            )
    if capacity.free < policy.minimum_free_reserve_bytes:
        violations.append(
            {
                "reason_code": "free_space_reserve",
                "detail": "free space is below the untouchable reserve",
            }
        )
    if capacity.used_fraction > policy.maximum_volume_used_fraction:
        violations.append(
            {
                "reason_code": "volume_high_watermark",
                "detail": "volume use exceeds the configured high-water mark",
            }
        )
    return {
        "schema_version": "1.0",
        "status": "ok" if not violations else "blocked",
        "approved": not violations,
        "policy_id": policy.policy_id,
        "disk": _disk_report(capacity),
        "minimum_free_reserve_bytes": policy.minimum_free_reserve_bytes,
        "maximum_volume_used_fraction": policy.maximum_volume_used_fraction,
        "managed_directories": directories,
        "violations": violations,
        "temporal_retention": dict(policy.temporal_retention),
        "cache_policy": {
            "maximum_precomputed_month_masks": policy.maximum_precomputed_month_masks,
            "prewarm_month_masks": list(policy.prewarm_month_masks),
            "arbitrary_month_masks": policy.arbitrary_month_masks,
            "automatic_deletion": policy.automatic_deletion,
        },
    }


def storage_policy_report(policy: StoragePolicy) -> dict[str, object]:
    """Return a disk-independent policy validation record for CI."""

    return {
        "schema_version": "1.0",
        "status": "valid",
        "approved": True,
        "policy_id": policy.policy_id,
        "maximum_local_backfill_years": policy.maximum_local_backfill_years,
        "minimum_free_reserve_bytes": policy.minimum_free_reserve_bytes,
        "maximum_volume_used_fraction": policy.maximum_volume_used_fraction,
        "managed_directory_quotas": {
            key: rule.maximum_bytes for key, rule in policy.directories.items()
        },
        "temporal_retention": dict(policy.temporal_retention),
        "cache_policy": {
            "maximum_precomputed_month_masks": policy.maximum_precomputed_month_masks,
            "prewarm_month_masks": list(policy.prewarm_month_masks),
            "arbitrary_month_masks": policy.arbitrary_month_masks,
            "automatic_deletion": policy.automatic_deletion,
        },
        "object_storage_required_before_multi_year_backfill": (
            policy.object_storage_required_before_multi_year_backfill
        ),
    }


def _raise_first(operation: str, report: Mapping[str, object]) -> None:
    violations = report.get("violations")
    if not isinstance(violations, list) or not violations:
        return
    first = violations[0]
    if not isinstance(first, dict):
        raise StorageLimitError(operation, "storage_policy", "storage policy blocked", report)
    raise StorageLimitError(
        operation,
        str(first.get("reason_code", "storage_policy")),
        str(first.get("detail", "storage policy blocked")),
        report,
    )


def preflight_managed_write(
    policy: StoragePolicy,
    managed_id: str,
    target_root: Path,
    planned_bytes: int,
    *,
    operation: str,
    disk: DiskCapacity | None = None,
) -> dict[str, object]:
    if isinstance(planned_bytes, bool) or not isinstance(planned_bytes, int) or planned_bytes < 0:
        raise ValueError("planned bytes must be a non-negative integer")
    try:
        rule = policy.directories[managed_id]
    except KeyError as error:
        raise StoragePolicyError(f"unknown managed directory {managed_id}") from error
    current = directory_size(target_root)
    capacity = disk or disk_capacity(target_root)
    projected_size = current + planned_bytes
    projected_free = capacity.free - planned_bytes
    projected_used_fraction = (capacity.used + planned_bytes) / capacity.total
    violations: list[dict[str, object]] = []
    if projected_size > rule.maximum_bytes:
        violations.append(
            {
                "reason_code": "managed_quota_exceeded",
                "detail": (
                    f"{managed_id} write would reach {_human_bytes(projected_size)}, "
                    f"above its {_human_bytes(rule.maximum_bytes)} quota"
                ),
            }
        )
    if projected_free < policy.minimum_free_reserve_bytes:
        violations.append(
            {
                "reason_code": "free_space_reserve",
                "detail": (
                    f"write would leave {_human_bytes(max(0, projected_free))} free, "
                    f"below the {_human_bytes(policy.minimum_free_reserve_bytes)} reserve"
                ),
            }
        )
    if projected_used_fraction > policy.maximum_volume_used_fraction:
        violations.append(
            {
                "reason_code": "volume_high_watermark",
                "detail": (
                    f"write would use {projected_used_fraction:.1%} of the volume, "
                    f"above the {policy.maximum_volume_used_fraction:.1%} high-water mark"
                ),
            }
        )
    report: dict[str, object] = {
        "schema_version": "1.0",
        "status": "approved" if not violations else "blocked",
        "approved": not violations,
        "policy_id": policy.policy_id,
        "operation": operation,
        "managed_directory": managed_id,
        "current_bytes": current,
        "planned_bytes": planned_bytes,
        "projected_bytes": projected_size,
        "quota_bytes": rule.maximum_bytes,
        "projected_free_bytes": projected_free,
        "projected_volume_used_fraction": round(projected_used_fraction, 6),
        "disk": _disk_report(capacity),
        "violations": violations,
    }
    _raise_first(operation, report)
    return report


def preflight_transient_write(
    policy: StoragePolicy,
    target_root: Path,
    planned_bytes: int,
    *,
    operation: str,
    disk: DiskCapacity | None = None,
) -> dict[str, object]:
    if isinstance(planned_bytes, bool) or not isinstance(planned_bytes, int) or planned_bytes < 0:
        raise ValueError("planned bytes must be a non-negative integer")
    capacity = disk or disk_capacity(target_root)
    projected_free = capacity.free - planned_bytes
    projected_used_fraction = (capacity.used + planned_bytes) / capacity.total
    violations: list[dict[str, object]] = []
    if projected_free < policy.minimum_free_reserve_bytes:
        violations.append(
            {
                "reason_code": "free_space_reserve",
                "detail": (
                    f"temporary write would leave {_human_bytes(max(0, projected_free))} free, "
                    f"below the {_human_bytes(policy.minimum_free_reserve_bytes)} reserve"
                ),
            }
        )
    if projected_used_fraction > policy.maximum_volume_used_fraction:
        violations.append(
            {
                "reason_code": "volume_high_watermark",
                "detail": (
                    f"temporary write would use {projected_used_fraction:.1%} of the volume, "
                    f"above the {policy.maximum_volume_used_fraction:.1%} high-water mark"
                ),
            }
        )
    report: dict[str, object] = {
        "schema_version": "1.0",
        "status": "approved" if not violations else "blocked",
        "approved": not violations,
        "policy_id": policy.policy_id,
        "operation": operation,
        "planned_bytes": planned_bytes,
        "projected_free_bytes": projected_free,
        "projected_volume_used_fraction": round(projected_used_fraction, 6),
        "disk": _disk_report(capacity),
        "violations": violations,
    }
    _raise_first(operation, report)
    return report


def managed_scope_root(
    policy: StoragePolicy,
    managed_id: str,
    target_root: Path,
) -> Path:
    """Use the managed ancestor when a caller writes into one of its children."""

    try:
        directory_name = policy.directories[managed_id].path.name
    except KeyError as error:
        raise StoragePolicyError(f"unknown managed directory {managed_id}") from error
    selected = target_root.resolve()
    for candidate in (selected, *selected.parents):
        if candidate.name == directory_name:
            return candidate
    return selected


def preflight_archive_extraction(
    policy: StoragePolicy,
    expanded_bytes: int,
    *,
    operation: str,
    disk: DiskCapacity | None = None,
) -> dict[str, object]:
    """Reserve exact expanded archive bytes before creating a temporary directory."""

    return preflight_transient_write(
        policy,
        Path(tempfile.gettempdir()),
        expanded_bytes,
        operation=operation,
        disk=disk,
    )


def preflight_normalization(
    policy: StoragePolicy,
    output_root: Path,
    *,
    disk: DiskCapacity | None = None,
) -> dict[str, object]:
    """Reserve bounded working and published space before source inspection mutates receipts."""

    output_scope = managed_scope_root(policy, "published", output_root)
    output_capacity = disk or disk_capacity(output_scope)
    temporary_capacity = disk or disk_capacity(Path(tempfile.gettempdir()))
    preflight_transient_write(
        policy,
        Path(tempfile.gettempdir()),
        (
            policy.normalization_working_reservation_bytes
            + policy.normalization_output_reservation_bytes
        ),
        operation="normalization_working_space",
        disk=temporary_capacity,
    )
    preflight_managed_write(
        policy,
        "published",
        output_scope,
        policy.normalization_output_reservation_bytes,
        operation="normalization_output",
        disk=output_capacity,
    )
    return {
        "schema_version": "1.0",
        "status": "approved",
        "approved": True,
        "policy_id": policy.policy_id,
        "temporal_retention": dict(policy.temporal_retention),
        "working_space": {
            "planned_bytes": (
                policy.normalization_working_reservation_bytes
                + policy.normalization_output_reservation_bytes
            ),
        },
        "published_output": {
            "managed_directory": "published",
            "planned_bytes": policy.normalization_output_reservation_bytes,
            "quota_bytes": policy.directories["published"].maximum_bytes,
        },
    }


def preflight_backfill(
    repository_root: Path,
    policy: StoragePolicy,
    years: int,
    *,
    disk: DiskCapacity | None = None,
) -> dict[str, object]:
    operation = "local_backfill"
    if isinstance(years, bool) or not isinstance(years, int) or years < 1:
        raise ValueError("backfill years must be a positive integer")
    root = repository_root.resolve()
    capacity = disk or disk_capacity(root)
    raw_per_year = (
        policy.annual_estimates["daily_utci_source_bytes"]
        + policy.annual_estimates["monthly_spei_source_bytes"]
    )
    published_per_year = policy.annual_estimates["monthly_canonical_utci_spei_bytes"]
    steady_increment = (raw_per_year + published_per_year) * years
    peak_increment = math.ceil(steady_increment * policy.processing_peak_multiplier)
    violations: list[dict[str, object]] = []
    if years > policy.maximum_local_backfill_years:
        violations.append(
            {
                "reason_code": "backfill_year_limit",
                "detail": (
                    f"requested {years} years; local runs are limited to "
                    f"{policy.maximum_local_backfill_years} year"
                ),
            }
        )
    raw_current = directory_size(root / policy.directories["raw"].path)
    published_current = directory_size(root / policy.directories["published"].path)
    if raw_current + raw_per_year * years > policy.directories["raw"].maximum_bytes:
        violations.append(
            {
                "reason_code": "managed_quota_exceeded",
                "detail": "estimated raw sources would exceed the local raw quota",
            }
        )
    if (
        published_current + published_per_year * years
        > policy.directories["published"].maximum_bytes
    ):
        violations.append(
            {
                "reason_code": "managed_quota_exceeded",
                "detail": "estimated monthly products would exceed the published quota",
            }
        )
    projected_free = capacity.free - peak_increment
    projected_used_fraction = (capacity.used + peak_increment) / capacity.total
    if projected_free < policy.minimum_free_reserve_bytes:
        violations.append(
            {
                "reason_code": "free_space_reserve",
                "detail": "estimated processing peak would consume the free-space reserve",
            }
        )
    if projected_used_fraction > policy.maximum_volume_used_fraction:
        violations.append(
            {
                "reason_code": "volume_high_watermark",
                "detail": "estimated processing peak would cross the volume high-water mark",
            }
        )
    report: dict[str, object] = {
        "schema_version": "1.0",
        "status": "approved" if not violations else "blocked",
        "approved": not violations,
        "policy_id": policy.policy_id,
        "operation": operation,
        "years": years,
        "maximum_local_backfill_years": policy.maximum_local_backfill_years,
        "raw_bytes_per_year": raw_per_year,
        "monthly_published_bytes_per_year": published_per_year,
        "steady_increment_bytes": steady_increment,
        "processing_peak_multiplier": policy.processing_peak_multiplier,
        "peak_increment_bytes": peak_increment,
        "projected_free_bytes": projected_free,
        "projected_volume_used_fraction": round(projected_used_fraction, 6),
        "estimate_basis": policy.annual_estimate_basis,
        "object_storage_required_before_multi_year_backfill": (
            policy.object_storage_required_before_multi_year_backfill
        ),
        "disk": _disk_report(capacity),
        "violations": violations,
    }
    _raise_first(operation, report)
    return report


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=_repository_root())
    parser.add_argument("--policy", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate the policy without inspecting disk state")
    subparsers.add_parser("status", help="inventory managed paths and report current limits")
    preflight = subparsers.add_parser(
        "preflight",
        help="evaluate the conservative local full-year backfill envelope",
    )
    preflight.add_argument("--years", type=int, default=1)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        policy = load_storage_policy(args.policy)
        if args.command == "validate":
            report = storage_policy_report(policy)
        elif args.command == "status":
            report = storage_status(args.repository_root, policy)
        else:
            report = preflight_backfill(args.repository_root, policy, args.years)
    except (OSError, StoragePolicyError, StorageLimitError, ValueError) as error:
        if isinstance(error, StorageLimitError):
            payload = {
                "schema_version": "1.0",
                "status": "blocked",
                "failure": error.as_dict(),
            }
        else:
            payload = {
                "schema_version": "1.0",
                "status": "blocked",
                "failure": {
                    "reason_code": "storage_policy_invalid",
                    "detail": str(error),
                },
            }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
