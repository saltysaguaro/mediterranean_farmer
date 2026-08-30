import json
from pathlib import Path

import pytest

from thermal_drought.api.app import create_app
from thermal_drought.api.core import DataService
from thermal_drought.api.runtime import RuntimeSettings, create_production_app
from thermal_drought.operations import STANDARD_MASKS, _percentile, security_probes

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_standard_prewarm_allowlist_is_exactly_seventeen_unique_masks() -> None:
    assert len(STANDARD_MASKS) == len(set(STANDARD_MASKS)) == 17
    assert STANDARD_MASKS[:12] == tuple(1 << index for index in range(12))
    assert STANDARD_MASKS[-1] == 0xFFF


def test_percentile_uses_nearest_rank() -> None:
    assert _percentile([4.0, 1.0, 3.0, 2.0], 0.5) == 2.0
    assert _percentile([4.0, 1.0, 3.0, 2.0], 0.95) == 4.0
    assert _percentile([], 0.95) == 0.0


def test_security_probes_reject_invalid_requests_when_release_exists(tmp_path: Path) -> None:
    report = REPOSITORY_ROOT / "pipeline/reports/sicily-release-v1.json"
    release = json.loads(report.read_text())
    if not all((REPOSITORY_ROOT / output["path"]).is_file() for output in release["outputs"]):
        pytest.skip("ignored official Sicily release products are not present")
    service = DataService.from_repository(REPOSITORY_ROOT)
    settings = RuntimeSettings.load(REPOSITORY_ROOT / "config/app.json", REPOSITORY_ROOT)
    settings = RuntimeSettings(
        **{
            **settings.__dict__,
            "cache_directory": tmp_path / "cache",
            "requests_per_minute": 1000,
        }
    )
    application = create_production_app(create_app(service), settings, readiness=lambda: True)
    result = security_probes(application, service.registry.settings.dataset_version)
    assert result["passed"] is True
