"""Shared selected-month aggregation rules for canonical climate arrays."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from thermal_drought.months import mask_to_months

FloatArray = NDArray[np.float64]
CountArray = NDArray[np.int64]


@dataclass(frozen=True)
class MedianResult:
    """A selected-month median together with its per-cell valid-month count."""

    values: FloatArray
    valid_month_count: CountArray
    required_valid_month_count: int


class MonthAvailabilityError(ValueError):
    """Raised when a selected month is absent from the published product."""

    def __init__(self, unavailable_months: tuple[int, ...]) -> None:
        self.unavailable_months = unavailable_months
        rendered = ", ".join(str(month) for month in unavailable_months)
        super().__init__(f"selected months are unavailable: {rendered}")


def required_valid_months(
    selected_month_count: int,
    minimum_valid_fraction: float = 0.75,
) -> int:
    """Return the documented ceil(selected months × fraction), with minimum one."""

    if isinstance(selected_month_count, bool) or not isinstance(selected_month_count, int):
        raise TypeError("selected month count must be an integer")
    if selected_month_count < 1:
        raise ValueError("at least one selected month is required")
    if not 0 <= minimum_valid_fraction <= 1:
        raise ValueError("minimum valid fraction must be between zero and one")
    return max(1, math.ceil(selected_month_count * minimum_valid_fraction))


def median_with_valid_fraction(
    monthly_values: NDArray[Any],
    minimum_valid_fraction: float = 0.75,
) -> MedianResult:
    """Median the first (month) axis and mask cells below the validity threshold."""

    values = np.asarray(monthly_values, dtype=np.float64)
    if values.ndim < 1 or values.shape[0] < 1:
        raise ValueError("monthly values must have a non-empty first axis")
    required = required_valid_months(values.shape[0], minimum_valid_fraction)
    finite_values = np.where(np.isfinite(values), values, np.nan)
    valid_count = np.sum(np.isfinite(finite_values), axis=0, dtype=np.int64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        medians = np.nanmedian(finite_values, axis=0)
    masked = np.where(valid_count >= required, medians, np.nan)
    return MedianResult(
        values=np.asarray(masked, dtype=np.float64),
        valid_month_count=np.asarray(valid_count, dtype=np.int64),
        required_valid_month_count=required,
    )


def median_for_month_mask(
    monthly_values: NDArray[Any],
    available_months: tuple[int, ...],
    month_mask: int,
    minimum_valid_fraction: float = 0.75,
) -> MedianResult:
    """Select canonical calendar months by mask, then apply the shared median rule."""

    values = np.asarray(monthly_values)
    if values.ndim < 1:
        raise ValueError("monthly values must have a month axis")
    if values.shape[0] != len(available_months):
        raise ValueError("available months must match the first array axis")
    if len(set(available_months)) != len(available_months) or any(
        month < 1 or month > 12 for month in available_months
    ):
        raise ValueError("available months must be unique calendar month numbers")

    requested = mask_to_months(month_mask)
    unavailable = tuple(month for month in requested if month not in available_months)
    if unavailable:
        raise MonthAvailabilityError(unavailable)
    month_indexes = {month: index for index, month in enumerate(available_months)}
    selected = np.asarray([values[month_indexes[month]] for month in requested])
    return median_with_valid_fraction(selected, minimum_valid_fraction)
