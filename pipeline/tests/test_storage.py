from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from thermal_drought.storage import (
    DirectoryPolicy,
    DiskCapacity,
    StorageLimitError,
    StoragePolicyError,
    directory_size,
    load_storage_policy,
    main,
    managed_scope_root,
    preflight_backfill,
    preflight_managed_write,
    preflight_normalization,
    preflight_transient_write,
    storage_status,
)

GIB = 1024**3
ROOMY_DISK = DiskCapacity(total=200 * GIB, used=80 * GIB, free=120 * GIB)


def test_checked_in_policy_locks_hybrid_retention_and_bounded_cache() -> None:
    policy = load_storage_policy()

    assert policy.scope_id == "sicily_istat_2026_grid_centers"
    assert policy.maximum_local_backfill_years == 2
    assert policy.maximum_acquisition_partition_bytes == 512 * 1024**2
    assert policy.acquisition_receipt_reservation_bytes == 64 * 1024
    assert policy.temporal_retention["utci_source_frequency"] == "daily maximum"
    assert (
        policy.temporal_retention["utci_published_frequency"] == "monthly median of daily maximum"
    )
    assert policy.temporal_retention["spei_source_frequency"] == "provider monthly SPEI-3"
    assert policy.maximum_precomputed_month_masks == 17
    assert len(policy.prewarm_month_masks) == 17
    assert policy.prewarm_month_masks[-5:] == ("803", "01c", "0e0", "700", "fff")
    assert policy.arbitrary_month_masks == "on_demand_only"
    assert policy.automatic_deletion is False
    assert policy.object_storage_required_before_multi_year_backfill is False


def test_policy_rejects_temporal_semantic_drift(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "config" / "storage-policy.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    value["temporal_retention"]["spei_source_frequency"] = (
        "reference-period median mislabeled as drought risk"
    )
    mutated = tmp_path / "storage-policy.json"
    mutated.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(StoragePolicyError, match="daily-source/monthly-serving"):
        load_storage_policy(mutated)


def test_directory_inventory_does_not_follow_symlinks(tmp_path: Path) -> None:
    managed = tmp_path / "managed"
    outside = tmp_path / "outside"
    managed.mkdir()
    outside.mkdir()
    (managed / "counted.bin").write_bytes(b"1234")
    (outside / "ignored.bin").write_bytes(b"123456789")
    (managed / "outside-link").symlink_to(outside, target_is_directory=True)

    assert directory_size(managed) == 4


def test_two_year_sicily_release_passes_but_third_year_fails_closed(tmp_path: Path) -> None:
    policy = load_storage_policy()

    report = preflight_backfill(tmp_path, policy, 1, disk=ROOMY_DISK)

    assert report["approved"] is True
    peak = report["peak_increment_bytes"]
    steady = report["steady_increment_bytes"]
    assert isinstance(peak, int)
    assert isinstance(steady, int)
    assert peak > steady
    two_year_report = preflight_backfill(tmp_path, policy, 2, disk=ROOMY_DISK)
    assert two_year_report["approved"] is True
    with pytest.raises(StorageLimitError) as raised:
        preflight_backfill(tmp_path, policy, 3, disk=ROOMY_DISK)
    assert raised.value.reason_code == "backfill_year_limit"


def test_managed_quota_and_disk_reserve_are_enforced_before_writes(
    tmp_path: Path,
) -> None:
    policy = load_storage_policy()
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "existing.bin").write_bytes(b"1234")
    directories = dict(policy.directories)
    directories["raw"] = DirectoryPolicy(
        id="raw",
        path=Path("raw"),
        maximum_bytes=5,
        retention=policy.directories["raw"].retention,
    )
    quota_policy = replace(
        policy,
        directories=directories,
        minimum_free_reserve_bytes=1,
        maximum_volume_used_fraction=0.99,
    )

    with pytest.raises(StorageLimitError) as quota:
        preflight_managed_write(
            quota_policy,
            "raw",
            raw,
            2,
            operation="test_quota",
            disk=ROOMY_DISK,
        )
    assert quota.value.reason_code == "managed_quota_exceeded"

    reserve_policy = replace(policy, minimum_free_reserve_bytes=121 * GIB)
    with pytest.raises(StorageLimitError) as reserve:
        preflight_transient_write(
            reserve_policy,
            tmp_path,
            1,
            operation="test_reserve",
            disk=ROOMY_DISK,
        )
    assert reserve.value.reason_code == "free_space_reserve"


def test_status_and_normalization_preflight_are_machine_readable(
    tmp_path: Path,
) -> None:
    policy = load_storage_policy()
    output = tmp_path / "data" / "published" / "sample"

    status = storage_status(tmp_path, policy, disk=ROOMY_DISK)
    preflight = preflight_normalization(policy, output, disk=ROOMY_DISK)

    assert status["status"] == "ok"
    assert preflight["status"] == "approved"
    published_output = preflight["published_output"]
    assert isinstance(published_output, dict)
    assert published_output["managed_directory"] == "published"
    assert managed_scope_root(policy, "published", output) == output.parent
    json.dumps(status)
    json.dumps(preflight)


def test_cli_returns_structured_blocker_beyond_two_year_sicily_release(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    exit_code = main(
        [
            "--repository-root",
            str(tmp_path),
            "preflight",
            "--years",
            "3",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert report["status"] == "blocked"
    assert report["failure"]["reason_code"] == "backfill_year_limit"
