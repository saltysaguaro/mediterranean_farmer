from __future__ import annotations

import json
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from thermal_drought.acquire.cli import (
    CredentialStatus,
    _select_dataset,
    credential_status,
    main,
)
from thermal_drought.acquire.inspection import (
    InspectionError,
    compare_grids,
    inspect_raw_root,
    read_netcdf_metadata,
)
from thermal_drought.acquire.requests import (
    DROUGHT_DATASET_ID,
    REPRESENTATIVE_REGIONS,
    UTCI_DATASET_ID,
    build_representative_requests,
    plan_sha256,
)
from thermal_drought.acquire.runner import (
    AcquisitionError,
    execute_request,
    receipt_path,
    sha256_file,
)
from thermal_drought.storage import StorageLimitError, load_storage_policy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PAYLOAD = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "acquisition" / "DETERMINISTIC_NOT_ERA5_PAYLOAD.txt"
)


def test_representative_plan_covers_two_seasons_and_all_required_regions() -> None:
    requests = build_representative_requests(year=2024, months=(1, 7))

    assert len(requests) == len(REPRESENTATIVE_REGIONS) * 2 * 3
    assert {request.region.id for request in requests} == {
        "hot_arid_phoenix",
        "temperate_paris",
        "cold_fairbanks",
        "utci_southern_limit",
    }
    assert {request.month for request in requests} == {1, 7}
    assert len({request.request_id for request in requests}) == len(requests)


def test_plan_fingerprint_covers_the_exact_plan_independently_of_order() -> None:
    requests = build_representative_requests(year=2024, months=(1, 7))

    fingerprint = plan_sha256(requests)

    assert len(fingerprint) == 64
    assert fingerprint == plan_sha256(tuple(reversed(requests)))
    assert fingerprint != plan_sha256(requests[:-1])
    with pytest.raises(ValueError, match="request IDs must be unique"):
        plan_sha256((requests[0], requests[0]))


def test_utci_requests_select_provider_daily_statistics() -> None:
    requests = build_representative_requests(year=2024, months=(1,))
    utci = next(request for request in requests if request.dataset_id == UTCI_DATASET_ID)

    assert utci.request["variable"] == ["universal_thermal_climate_index_daily_statistics"]
    assert utci.request["version"] == "1_1"
    assert utci.request["product_type"] == "consolidated_dataset"
    assert utci.request["day"] == [f"{day:02d}" for day in range(1, 32)]


def test_drought_requests_are_deterministic_spei_3_with_quality() -> None:
    requests = build_representative_requests(year=2024, months=(7,))
    drought = next(
        request
        for request in requests
        if request.dataset_id == DROUGHT_DATASET_ID and request.variable_id == "spei_3"
    )
    quality = next(
        request
        for request in requests
        if request.dataset_id == DROUGHT_DATASET_ID and request.variable_id == "spei_3_quality"
    )

    assert drought.request["variable"] == ["standardised_precipitation_evapotranspiration_index"]
    assert drought.request["accumulation_period"] == ["3"]
    assert drought.request["product_type"] == ["reanalysis"]
    assert drought.request["dataset_type"] == "consolidated_dataset"
    assert drought.request["year"] == ["2024"]

    assert quality.request["variable"] == ["test_for_normality_spei"]
    assert quality.request["accumulation_period"] == ["3"]
    assert quality.year is None
    assert "year" not in quality.request
    assert "reference-period" in quality.target_relative_path.parts


def test_verified_file_is_not_downloaded_twice(tmp_path: Path) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]
    calls = 0

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        nonlocal calls
        assert dataset_id == request.dataset_id
        assert provider_request == request.request
        calls += 1
        target.write_bytes(FIXTURE_PAYLOAD.read_bytes())

    frozen_time = datetime(2026, 7, 23, 9, 0, tzinfo=timezone.utc)
    first = execute_request(
        request,
        tmp_path,
        retrieve_fixture,
        now=lambda: frozen_time,
        fixture=True,
    )
    second = execute_request(request, tmp_path, retrieve_fixture, fixture=True)

    assert calls == 1
    assert first.status == "downloaded"
    assert second.status == "verified-existing"
    assert first.sha256 == second.sha256 == sha256_file(FIXTURE_PAYLOAD)
    assert first.byte_size == second.byte_size == FIXTURE_PAYLOAD.stat().st_size
    assert first.retrieval_duration_seconds is not None
    assert first.retrieval_duration_seconds >= 0
    assert second.retrieval_duration_seconds is None

    receipt = json.loads(receipt_path(first.target).read_text(encoding="utf-8"))
    assert receipt["schema_version"] == "1.1"
    assert receipt["fixture"] is True
    assert receipt["retrieved_at"] == "2026-07-23T09:00:00+00:00"
    assert receipt["retrieval_duration_seconds"] >= 0
    assert receipt["period"] == {"year": 2024, "month": 1}
    assert receipt["file"]["sha256"] == sha256_file(FIXTURE_PAYLOAD)
    assert receipt["source"]["doi"].startswith("10.")
    assert receipt["source"]["license"]
    assert receipt["source"]["citation"]
    assert receipt["storage_policy"]["policy_id"] == "local-safe-v1"
    assert receipt["storage_policy"]["receipt_reservation_bytes"] == 64 * 1024


def test_verified_existing_artifact_needs_no_new_storage_reservation(
    tmp_path: Path,
) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]
    calls = 0

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        nonlocal calls
        calls += 1
        target.write_bytes(FIXTURE_PAYLOAD.read_bytes())

    first = execute_request(request, tmp_path, retrieve_fixture, fixture=True)
    blocked_policy = replace(
        load_storage_policy(),
        minimum_free_reserve_bytes=10**18,
    )
    second = execute_request(
        request,
        tmp_path,
        retrieve_fixture,
        fixture=True,
        storage_policy=blocked_policy,
    )

    assert calls == 1
    assert first.status == "downloaded"
    assert second.status == "verified-existing"


def test_acquisition_preflight_blocks_before_provider_call(tmp_path: Path) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]
    calls = 0

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        nonlocal calls
        calls += 1

    blocked_policy = replace(
        load_storage_policy(),
        minimum_free_reserve_bytes=10**18,
    )
    with pytest.raises(StorageLimitError) as raised:
        execute_request(
            request,
            tmp_path,
            retrieve_fixture,
            storage_policy=blocked_policy,
        )

    assert calls == 0
    assert raised.value.reason_code == "free_space_reserve"


def test_oversize_acquisition_partition_is_removed(tmp_path: Path) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]
    tiny_policy = replace(
        load_storage_policy(),
        minimum_free_reserve_bytes=1,
        maximum_volume_used_fraction=0.99,
        maximum_acquisition_partition_bytes=4,
        fixture_partition_reservation_bytes=4,
    )

    def retrieve_oversize(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        target.write_bytes(b"12345")

    with pytest.raises(StorageLimitError) as raised:
        execute_request(
            request,
            tmp_path,
            retrieve_oversize,
            fixture=True,
            storage_policy=tiny_policy,
        )

    target = tmp_path / request.target_relative_path
    assert raised.value.reason_code == "acquisition_partition_limit"
    assert not target.exists()
    assert not target.with_suffix(f"{target.suffix}.part").exists()
    assert not receipt_path(target).exists()


def test_corrupt_existing_file_is_retrieved_again(tmp_path: Path) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]
    payload = FIXTURE_PAYLOAD.read_bytes()
    calls = 0

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        nonlocal calls
        calls += 1
        target.write_bytes(payload)

    first = execute_request(request, tmp_path, retrieve_fixture)
    first.target.write_text("corrupted", encoding="utf-8")
    second = execute_request(request, tmp_path, retrieve_fixture)

    assert calls == 2
    assert second.status == "downloaded"
    assert second.target.read_bytes() == payload


def test_fixture_receipt_cannot_verify_a_production_download(tmp_path: Path) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]
    calls = 0

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        nonlocal calls
        calls += 1
        target.write_bytes(FIXTURE_PAYLOAD.read_bytes())

    execute_request(request, tmp_path, retrieve_fixture, fixture=True)
    production_result = execute_request(request, tmp_path, retrieve_fixture)

    assert calls == 2
    assert production_result.status == "downloaded"
    receipt = json.loads(receipt_path(production_result.target).read_text(encoding="utf-8"))
    assert receipt["fixture"] is False


def test_empty_provider_response_fails_without_verified_artifact(tmp_path: Path) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]

    def retrieve_empty(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        target.touch()

    with pytest.raises(RuntimeError, match="provider returned no data"):
        execute_request(request, tmp_path, retrieve_empty)

    target = tmp_path / request.target_relative_path
    assert not target.exists()
    assert not receipt_path(target).exists()


def test_provider_licence_failure_is_secret_safe_and_leaves_no_partial(
    tmp_path: Path,
) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]
    secret = "credential-that-must-not-escape"

    def reject_retrieval(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        target.write_text("partial response", encoding="utf-8")
        raise RuntimeError(f"403 required licences not accepted; internal credential={secret}")

    with pytest.raises(AcquisitionError) as raised:
        execute_request(request, tmp_path, reject_retrieval)

    error = raised.value
    assert error.reason_code == "licence_not_accepted"
    assert error.dataset_id == UTCI_DATASET_ID
    assert error.request_id == request.request_id
    assert secret not in str(error)
    assert secret not in json.dumps(error.as_dict())

    target = tmp_path / request.target_relative_path
    assert not target.exists()
    assert not target.with_suffix(f"{target.suffix}.part").exists()
    assert not receipt_path(target).exists()


def test_fetch_can_be_scoped_to_one_dataset() -> None:
    requests = build_representative_requests(year=2024, months=(1, 7))

    selected = _select_dataset(requests, DROUGHT_DATASET_ID)

    assert len(selected) == len(REPRESENTATIVE_REGIONS) * 2 * 2
    assert {request.dataset_id for request in selected} == {DROUGHT_DATASET_ID}
    assert plan_sha256(requests) != plan_sha256(selected)


def test_fetch_reports_provider_block_as_machine_readable_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]
    secret = "credential-that-must-not-escape"
    status = CredentialStatus(
        cdsapirc_present=True,
        cdsapirc_nonempty=True,
        environment_url_present=False,
        environment_key_present=False,
        cdsapi_installed=True,
    )

    monkeypatch.setattr(
        "thermal_drought.acquire.cli.credential_status",
        lambda: status,
    )

    def reject_requests(*args: object, **kwargs: object) -> object:
        raise AcquisitionError(
            request,
            "licence_not_accepted",
            "required dataset licence(s) are not accepted for this CDS account",
        )

    monkeypatch.setattr(
        "thermal_drought.acquire.cli.execute_requests",
        reject_requests,
    )

    exit_code = main(
        [
            "fetch",
            "--months",
            "1",
            "--raw-root",
            str(tmp_path),
            "--dataset-id",
            UTCI_DATASET_ID,
        ]
    )
    output = capsys.readouterr().out
    report = json.loads(output)

    assert exit_code == 2
    assert report["status"] == "blocked"
    assert report["fixture"] is False
    assert report["failure"]["reason_code"] == "licence_not_accepted"
    assert report["failure"]["request_id"] == request.request_id
    assert report["failure"]["dataset_id"] == UTCI_DATASET_ID
    assert report["failure"]["dataset_url"].startswith("https://")
    assert secret not in output


def test_credential_probe_reports_presence_without_secret_values(tmp_path: Path) -> None:
    secret = "do-not-print-or-return-this-token"
    (tmp_path / ".cdsapirc").write_text(f"url: example.invalid\nkey: {secret}\n")

    status = credential_status(
        home=tmp_path,
        environ={"CDSAPI_URL": "example.invalid", "CDSAPI_KEY": secret},
    )

    assert status.cdsapirc_present
    assert status.cdsapirc_nonempty
    assert status.environment_url_present
    assert status.environment_key_present
    assert status.usable_configuration_present
    assert secret not in repr(status)


def _structural_metadata(
    latitudes: list[float],
    longitudes: list[float],
    variable_name: str,
    units: str,
) -> dict[str, object]:
    return {
        "dimensions": {
            "time": 1,
            "latitude": len(latitudes),
            "longitude": len(longitudes),
        },
        "coordinates": {
            "latitude": {
                "dimensions": ["latitude"],
                "shape": [len(latitudes)],
                "dtype": "float64",
                "attributes": {
                    "standard_name": "latitude",
                    "units": "degrees_north",
                },
                "units": "degrees_north",
                "nodata": None,
                "values": latitudes,
                "order": {},
            },
            "longitude": {
                "dimensions": ["longitude"],
                "shape": [len(longitudes)],
                "dtype": "float64",
                "attributes": {
                    "standard_name": "longitude",
                    "units": "degrees_east",
                },
                "units": "degrees_east",
                "nodata": None,
                "values": longitudes,
                "order": {},
            },
        },
        "data_variables": {
            variable_name: {
                "dimensions": ["time", "latitude", "longitude"],
                "shape": [1, len(latitudes), len(longitudes)],
                "dtype": "float32",
                "attributes": {"units": units},
                "units": units,
                "nodata": -9999.0,
            }
        },
        "global_attributes": {},
    }


def test_grid_comparison_documents_order_and_longitude_normalization() -> None:
    utci = _structural_metadata(
        [34.25, 34.0, 33.75],
        [-112.25, -112.0, -111.75],
        "utci_daily_max",
        "K",
    )
    spei = _structural_metadata(
        [33.75, 34.0, 34.25],
        [247.75, 248.0, 248.25],
        "spei",
        "1",
    )

    result = compare_grids(utci, spei)

    assert result["compatible"] is True
    assert result["required_transformations"] == [
        "reorder latitude",
        "normalize longitude to [-180, 180)",
    ]
    assert result["mismatch_reasons"] == []


def test_grid_comparison_reports_incompatible_cell_centers() -> None:
    left = _structural_metadata([10.0, 9.75], [20.0, 20.25], "left", "1")
    right = _structural_metadata([10.125, 9.875], [20.0, 20.25], "right", "1")

    result = compare_grids(left, right)

    assert result["compatible"] is False
    assert result["mismatch_reasons"] == ["latitude cell centers differ"]


def test_inspection_rejects_fixture_receipts_as_official_evidence(tmp_path: Path) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        target.write_bytes(FIXTURE_PAYLOAD.read_bytes())

    execute_request(request, tmp_path, retrieve_fixture, fixture=True)

    with pytest.raises(InspectionError, match="not valid official-data evidence"):
        inspect_raw_root(tmp_path, reader=lambda path: {})


def test_fixture_inspection_is_structural_but_never_completes_gate(
    tmp_path: Path,
) -> None:
    requests = build_representative_requests(year=2024, months=(1,))
    representative_requests = [
        request for request in requests if request.region.id == "hot_arid_phoenix"
    ]

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        target.write_bytes(FIXTURE_PAYLOAD.read_bytes())

    for request in representative_requests:
        execute_request(request, tmp_path, retrieve_fixture, fixture=True)

    def read_structure(path: Path) -> dict[str, object]:
        if "utci_daymax_median" in path.parts:
            return _structural_metadata(
                [34.25, 34.0, 33.75],
                [-112.25, -112.0, -111.75],
                "utci_daily_max",
                "K",
            )
        return _structural_metadata(
            [33.75, 34.0, 34.25],
            [247.75, 248.0, 248.25],
            "spei",
            "1",
        )

    frozen_time = datetime(2026, 7, 24, 9, 0, tzinfo=timezone.utc)
    report = inspect_raw_root(
        tmp_path,
        reader=read_structure,
        now=lambda: frozen_time,
        allow_fixtures=True,
        expected_requests=representative_requests,
    )

    assert report["artifact_count"] == 3
    assert report["expected_request_count"] == 3
    assert report["expected_plan_sha256"] == plan_sha256(representative_requests)
    assert report["missing_artifacts"] == []
    assert report["unexpected_artifacts"] == []
    assert report["duplicate_request_ids"] == []
    assert report["receipt_plan_issues"] == []
    assert report["official_evidence"] is False
    assert report["complete"] is False
    assert report["pair_comparisons"][0]["grid"]["compatible"] is True
    assert report["quality_comparisons"][0]["grid"]["compatible"] is True
    for request in representative_requests:
        target = tmp_path / request.target_relative_path
        receipt = json.loads(receipt_path(target).read_text(encoding="utf-8"))
        assert receipt["fixture"] is True
        assert receipt["inspected_at"] == "2026-07-24T09:00:00+00:00"
        assert receipt["observed_netcdf_metadata"]["coordinates"]


def test_inspection_rejects_receipt_that_is_not_bound_to_exact_plan(
    tmp_path: Path,
) -> None:
    requests = [
        request
        for request in build_representative_requests(year=2024, months=(1,))
        if request.region.id == "hot_arid_phoenix"
    ]

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        target.write_bytes(FIXTURE_PAYLOAD.read_bytes())

    for request in requests:
        execute_request(request, tmp_path, retrieve_fixture, fixture=True)

    tampered_request = requests[0]
    tampered_receipt_path = receipt_path(tmp_path / tampered_request.target_relative_path)
    tampered_receipt = json.loads(tampered_receipt_path.read_text(encoding="utf-8"))
    tampered_receipt["request"]["month"] = ["02"]
    tampered_receipt_path.write_text(json.dumps(tampered_receipt), encoding="utf-8")

    report = inspect_raw_root(
        tmp_path,
        reader=lambda path: _structural_metadata(
            [34.25, 34.0, 33.75],
            [-112.25, -112.0, -111.75],
            "structural_test_variable",
            "1",
        ),
        allow_fixtures=True,
        expected_requests=requests,
    )

    assert report["artifact_count"] == 2
    assert report["missing_artifacts"] == [tampered_request.request_id]
    assert any(
        "request does not match the planned request" in issue
        for issue in report["receipt_plan_issues"]
    )
    assert report["complete"] is False
    persisted_receipt = json.loads(tampered_receipt_path.read_text(encoding="utf-8"))
    assert persisted_receipt["observed_netcdf_metadata"] is None


def test_inspection_reports_unexpected_and_duplicate_receipts(
    tmp_path: Path,
) -> None:
    requests = build_representative_requests(year=2024, months=(1, 7))
    expected = [
        request
        for request in requests
        if request.region.id == "hot_arid_phoenix" and request.month == 1
    ]
    unexpected = [
        request
        for request in requests
        if request.region.id == "hot_arid_phoenix" and request.month == 7
    ]

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        target.write_bytes(FIXTURE_PAYLOAD.read_bytes())

    for request in [*expected, *unexpected]:
        execute_request(request, tmp_path, retrieve_fixture, fixture=True)

    duplicated_request = expected[0]
    original_sidecar = receipt_path(tmp_path / duplicated_request.target_relative_path)
    duplicate_sidecar = tmp_path / "duplicate" / "copy.nc.receipt.json"
    duplicate_sidecar.parent.mkdir(parents=True)
    duplicate_sidecar.write_text(
        original_sidecar.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    report = inspect_raw_root(
        tmp_path,
        reader=lambda path: _structural_metadata(
            [34.25, 34.0, 33.75],
            [-112.25, -112.0, -111.75],
            "structural_test_variable",
            "1",
        ),
        allow_fixtures=True,
        expected_requests=expected,
    )

    assert report["duplicate_request_ids"] == [duplicated_request.request_id]
    assert report["unexpected_artifacts"] == sorted(request.request_id for request in unexpected)
    assert report["missing_artifacts"] == [duplicated_request.request_id]
    assert report["artifact_count"] == 2
    assert report["complete"] is False


def test_empty_inspection_report_does_not_import_optional_reader(tmp_path: Path) -> None:
    expected = build_representative_requests(year=2024, months=(1,))[0:1]
    report = inspect_raw_root(
        tmp_path,
        reader=lambda path: pytest.fail(f"unexpected reader call for {path}"),
        expected_requests=expected,
    )

    assert report["artifact_count"] == 0
    assert report["missing_artifacts"] == [expected[0].request_id]
    assert report["expected_plan_sha256"] == plan_sha256(expected)
    assert report["unexpected_artifacts"] == []
    assert report["duplicate_request_ids"] == []
    assert report["receipt_plan_issues"] == []
    assert report["official_evidence"] is False
    assert report["complete"] is False


def test_inspection_preflights_receipt_updates_before_writing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    request = build_representative_requests(year=2024, months=(1,))[0]

    def retrieve_fixture(
        dataset_id: str,
        provider_request: object,
        target: Path,
    ) -> None:
        target.write_bytes(FIXTURE_PAYLOAD.read_bytes())

    result = execute_request(
        request,
        tmp_path,
        retrieve_fixture,
        fixture=True,
    )
    original_receipt = result.receipt.read_text(encoding="utf-8")
    blocked_policy = replace(
        load_storage_policy(),
        minimum_free_reserve_bytes=10**18,
    )
    monkeypatch.setattr(
        "thermal_drought.acquire.inspection.load_storage_policy",
        lambda: blocked_policy,
    )

    with pytest.raises(StorageLimitError) as raised:
        inspect_raw_root(
            tmp_path,
            reader=lambda path: _structural_metadata(
                [34.25, 34.0, 33.75],
                [-112.25, -112.0, -111.75],
                "utci_daily_max",
                "K",
            ),
            allow_fixtures=True,
            expected_requests=[request],
        )

    assert raised.value.reason_code == "free_space_reserve"
    assert result.receipt.read_text(encoding="utf-8") == original_receipt


def test_netcdf_reader_extracts_structural_coordinates_when_data_extra_is_present(
    tmp_path: Path,
) -> None:
    xr = pytest.importorskip("xarray")
    pytest.importorskip("h5netcdf")
    path = tmp_path / "STRUCTURAL_TEST_FILE_NOT_CLIMATE_DATA.nc"
    dataset = xr.Dataset(
        coords={
            "latitude": (
                "latitude",
                [34.25, 34.0, 33.75],
                {"standard_name": "latitude", "units": "degrees_north"},
            ),
            "longitude": (
                "longitude",
                [-112.25, -112.0, -111.75],
                {"standard_name": "longitude", "units": "degrees_east"},
            ),
        },
        attrs={
            "fixture": (
                "STRUCTURAL TEST FILE ONLY — NOT ERA5, CLIMATE DATA, OR AN OBSERVATIONAL SAMPLE"
            )
        },
    )
    dataset.to_netcdf(path, engine="h5netcdf")

    metadata = read_netcdf_metadata(path)

    assert metadata["dimensions"] == {"latitude": 3, "longitude": 3}
    assert metadata["coordinates"]["latitude"]["values"] == [34.25, 34.0, 33.75]
    assert metadata["coordinates"]["latitude"]["order"] == {
        "first": 34.25,
        "last": 33.75,
        "order": "descending",
        "regular_step": -0.25,
    }
    assert metadata["data_variables"] == {}
    assert "NOT ERA5" in metadata["global_attributes"]["fixture"]


def test_netcdf_reader_inspects_safe_zip_members_without_loading_climate_data(
    tmp_path: Path,
) -> None:
    xr = pytest.importorskip("xarray")
    pytest.importorskip("h5netcdf")
    members: list[Path] = []
    for day in (1, 2):
        member = tmp_path / f"STRUCTURAL_TEST_202401{day:02d}_NOT_CLIMATE.nc"
        dataset = xr.Dataset(
            coords={
                "time": (
                    "time",
                    [day],
                    {
                        "standard_name": "time",
                        "units": f"hours since 2024-01-{day:02d} 00:00:00",
                    },
                ),
                "latitude": (
                    "latitude",
                    [34.25, 34.0, 33.75],
                    {"standard_name": "latitude", "units": "degrees_north"},
                ),
                "longitude": (
                    "longitude",
                    [-112.25, -112.0, -111.75],
                    {"standard_name": "longitude", "units": "degrees_east"},
                ),
            },
            attrs={"fixture": "STRUCTURAL TEST ONLY — NOT CLIMATE DATA"},
        )
        dataset.to_netcdf(member, engine="h5netcdf")
        members.append(member)

    archive_path = tmp_path / "STRUCTURAL_TEST_ARCHIVE_NOT_CLIMATE_DATA.nc"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in members:
            archive.write(member, arcname=member.name)

    metadata = read_netcdf_metadata(archive_path)

    assert metadata["archive"]["format"] == "zip"
    assert metadata["archive"]["member_count"] == 2
    assert metadata["archive"]["member_names"] == [member.name for member in members]
    assert metadata["archive"]["member_structures_consistent"] is True
    assert metadata["archive"]["spatial_grids_consistent"] is True
    assert metadata["coordinates"]["latitude"]["values"] == [34.25, 34.0, 33.75]


def test_netcdf_reader_rejects_unsafe_zip_member(tmp_path: Path) -> None:
    archive_path = tmp_path / "UNSAFE_STRUCTURAL_TEST_ARCHIVE.nc"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.nc", b"not a NetCDF file")

    with pytest.raises(InspectionError, match="unsafe or non-NetCDF member"):
        read_netcdf_metadata(archive_path)
