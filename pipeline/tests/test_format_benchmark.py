from __future__ import annotations

from pathlib import Path

from thermal_drought.format_benchmark import run_benchmark

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_sicily_structural_format_benchmark_is_exact_and_conspicuous() -> None:
    report = run_benchmark(REPOSITORY_ROOT / "config" / "scope.json")

    assert report["fixture"] is True
    assert report["official_evidence"] is False
    assert "NOT CLIMATE OBSERVATIONS" in str(report["fixture_label"])
    assert report["shape"] == [12, 16, 17]
    assert report["included_scope_cells"] == 44
    assert report["exact_round_trip_parity"] is True
    assert int(report["compressed_netcdf_bytes"]) > 0
    assert int(report["sparse_json_gzip_bytes"]) < int(report["sparse_json_bytes"])
