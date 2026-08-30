from __future__ import annotations

from pathlib import Path

from thermal_drought.structural_validation import (
    SCENARIOS,
    build_structural_release,
    validate_structural_release,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_structural_matrix_covers_locations_classes_quality_and_point_tile_parity(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "fixture-release.json"
    build_structural_release(
        tmp_path,
        scope_path=REPOSITORY_ROOT / "config" / "scope.json",
        output_report=report_path,
    )

    result = validate_structural_release(
        tmp_path,
        report_path=report_path,
        manifests_root=REPOSITORY_ROOT / "config" / "variables",
        app_path=REPOSITORY_ROOT / "config" / "app.json",
    )

    assert result["status"] == "complete"
    assert result["fixture"] is True
    assert result["official_evidence"] is False
    assert result["scenario_count"] == len(SCENARIOS)
    assert result["all_nine_bivariate_pairs"] is True
    assert result["point_tile_parity"] is True
    cases = {record["id"]: record for record in result["results"]}
    assert cases["quality_failure"]["status"] == "partial_data"
    assert cases["quality_failure"]["quality_warning"] is True
    assert cases["no_data"]["status"] == "no_data"
