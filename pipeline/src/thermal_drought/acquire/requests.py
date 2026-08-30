"""Build bounded CDS requests for ERA5-HEAT and deterministic ERA5-Drought."""

from __future__ import annotations

import calendar
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UTCI_DATASET_ID = "derived-utci-historical"
DROUGHT_DATASET_ID = "derived-drought-historical-monthly"


@dataclass(frozen=True)
class Region:
    """A small representative CDS extraction area."""

    id: str
    label: str
    north: float
    west: float
    south: float
    east: float
    purpose: str

    def __post_init__(self) -> None:
        if not self.id or not self.id.replace("_", "").isalnum():
            raise ValueError("region id must contain only letters, digits, and underscores")
        if not -90 <= self.south < self.north <= 90:
            raise ValueError("region latitude bounds must be ordered south to north")
        if not -180 <= self.west < self.east <= 180:
            raise ValueError("region longitude bounds must be ordered west to east")

    @property
    def cds_area(self) -> list[float]:
        """Return CDS area order: north, west, south, east."""

        return [self.north, self.west, self.south, self.east]


REPRESENTATIVE_REGIONS = (
    Region(
        id="hot_arid_phoenix",
        label="Phoenix, Arizona",
        north=34.25,
        west=-112.25,
        south=33.75,
        east=-111.75,
        purpose="hot/arid conditions",
    ),
    Region(
        id="temperate_paris",
        label="Paris, France",
        north=49.00,
        west=2.00,
        south=48.50,
        east=2.50,
        purpose="temperate conditions",
    ),
    Region(
        id="cold_fairbanks",
        label="Fairbanks, Alaska",
        north=65.00,
        west=-148.00,
        south=64.50,
        east=-147.50,
        purpose="cold conditions",
    ),
    Region(
        id="utci_southern_limit",
        label="ERA5-HEAT southern coverage limit",
        north=-59.50,
        west=0.00,
        south=-60.00,
        east=0.50,
        purpose="UTCI coverage-edge behavior, if the provider response permits verification",
    ),
)

SICILY_REGION = Region(
    id="sicily",
    label="Sicilia, Italy",
    north=39.0,
    west=11.75,
    south=35.25,
    east=15.75,
    purpose="Sicily-only production scope on the provider-aligned 0.25-degree grid",
)


@dataclass(frozen=True)
class SourceMetadata:
    """Provider metadata retained beside every verified acquisition."""

    provider: str
    dataset_url: str
    doi: str
    product_version: str
    license: str
    citation: str
    expected_units: dict[str, str]
    expected_coordinates: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "dataset_url": self.dataset_url,
            "doi": self.doi,
            "product_version": self.product_version,
            "license": self.license,
            "citation": self.citation,
            "expected_units": self.expected_units,
            "expected_coordinates": list(self.expected_coordinates),
        }


SOURCE_METADATA = {
    UTCI_DATASET_ID: SourceMetadata(
        provider="ECMWF/Copernicus Climate Change Service",
        dataset_url=("https://cds.climate.copernicus.eu/datasets/derived-utci-historical"),
        doi="10.24381/cds.553b7518",
        product_version="1.1",
        license="Licence to use Copernicus Products",
        citation=(
            "Di Napoli et al. (2021), ERA5-HEAT: a global gridded historical "
            "dataset of human thermal comfort indices from climate reanalysis."
        ),
        expected_units={"daily minimum UTCI": "K", "daily maximum UTCI": "K"},
        expected_coordinates=("time", "latitude", "longitude"),
    ),
    DROUGHT_DATASET_ID: SourceMetadata(
        provider="ECMWF/Copernicus Climate Change Service",
        dataset_url=(
            "https://cds.climate.copernicus.eu/datasets/derived-drought-historical-monthly"
        ),
        doi="10.24381/9bea5e16",
        product_version="1.0",
        license="CC-BY-4.0",
        citation=(
            "Keune et al. (2025), ERA5-Drought: Global drought indices based "
            "on ECMWF reanalysis, Scientific Data 12, 616."
        ),
        expected_units={
            "SPEI-3": "standard deviations (dimensionless)",
            "SPEI normality quality": "dimensionless binary flag",
        },
        expected_coordinates=("time", "latitude", "longitude"),
    ),
}


@dataclass(frozen=True)
class AcquisitionRequest:
    """One immutable dataset/region/year/month acquisition partition."""

    variable_id: str
    dataset_id: str
    region: Region
    year: int | None
    month: int
    request: dict[str, object]

    def __post_init__(self) -> None:
        if self.dataset_id not in SOURCE_METADATA:
            raise ValueError(f"unsupported dataset: {self.dataset_id}")
        if self.year is not None and not 1940 <= self.year <= 2200:
            raise ValueError("year must be between 1940 and 2200")
        if not 1 <= self.month <= 12:
            raise ValueError("month must be between 1 and 12")

    @property
    def request_id(self) -> str:
        period = str(self.year) if self.year is not None else "reference-period"
        return f"{self.variable_id}-{self.region.id}-{period}-{self.month:02d}"

    @property
    def target_relative_path(self) -> Path:
        version = SOURCE_METADATA[self.dataset_id].product_version.replace(".", "_")
        period = str(self.year) if self.year is not None else "reference-period"
        return (
            Path(self.variable_id)
            / f"v{version}"
            / self.region.id
            / period
            / f"{self.month:02d}.nc"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "variable_id": self.variable_id,
            "dataset_id": self.dataset_id,
            "region": {
                "id": self.region.id,
                "label": self.region.label,
                "purpose": self.region.purpose,
                "area": self.region.cds_area,
            },
            "year": self.year,
            "month": self.month,
            "target_relative_path": self.target_relative_path.as_posix(),
            "request": self.request,
            "source": SOURCE_METADATA[self.dataset_id].as_dict(),
        }


def _validate_months(months: tuple[int, ...]) -> None:
    if not months:
        raise ValueError("at least one month is required")
    if len(set(months)) != len(months):
        raise ValueError("months must not contain duplicates")
    if any(month < 1 or month > 12 for month in months):
        raise ValueError("months must be between 1 and 12")


def _utci_request(region: Region, year: int, month: int) -> AcquisitionRequest:
    days_in_month = calendar.monthrange(year, month)[1]
    return AcquisitionRequest(
        variable_id="utci_daymax_median",
        dataset_id=UTCI_DATASET_ID,
        region=region,
        year=year,
        month=month,
        request={
            "variable": ["universal_thermal_climate_index_daily_statistics"],
            "version": "1_1",
            "product_type": "consolidated_dataset",
            "year": [f"{year:04d}"],
            "month": [f"{month:02d}"],
            "day": [f"{day:02d}" for day in range(1, days_in_month + 1)],
            "area": region.cds_area,
        },
    )


def _drought_index_request(region: Region, year: int, month: int) -> AcquisitionRequest:
    return AcquisitionRequest(
        variable_id="spei_3",
        dataset_id=DROUGHT_DATASET_ID,
        region=region,
        year=year,
        month=month,
        request={
            "variable": ["standardised_precipitation_evapotranspiration_index"],
            "accumulation_period": ["3"],
            "version": "1_0",
            "product_type": ["reanalysis"],
            "dataset_type": "consolidated_dataset",
            "year": [f"{year:04d}"],
            "month": [f"{month:02d}"],
            "area": region.cds_area,
        },
    )


def _drought_quality_request(region: Region, month: int) -> AcquisitionRequest:
    return AcquisitionRequest(
        variable_id="spei_3_quality",
        dataset_id=DROUGHT_DATASET_ID,
        region=region,
        year=None,
        month=month,
        request={
            "variable": ["test_for_normality_spei"],
            "accumulation_period": ["3"],
            "version": "1_0",
            "product_type": ["reanalysis"],
            "dataset_type": "consolidated_dataset",
            "month": [f"{month:02d}"],
            "area": region.cds_area,
        },
    )


def build_representative_requests(
    year: int = 2024,
    months: tuple[int, ...] = (1, 7),
    regions: tuple[Region, ...] = REPRESENTATIVE_REGIONS,
) -> tuple[AcquisitionRequest, ...]:
    """Build a bounded two-season plan across the required representative regions."""

    _validate_months(months)
    if not regions:
        raise ValueError("at least one region is required")

    requests: list[AcquisitionRequest] = []
    for region in regions:
        for month in months:
            requests.append(_utci_request(region, year, month))
            requests.append(_drought_index_request(region, year, month))
            requests.append(_drought_quality_request(region, month))
    return tuple(requests)


def build_sicily_requests(
    years: tuple[int, ...] = (2025, 2024),
    months: tuple[int, ...] = tuple(range(1, 13)),
) -> tuple[AcquisitionRequest, ...]:
    """Build the bounded two-year Sicily release plan.

    Provider quality is reference-period data keyed by calendar month, so it is
    requested once and reused for every selected analysis year.
    """

    _validate_months(months)
    if not years:
        raise ValueError("at least one year is required")
    if len(set(years)) != len(years):
        raise ValueError("years must not contain duplicates")
    if any(year < 1940 or year > 2200 for year in years):
        raise ValueError("years must be between 1940 and 2200")

    requests: list[AcquisitionRequest] = []
    for year in years:
        for month in months:
            requests.append(_utci_request(SICILY_REGION, year, month))
            requests.append(_drought_index_request(SICILY_REGION, year, month))
    for month in months:
        requests.append(_drought_quality_request(SICILY_REGION, month))
    return tuple(requests)


def plan_sha256(requests: Sequence[AcquisitionRequest]) -> str:
    """Fingerprint the complete plan independently of request iteration order."""

    request_ids = [request.request_id for request in requests]
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("acquisition plan request IDs must be unique")
    encoded = json.dumps(
        sorted((request.as_dict() for request in requests), key=lambda value: value["request_id"]),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
