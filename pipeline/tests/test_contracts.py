from __future__ import annotations

import json
from pathlib import Path

import pytest

from thermal_drought.contracts import (
    ManifestValidationError,
    build_validator,
    load_json,
    schema_path,
    validate_manifest,
    validate_targets,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VARIABLES = REPOSITORY_ROOT / "config" / "variables"


def test_real_variable_manifests_validate() -> None:
    paths = validate_targets([VARIABLES])
    assert [path.name for path in paths] == [
        "spei_3.json",
        "utci_daymax_median.json",
    ]


def test_invalid_fixture_has_actionable_path() -> None:
    validator = build_validator(load_json(schema_path()))
    fixture = REPOSITORY_ROOT / "tests" / "fixtures" / "manifests" / "invalid-missing-id.json"
    with pytest.raises(ManifestValidationError, match=r"'id' is a required property"):
        validate_manifest(fixture, validator)


def test_unsorted_breaks_fail_even_when_json_schema_is_valid(tmp_path: Path) -> None:
    source = load_json(VARIABLES / "utci_daymax_median.json")
    source["classification"]["breaks"] = [26, 9]
    manifest = tmp_path / "unsorted.json"
    manifest.write_text(json.dumps(source), encoding="utf-8")

    validator = build_validator(load_json(schema_path()))
    with pytest.raises(ManifestValidationError, match="strictly ascending"):
        validate_manifest(manifest, validator)


def test_quality_policy_and_field_must_agree(tmp_path: Path) -> None:
    source = load_json(VARIABLES / "utci_daymax_median.json")
    source["quality"]["field"] = "unexpected_quality"
    manifest = tmp_path / "invalid-quality.json"
    manifest.write_text(json.dumps(source), encoding="utf-8")

    validator = build_validator(load_json(schema_path()))
    with pytest.raises(ManifestValidationError, match="policy none"):
        validate_manifest(manifest, validator)
