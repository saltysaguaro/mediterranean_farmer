from datetime import datetime, timezone

import pytest

from thermal_drought.monitor import _base_url, evaluate


def _payloads(retrieved_at: str = "2026-08-07T09:00:00+00:00") -> dict[str, dict[str, object]]:
    return {
        "live": {"status": "ok", "live": True},
        "ready": {"status": "ok", "ready": True},
        "availability": {
            "status": "ok",
            "fixture": False,
            "official_evidence": True,
            "dataset_version": "sicily-v1",
            "latest_complete_year": 2025,
            "variables": [
                {"id": "spei_3", "sample_retrieved_at": retrieved_at},
                {"id": "utci", "sample_retrieved_at": retrieved_at},
            ],
        },
        "metrics": {
            "status": "ok",
            "counts": {},
            "privacy": "Metrics contain route classes only; coordinates are not recorded.",
        },
    }


def test_monitor_accepts_healthy_recent_official_release() -> None:
    result = evaluate(
        _payloads(),
        now=datetime(2026, 8, 29, tzinfo=timezone.utc),
        maximum_freshness_days=120,
    )
    assert result["status"] == "ok"
    assert result["failures"] == []


def test_monitor_fails_closed_for_fixture_and_stale_data() -> None:
    payloads = _payloads("2025-01-01T00:00:00+00:00")
    payloads["availability"]["fixture"] = True
    payloads["availability"]["official_evidence"] = False
    result = evaluate(
        payloads,
        now=datetime(2026, 8, 29, tzinfo=timezone.utc),
        maximum_freshness_days=120,
    )
    assert result["status"] == "blocked"
    assert "official_release_not_active" in result["failures"]
    assert "freshness_out_of_bounds:spei_3" in result["failures"]


def test_monitor_url_requires_https_except_explicit_loopback() -> None:
    assert _base_url("https://climate.example/api/", allow_http=False) == (
        "https://climate.example/api"
    )
    assert _base_url("http://127.0.0.1:4173/api", allow_http=True).startswith("http://")
    with pytest.raises(ValueError, match="must use https"):
        _base_url("http://climate.example", allow_http=True)
    with pytest.raises(ValueError, match="must not contain credentials"):
        credentialed_url = "https://" + "test-user:test-value@" + "climate.example"
        _base_url(credentialed_url, allow_http=False)
