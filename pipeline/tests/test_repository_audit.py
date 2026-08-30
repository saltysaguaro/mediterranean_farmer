from pathlib import PurePosixPath

from thermal_drought.repository_audit import path_violation, scan_text


def test_repository_boundary_rejects_generated_and_secret_paths() -> None:
    cases = {
        "data/raw/source.nc": "climate_data_path",
        "data/canonical/year.zarr/chunk": "climate_data_path",
        "data/published/month.tif": "climate_data_path",
        "pipeline/.venv/bin/python": "dependency_or_cache_path",
        "web/node_modules/pkg/index.js": "dependency_or_cache_path",
        "web/dist/index.html": "generated_web_build",
        "output/preview/smoke.png": "generated_browser_output",
        ".cdsapirc": "credential_path",
        ".env.local": "credential_path",
        "services/tile/cache/0.png": "runtime_cache_path",
        "services/state.sqlite": "runtime_state_path",
        "preview/month.webp": "generated_or_climate_artifact",
    }
    for raw_path, expected_reason in cases.items():
        assert path_violation(PurePosixPath(raw_path)) == expected_reason


def test_repository_boundary_grandfathers_only_legacy_rasters() -> None:
    assert path_violation(PurePosixPath("docs/data/crops/legacy/annual.tif")) is None
    assert path_violation(PurePosixPath("docs/data/crops/legacy/annual.webp")) is None
    assert (
        path_violation(
            PurePosixPath("docs/data/crops/legacy/new-annual.tif"),
            allow_legacy_raster=False,
        )
        == "generated_or_climate_artifact"
    )
    assert (
        path_violation(PurePosixPath("docs/data/new-climate/annual.tif"))
        == "generated_or_climate_artifact"
    )
    assert path_violation(PurePosixPath(".env.example")) is None
    assert path_violation(PurePosixPath("pipeline/reports/evidence.json")) is None


def test_secret_scan_reports_location_without_secret_value() -> None:
    aws_token = "A" + "KIA" + "1234567890ABCDEF"
    private_key_header = "-----BEGIN " + "PRIVATE KEY-----"
    text = f"safe line\n{aws_token}\n{private_key_header}\n"

    findings = scan_text(PurePosixPath("candidate.txt"), text)

    assert [(item.kind, item.line) for item in findings] == [
        ("aws_access_key", 2),
        ("private_key", 3),
    ]
    assert all(not hasattr(item, "value") for item in findings)


def test_secret_scan_ignores_placeholders_and_normal_urls() -> None:
    findings = scan_text(
        PurePosixPath("README.md"),
        "CDSAPI_KEY=<secret>\nhttps://example.com/dataset\nnot-a-token\n",
    )

    assert findings == ()
