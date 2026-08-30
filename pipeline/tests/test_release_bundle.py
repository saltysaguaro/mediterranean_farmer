from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from thermal_drought.release_bundle import (
    ReleasePointer,
    ReleaseStore,
    build_bundle,
    inspect_bundle,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_official_release_bundle_is_deterministic_and_complete_when_products_exist(
    tmp_path: Path,
) -> None:
    report = json.loads((REPOSITORY_ROOT / "pipeline/reports/sicily-release-v1.json").read_text())
    if not all((REPOSITORY_ROOT / output["path"]).is_file() for output in report["outputs"]):
        pytest.skip("ignored official Sicily release products are not present")
    output = REPOSITORY_ROOT / "output" / "test-release-bundle.zip"

    first = build_bundle(REPOSITORY_ROOT, output)
    first_bytes = output.read_bytes()
    second = build_bundle(REPOSITORY_ROOT, output)

    assert first["bundle_sha256"] == second["bundle_sha256"]
    assert first_bytes == output.read_bytes()
    assert inspect_bundle(output, str(first["bundle_sha256"]))["status"] == "complete"


def test_bundle_inspection_rejects_traversal(tmp_path: Path) -> None:
    bundle = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("../escape", b"unsafe")
    with pytest.raises(ValueError, match="unsafe release bundle path"):
        inspect_bundle(bundle)


def test_release_pointer_promotes_and_rolls_back_without_deleting(tmp_path: Path) -> None:
    store = ReleaseStore(tmp_path)
    first = store.releases / "first"
    second = store.releases / "second"
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    # Pointer mechanics are isolated from product validation in this unit test.
    store._write_pointer(ReleasePointer("first", None, "2026-01-01T00:00:00+00:00"))
    store._write_pointer(ReleasePointer("second", "first", "2026-01-02T00:00:00+00:00"))
    rolled_back = store.rollback()

    assert rolled_back.current == "first"
    assert rolled_back.previous == "second"
    assert first.is_dir() and second.is_dir()
