from __future__ import annotations

import json
import statistics
import zipfile
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
import xarray as xr

from thermal_drought.acquire.requests import AcquisitionRequest, build_representative_requests
from thermal_drought.normalize.core import (
    NormalizationError,
    normalize_period,
    normalize_representative_sample,
)
from thermal_drought.storage import StorageLimitError, load_storage_policy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_RAW_ROOT = REPOSITORY_ROOT / "data" / "raw"


def _write_zip(path: Path, members: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in members:
            archive.write(member, arcname=member.name)


def _structural_test_archives(
    root: Path,
    *,
    utci_units: str | None = None,
    spei_units: str | None = None,
    quality_value: float = 0.0,
) -> tuple[Path, Path, Path]:
    """Create deterministic structural inputs that are explicitly not ERA5 data."""

    latitudes = np.asarray([33.75, 34.0])
    longitudes = np.asarray([247.75, 248.0])
    utci_members: list[Path] = []
    for day in range(1, 30):
        attributes: dict[str, object] = {
            "cell_methods": "time: maximum",
            "fixture": "STRUCTURAL TEST ONLY — NOT ERA5 OR OBSERVATIONS",
        }
        if utci_units is not None:
            attributes["units"] = utci_units
        member = root / f"STRUCTURAL_TEST_202402{day:02d}_NOT_CLIMATE.nc"
        daily_celsius = np.asarray(
            [[day, day + 1], [day + 2, day + 3]],
            dtype=np.float32,
        )
        dataset = xr.Dataset(
            data_vars={
                "utci_daily_min": (
                    ("time", "lat", "lon"),
                    (daily_celsius + 260.0)[None, :, :],
                    {"cell_methods": "time: minimum"},
                ),
                "utci_daily_max": (
                    ("time", "lat", "lon"),
                    (daily_celsius + 273.15)[None, :, :],
                    attributes,
                ),
            },
            coords={
                "time": [np.datetime64(f"2024-02-{day:02d}T11:30:00", "ns")],
                "lat": (
                    "lat",
                    latitudes,
                    {"standard_name": "latitude", "units": "degrees_north"},
                ),
                "lon": (
                    "lon",
                    longitudes,
                    {"standard_name": "longitude", "units": "degrees_east"},
                ),
            },
            attrs={"fixture": "STRUCTURAL TEST ONLY — NOT CLIMATE DATA"},
        )
        dataset.to_netcdf(
            member,
            engine="h5netcdf",
            encoding={"utci_daily_max": {"_FillValue": np.float32(-9e33)}},
        )
        utci_members.append(member)

    spei_member = root / "STRUCTURAL_TEST_SPEI3_NOT_CLIMATE.nc"
    spei_attributes: dict[str, object] = {"long_name": "STRUCTURAL TEST — NOT ERA5-Drought"}
    if spei_units is not None:
        spei_attributes["units"] = spei_units
    spei_dataset = xr.Dataset(
        data_vars={
            "SPEI3": (
                ("time", "lat", "lon"),
                np.asarray([[[-2.0, -0.5], [-1.2, np.nan]]]),
                spei_attributes,
            )
        },
        coords={
            "time": [np.datetime64("2024-02-01T06:00:00", "ns")],
            "lat": ("lat", latitudes, {"standard_name": "latitude"}),
            "lon": ("lon", longitudes, {"standard_name": "longitude"}),
        },
        attrs={"fixture": "STRUCTURAL TEST ONLY — NOT CLIMATE DATA"},
    )
    spei_dataset.to_netcdf(
        spei_member,
        engine="h5netcdf",
        encoding={"SPEI3": {"_FillValue": -9999.0}},
    )

    quality_member = root / "STRUCTURAL_TEST_QUALITY_NOT_CLIMATE.nc"
    quality_dataset = xr.Dataset(
        data_vars={
            "significance": (
                ("time", "lat", "lon"),
                np.asarray([[[1.0, 1.0], [quality_value, 1.0]]]),
                {
                    "units": "1",
                    "long_name": "STRUCTURAL TEST — NOT A PROVIDER QUALITY FIELD",
                },
            )
        },
        coords={
            "time": [np.datetime64("2020-02-01T00:00:00", "ns")],
            "lat": ("lat", latitudes, {"standard_name": "latitude"}),
            "lon": ("lon", longitudes, {"standard_name": "longitude"}),
        },
        attrs={"fixture": "STRUCTURAL TEST ONLY — NOT CLIMATE DATA"},
    )
    quality_dataset.to_netcdf(quality_member, engine="h5netcdf")

    utci_archive = root / "STRUCTURAL_TEST_UTCI_ARCHIVE_NOT_CLIMATE.nc"
    spei_archive = root / "STRUCTURAL_TEST_SPEI_ARCHIVE_NOT_CLIMATE.nc"
    quality_archive = root / "STRUCTURAL_TEST_QUALITY_ARCHIVE_NOT_CLIMATE.nc"
    _write_zip(utci_archive, utci_members)
    _write_zip(spei_archive, [spei_member])
    _write_zip(quality_archive, [quality_member])
    return utci_archive, spei_archive, quality_archive


def _february_requests() -> tuple[
    AcquisitionRequest,
    AcquisitionRequest,
    AcquisitionRequest,
]:
    requests = [
        request
        for request in build_representative_requests(year=2024, months=(2,))
        if request.region.id == "hot_arid_phoenix"
    ]
    indexed = {request.variable_id: request for request in requests}
    return (
        indexed["utci_daymax_median"],
        indexed["spei_3"],
        indexed["spei_3_quality"],
    )


def test_normalization_selects_daily_max_converts_units_and_applies_quality(
    tmp_path: Path,
) -> None:
    paths = _structural_test_archives(tmp_path)
    requests = _february_requests()

    result = normalize_period(*paths, *requests)

    np.testing.assert_array_equal(result.latitudes, [34.0, 33.75])
    np.testing.assert_array_equal(result.longitudes, [-112.25, -112.0])
    np.testing.assert_allclose(
        result.utci_celsius,
        [[17.0, 18.0], [15.0, 16.0]],
        atol=1e-5,
    )
    np.testing.assert_array_equal(result.utci_valid_day_count, np.full((2, 2), 29))
    np.testing.assert_allclose(
        result.spei_source,
        [[-1.2, np.nan], [-2.0, -0.5]],
        equal_nan=True,
    )
    np.testing.assert_array_equal(result.spei_quality, [[0, 1], [1, 1]])
    np.testing.assert_allclose(
        result.spei_published,
        [[np.nan, np.nan], [-2.0, -0.5]],
        equal_nan=True,
    )
    assert not np.any(result.spei_published == 0)


def test_unitless_adapter_is_product_versioned_and_rejects_unexpected_units(
    tmp_path: Path,
) -> None:
    paths = _structural_test_archives(tmp_path, utci_units="degree_Celsius")
    requests = _february_requests()

    with pytest.raises(NormalizationError, match="unexpected UTCI unit"):
        normalize_period(*paths, *requests)


def test_spei_adapter_rejects_unexpected_unit(
    tmp_path: Path,
) -> None:
    paths = _structural_test_archives(tmp_path, spei_units="millimetres")
    requests = _february_requests()

    with pytest.raises(NormalizationError, match="unexpected SPEI-3 unit"):
        normalize_period(*paths, *requests)


def test_quality_field_rejects_values_outside_provider_contract(
    tmp_path: Path,
) -> None:
    paths = _structural_test_archives(tmp_path, quality_value=2.0)
    requests = _february_requests()

    with pytest.raises(NormalizationError, match="quality values must be 0, 1, or nodata"):
        normalize_period(*paths, *requests)


def _independent_center_value(path: Path, variable: str) -> float:
    with zipfile.ZipFile(path) as archive, TemporaryDirectory() as temp:
        values: list[float] = []
        for index, name in enumerate(archive.namelist()):
            extracted = Path(temp) / f"{index:03d}.nc"
            extracted.write_bytes(archive.read(name))
            with xr.open_dataset(extracted) as dataset:
                values.append(float(dataset[variable].values[0, 1, 1]))
    return statistics.median(values)


def test_official_sample_matches_independent_center_calculation_and_is_idempotent(
    tmp_path: Path,
) -> None:
    expected_probe = (
        OFFICIAL_RAW_ROOT / "utci_daymax_median" / "v1_1" / "hot_arid_phoenix" / "2024" / "01.nc"
    )
    if not expected_probe.is_file():
        pytest.skip("bounded official sample is not present in this checkout")

    output_root = tmp_path / "published"
    report = normalize_representative_sample(
        OFFICIAL_RAW_ROOT,
        output_root,
        manifests_root=REPOSITORY_ROOT / "config" / "variables",
    )
    first_checksums = {output["region_id"]: output["sha256"] for output in report["outputs"]}
    second_report = normalize_representative_sample(
        OFFICIAL_RAW_ROOT,
        output_root,
        manifests_root=REPOSITORY_ROOT / "config" / "variables",
    )
    second_checksums = {
        output["region_id"]: output["sha256"] for output in second_report["outputs"]
    }

    assert first_checksums == second_checksums
    assert report["fixture"] is False
    assert report["source_audit_complete"] is True
    assert report["storage_preflight"]["approved"] is True
    assert report["temporal_retention"]["utci_source_frequency"] == "daily maximum"
    assert (
        report["temporal_retention"]["utci_published_frequency"]
        == "monthly median of daily maximum"
    )
    assert len(report["outputs"]) == 4
    assert len(report["golden_center_cell_samples"]) == 8

    for sample in report["golden_center_cell_samples"]:
        region = sample["region_id"]
        month = sample["month"]
        utci_path = (
            OFFICIAL_RAW_ROOT / "utci_daymax_median" / "v1_1" / region / "2024" / f"{month:02d}.nc"
        )
        independent_celsius = (
            _independent_center_value(
                utci_path,
                "utci_daily_max",
            )
            - 273.15
        )
        assert sample["utci_daymax_median_celsius"] == pytest.approx(
            independent_celsius,
            abs=1e-5,
        )
        spei_path = OFFICIAL_RAW_ROOT / "spei_3" / "v1_0" / region / "2024" / f"{month:02d}.nc"
        quality_path = (
            OFFICIAL_RAW_ROOT
            / "spei_3_quality"
            / "v1_0"
            / region
            / "reference-period"
            / f"{month:02d}.nc"
        )
        independent_spei = _independent_center_value(spei_path, "SPEI3")
        independent_quality = _independent_center_value(
            quality_path,
            "significance",
        )
        if np.isfinite(independent_spei):
            assert sample["spei_3_source"] == pytest.approx(
                independent_spei,
                abs=1e-6,
            )
        else:
            assert sample["spei_3_source"] is None
        assert sample["spei_quality_flag"] == int(independent_quality)
        if independent_quality == 1 and np.isfinite(independent_spei):
            assert sample["spei_3_published"] == pytest.approx(
                independent_spei,
                abs=1e-6,
            )
        else:
            assert sample["spei_3_published"] is None

    southern = next(
        sample
        for sample in report["golden_center_cell_samples"]
        if sample["region_id"] == "utci_southern_limit" and sample["month"] == 1
    )
    assert southern["spei_3_source"] is None
    assert southern["spei_3_published"] is None
    assert southern["spei_quality_flag"] == 0
    assert southern["spei_3_class"] == "No data"

    output = output_root / "v1" / "2024" / "hot_arid_phoenix.nc"
    with xr.open_dataset(output) as dataset:
        assert dataset.attrs["fixture"] == "false"
        assert dataset.attrs["crs"] == "EPSG:4326"
        assert dataset.attrs["published_temporal_frequency"] == "monthly"
        assert "daily maximum UTCI" in dataset.attrs["source_temporal_frequency"]
        assert list(dataset.sizes) == ["time", "latitude", "longitude"]
        assert dataset.sizes["time"] == 2
        assert dataset["spei_3"].attrs["quality_rule"]
        assert json.loads(json.dumps(report))["status"] == "complete"


def test_normalization_preflight_blocks_before_source_inspection(
    tmp_path: Path,
) -> None:
    blocked_policy = replace(
        load_storage_policy(),
        minimum_free_reserve_bytes=10**18,
    )

    with pytest.raises(StorageLimitError) as raised:
        normalize_representative_sample(
            tmp_path / "missing-raw",
            tmp_path / "published",
            manifests_root=REPOSITORY_ROOT / "config" / "variables",
            storage_policy=blocked_policy,
        )

    assert raised.value.reason_code == "free_space_reserve"
