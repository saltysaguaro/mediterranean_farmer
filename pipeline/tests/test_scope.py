from __future__ import annotations

import json
from pathlib import Path

import pytest

from thermal_drought.scope import load_scope

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = REPOSITORY_ROOT / "config" / "scope.json"


def test_sicily_scope_has_authoritative_boundary_and_exact_grid_mask() -> None:
    scope = load_scope(SCOPE_PATH)

    assert scope.scope_id == "sicily_istat_2026_grid_centers"
    assert scope.name == "Sicilia"
    assert scope.grid_id == "era5_latlon_0_25"
    assert scope.acquisition_bbox == (11.75, 35.25, 15.75, 39.0)
    assert len(scope.included_cell_centers) == 44
    assert scope.includes(13.75, 37.5)
    assert scope.includes(12.0, 36.75)
    assert not scope.includes(15.75, 38.0)
    assert len(scope.boundary_archive_sha256) == 64
    assert scope.boundary_license == "CC BY 4.0"
    assert scope.boundary_dataset_url.startswith("https://www.istat.it/")


def test_sicily_scope_rejects_non_grid_center(tmp_path: Path) -> None:
    payload = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    payload["analysis_grid"]["included_cell_centers"].append([13.1, 37.5])
    invalid = tmp_path / "scope.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="not provider-grid aligned"):
        load_scope(invalid)
