from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import xarray as xr

from thermal_drought.api.app import WsgiApplication, create_app
from thermal_drought.api.core import DataService, ServiceError, _validate_official_publication
from thermal_drought.months import months_to_mask

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFESTS = REPOSITORY_ROOT / "config" / "variables"
APP_CONFIG = REPOSITORY_ROOT / "config" / "app.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture
def fixture_service(tmp_path: Path) -> DataService:
    product = (
        tmp_path
        / "data"
        / "published"
        / "deterministic-structural-fixture"
        / "v1"
        / "2024"
        / "test_region.nc"
    )
    product.parent.mkdir(parents=True)
    times = np.asarray(
        [
            np.datetime64("2024-01-01T00:00:00", "ns"),
            np.datetime64("2024-07-01T00:00:00", "ns"),
        ]
    )
    dataset = xr.Dataset(
        data_vars={
            "utci_daymax_median": (
                ("time", "latitude", "longitude"),
                np.asarray(
                    [
                        [[8.0, 9.0], [26.0, 27.0]],
                        [[10.0, 11.0], [28.0, 29.0]],
                    ],
                    dtype=np.float32,
                ),
            ),
            "spei_3": (
                ("time", "latitude", "longitude"),
                np.asarray(
                    [
                        [[-1.5, -1.0], [-0.5, np.nan]],
                        [[-1.5, -1.0], [-0.5, np.nan]],
                    ],
                    dtype=np.float32,
                ),
            ),
            "spei_3_quality": (
                ("time", "latitude", "longitude"),
                np.asarray(
                    [
                        [[1, 1], [1, 0]],
                        [[1, 1], [1, 0]],
                    ],
                    dtype=np.uint8,
                ),
            ),
            "artificial_interface_fixture": (
                ("time", "latitude", "longitude"),
                np.asarray(
                    [
                        [[1.0, 2.0], [3.0, 4.0]],
                        [[5.0, 6.0], [7.0, 8.0]],
                    ],
                    dtype=np.float32,
                ),
            ),
        },
        coords={
            "time": ("time", times),
            "latitude": ("latitude", [34.25, 34.0]),
            "longitude": ("longitude", [-112.25, -112.0]),
        },
        attrs={
            "schema_version": "1.0",
            "fixture": "true",
            "evidence_scope": "deterministic structural test fixture; not climate observations",
            "region_id": "test_region",
            "analysis_year": 2024,
            "grid_id": "era5_latlon_0_25",
            "crs": "EPSG:4326",
        },
    )
    dataset.to_netcdf(product, engine="h5netcdf")
    report = {
        "schema_version": "1.0",
        "status": "complete",
        "fixture": True,
        "scope": "deterministic structural test fixture; not climate observations",
        "source_audit_complete": False,
        "source_official_evidence": False,
        "plan_sha256": "0" * 64,
        "outputs": [
            {
                "region_id": "test_region",
                "path": str(product.relative_to(tmp_path)),
                "sha256": _sha256(product),
                "months": [1, 7],
                "shape": [2, 2, 2],
            }
        ],
    }
    report_path = tmp_path / "fixture-report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="fixture releases are disabled"):
        DataService.from_repository(
            tmp_path,
            manifests_root=MANIFESTS,
            app_path=APP_CONFIG,
            report_path=report_path,
        )
    return DataService.from_repository(
        tmp_path,
        manifests_root=MANIFESTS,
        app_path=APP_CONFIG,
        report_path=report_path,
        allow_fixture=True,
    )


def test_health_and_availability_label_fixture_scope(fixture_service: DataService) -> None:
    health = fixture_service.health()
    availability = fixture_service.availability()

    assert health["status"] == "ok"
    assert health["fixture"] is True
    assert health["official_evidence"] is False
    assert availability["latest_complete_year"] is None
    assert availability["years"] == [
        {
            "year": 2024,
            "months": [1, 7],
            "complete": False,
            "regions": ["test_region"],
        }
    ]
    assert availability["maximum_active_variables"] == 2


def test_official_release_rejects_planned_manifest(fixture_service: DataService) -> None:
    spei = fixture_service.registry.variables["spei_3"]
    registry = replace(
        fixture_service.registry,
        variables={
            **fixture_service.registry.variables,
            "spei_3": replace(spei, publication_status="planned"),
        },
    )

    with pytest.raises(ValueError, match="official release manifest is not published"):
        _validate_official_publication(registry, {2024, 2025})


def test_service_excludes_cells_outside_release_scope_mask(
    fixture_service: DataService,
) -> None:
    product = replace(
        fixture_service.release.products[0],
        included_indices=frozenset({(0, 0)}),
    )
    scoped = DataService(
        fixture_service.registry,
        replace(fixture_service.release, products=(product,)),
    )

    outside, _ = scoped.sample(
        ["spei_3", "utci_daymax_median"],
        2024,
        months_to_mask([1]),
        34.0,
        -112.0,
    )
    tile, _ = scoped.tile(
        "sicily-2024-2025-v1",
        ["spei_3", "utci_daymax_median"],
        2024,
        months_to_mask([1]),
        0,
        0,
        0,
    )

    assert outside["status"] == "no_data"
    assert outside["reason"] == "outside_sicily_scope"
    assert "grid_cell" not in outside
    assert len(tile["cells"]) == 1
    assert tile["cells"][0]["row"] == 0
    assert tile["cells"][0]["column"] == 0


def test_point_uses_provider_january_spei_without_recomputation(
    fixture_service: DataService,
) -> None:
    response, _ = fixture_service.sample(
        ["spei_3", "utci_daymax_median"],
        2024,
        months_to_mask([1]),
        34.25,
        -112.25,
    )

    spei, utci = response["variables"]
    assert response["status"] == "ok"
    assert spei["value"] == -1.5
    assert spei["class_index"] == 0
    assert spei["class_label"] == "Severe or extreme drought"
    assert spei["quality_state"] == "passes"
    assert spei["source"]["sample_retrieved_at"] == "2026-08-07T09:39:40.662926+00:00"
    assert utci["value"] == 8.0
    assert utci["class_label"] == "Cold stress"


def test_point_and_corresponding_tile_cell_are_identical(
    fixture_service: DataService,
) -> None:
    mask = months_to_mask([1, 7])
    point, point_etag = fixture_service.sample(
        ["spei_3", "utci_daymax_median"],
        2024,
        mask,
        34.0,
        -112.0,
    )
    tile, tile_etag = fixture_service.tile(
        "sicily-2024-2025-v1",
        ["spei_3", "utci_daymax_median"],
        2024,
        mask,
        0,
        0,
        0,
    )
    tile_cell = next(
        cell
        for cell in tile["cells"]
        if cell["latitude"] == point["grid_cell"]["latitude"]
        and cell["longitude"] == point["grid_cell"]["longitude"]
    )

    assert point["status"] == "partial_data"
    assert point["quality_warning"] is True
    assert point["variables"][0]["value"] is None
    assert point["variables"][0]["class_index"] is None
    assert point["variables"][0]["valid_month_count"] == 0
    assert point["variables"][0]["quality_state"] == "low_quality"
    assert point["variables"] == tile_cell["variables"]
    assert point_etag != tile_etag
    assert tile["format"] == "lossless_sparse_grid_cells_v1"


def test_cache_identity_changes_with_axis_or_classification(
    fixture_service: DataService,
) -> None:
    mask = months_to_mask([1])
    original, _ = fixture_service.sample(
        ["spei_3", "utci_daymax_median"], 2024, mask, 34.25, -112.25
    )
    swapped, _ = fixture_service.sample(
        ["utci_daymax_median", "spei_3"], 2024, mask, 34.25, -112.25
    )
    original_spei = fixture_service.registry.variables["spei_3"]
    changed_spei = replace(
        original_spei,
        classification=replace(
            original_spei.classification,
            breaks=(-1.6, -1.0),
            version="changed-for-test",
        ),
    )
    changed_registry = replace(
        fixture_service.registry,
        variables={
            **fixture_service.registry.variables,
            "spei_3": changed_spei,
        },
    )
    changed_service = DataService(changed_registry, fixture_service.release)
    changed, _ = changed_service.sample(
        ["spei_3", "utci_daymax_median"], 2024, mask, 34.25, -112.25
    )
    changed_validity = replace(original_spei, minimum_valid_fraction=0.5)
    validity_registry = replace(
        fixture_service.registry,
        variables={
            **fixture_service.registry.variables,
            "spei_3": changed_validity,
        },
    )
    validity_service = DataService(validity_registry, fixture_service.release)
    validity, _ = validity_service.sample(
        ["spei_3", "utci_daymax_median"], 2024, mask, 34.25, -112.25
    )

    assert original["cache_key"] != swapped["cache_key"]
    assert original["cache_key"] != changed["cache_key"]
    assert original["cache_key"] != validity["cache_key"]


def test_univariate_selection_and_data_driven_compatibility(
    fixture_service: DataService,
) -> None:
    univariate, _ = fixture_service.sample(["spei_3"], 2024, months_to_mask([1]), 34.25, -112.25)
    original_utci = fixture_service.registry.variables["utci_daymax_median"]
    incompatible_utci = replace(original_utci, grid_id="different_grid")
    incompatible_registry = replace(
        fixture_service.registry,
        variables={
            **fixture_service.registry.variables,
            "utci_daymax_median": incompatible_utci,
        },
    )
    incompatible_service = DataService(incompatible_registry, fixture_service.release)

    assert len(univariate["variables"]) == 1
    with pytest.raises(ServiceError) as error:
        incompatible_service.sample(
            ["spei_3", "utci_daymax_median"],
            2024,
            months_to_mask([1]),
            34.25,
            -112.25,
        )
    assert error.value.code == "incompatible_variables"


def test_artificial_third_variable_uses_generic_median_classification_and_sampling(
    fixture_service: DataService,
) -> None:
    template = fixture_service.registry.variables["utci_daymax_median"]
    artificial = replace(
        template,
        id="artificial_interface_fixture",
        label="Artificial interface variable — not climate observations",
        unit="fixture units",
        source={
            **template.source,
            "dataset": "Deterministic structural fixture — not climate observations",
            "provider": "Local test only",
            "product_version": "fixture-1",
            "doi": "10.0000/not-a-climate-observation",
        },
        data_version="deterministic-interface-fixture-v1",
        sample_retrieved_at=None,
    )
    registry = replace(
        fixture_service.registry,
        variables={**fixture_service.registry.variables, artificial.id: artificial},
    )
    service = DataService(registry, fixture_service.release)

    point, _ = service.sample(
        ["spei_3", artificial.id],
        2024,
        months_to_mask([1, 7]),
        34.25,
        -112.25,
    )

    assert point["fixture"] is True
    assert point["official_evidence"] is False
    assert point["variables"][1]["value"] == 3.0
    assert point["variables"][1]["class_label"] == "Cold stress"
    assert point["variables"][1]["source"]["sample_retrieved_at"] is None
    assert any(
        record["variables"] == ["artificial_interface_fixture", "spei_3"]
        for record in service.availability()["compatibility"]
    )


@pytest.mark.parametrize(
    ("operation", "code"),
    [
        (
            lambda service: service.sample(["spei_3", "spei_3"], 2024, 0x001, 34.0, -112.0),
            "duplicate_variable",
        ),
        (
            lambda service: service.sample(
                ["spei_3", "utci_daymax_median", "third"],
                2024,
                0x001,
                34.0,
                -112.0,
            ),
            "invalid_variable_count",
        ),
        (
            lambda service: service.sample(["spei_3"], 2024, months_to_mask([2]), 34.0, -112.0),
            "months_not_available",
        ),
        (
            lambda service: service.tile(
                "sicily-2024-2025-v1",
                ["spei_3"],
                2024,
                0x001,
                10,
                0,
                0,
            ),
            "invalid_zoom",
        ),
        (
            lambda service: service.sample(["spei_3"], 2024, 0x001, 91.0, -112.0),
            "invalid_latitude",
        ),
    ],
)
def test_invalid_inputs_fail_before_data_reads(
    fixture_service: DataService,
    operation: Any,
    code: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("invalid request reached the data reader")

    monkeypatch.setattr(fixture_service, "_aggregate_product", fail_if_opened)
    with pytest.raises(ServiceError) as error:
        operation(fixture_service)
    assert error.value.code == code


def _request(
    application: WsgiApplication,
    path: str,
    query: str = "",
) -> tuple[int, dict[str, str], dict[str, Any]]:
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(
        application(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": path,
                "QUERY_STRING": query,
            },
            start_response,
        )
    )
    return (
        int(str(captured["status"]).split()[0]),
        captured["headers"],
        json.loads(body),
    )


def test_wsgi_health_sample_tile_and_bounded_error(fixture_service: DataService) -> None:
    application = create_app(fixture_service)

    health_status, _, health = _request(application, "/v1/health")
    sample_status, sample_headers, sample = _request(
        application,
        "/v1/sample",
        "x=spei_3&y=utci_daymax_median&year=2024&months=001&lng=-112.25&lat=34.25",
    )
    tile_status, tile_headers, tile = _request(
        application,
        "/v1/tiles/sicily-2024-2025-v1/spei_3/utci_daymax_median/2024/001/0/0/0",
    )
    error_status, _, error = _request(
        application,
        "/v1/tiles/sicily-2024-2025-v1/spei_3/-/2024/001/0/1/0",
    )

    assert health_status == 200
    assert health["status"] == "ok"
    assert sample_status == 200
    assert sample["variables"][0]["value"] == -1.5
    assert sample_headers["ETag"]
    assert tile_status == 200
    assert len(tile["cells"]) == 4
    assert tile_headers["Cache-Control"].endswith("immutable")
    assert error_status == 400
    assert error["error"]["code"] == "invalid_tile_coordinate"


def test_official_sicily_point_and_tile_agree_when_local_products_exist() -> None:
    outputs = load_official_output_paths()
    if not outputs or not all(path.is_file() for path in outputs):
        pytest.skip("ignored official Sicily release products are not present")
    service = DataService.from_repository(REPOSITORY_ROOT)
    mask = months_to_mask(range(1, 13))
    point, _ = service.sample(
        ["spei_3", "utci_daymax_median"],
        2025,
        mask,
        37.5,
        13.75,
    )
    tile, _ = service.tile(
        "sicily-2024-2025-v1",
        ["spei_3", "utci_daymax_median"],
        2025,
        mask,
        0,
        0,
        0,
    )
    matching = next(
        cell
        for cell in tile["cells"]
        if cell["region_id"] == "sicily"
        and cell["latitude"] == point["grid_cell"]["latitude"]
        and cell["longitude"] == point["grid_cell"]["longitude"]
    )

    assert service.health()["official_evidence"] is True
    assert point["fixture"] is False
    assert point["variables"] == matching["variables"]
    assert all(variable["value"] is not None for variable in point["variables"])
    assert all(variable["valid_month_count"] >= 9 for variable in point["variables"])


def load_official_output_paths() -> list[Path]:
    report_path = REPOSITORY_ROOT / "pipeline" / "reports" / "sicily-release-v1.json"
    if not report_path.is_file():
        return []
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return [REPOSITORY_ROOT / output["path"] for output in report["outputs"]]
