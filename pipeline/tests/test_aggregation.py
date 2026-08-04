from __future__ import annotations

import warnings

import numpy as np
import pytest

from thermal_drought.aggregation import (
    MonthAvailabilityError,
    median_for_month_mask,
    median_with_valid_fraction,
    required_valid_months,
)
from thermal_drought.months import ALL_MONTHS_MASK, mask_to_months


@pytest.mark.parametrize(
    ("selected", "required"),
    [(1, 1), (2, 2), (3, 3), (4, 3), (8, 6), (12, 9)],
)
def test_required_valid_months_uses_documented_ceiling(
    selected: int,
    required: int,
) -> None:
    assert required_valid_months(selected) == required


def test_month_median_masks_below_but_not_at_75_percent() -> None:
    values = np.asarray(
        [
            [1.0, 1.0, 0.0],
            [2.0, 2.0, np.nan],
            [3.0, 3.0, np.nan],
            [4.0, np.nan, np.nan],
        ]
    )

    result = median_with_valid_fraction(values)

    assert result.required_valid_month_count == 3
    np.testing.assert_array_equal(result.valid_month_count, [4, 3, 1])
    np.testing.assert_allclose(result.values[:2], [2.5, 2.0])
    assert np.isnan(result.values[2])


def test_one_month_identity_preserves_real_zero_and_masks_nodata() -> None:
    result = median_with_valid_fraction(np.asarray([[0.0, np.nan]]))

    assert result.values[0] == 0.0
    assert np.isnan(result.values[1])
    np.testing.assert_array_equal(result.valid_month_count, [1, 0])


def test_all_4095_masks_match_simple_reference_median() -> None:
    monthly = np.asarray(
        [
            [float(month), np.nan if month in {2, 5, 8} else float(month * 2)]
            for month in range(1, 13)
        ]
    )
    for mask in range(1, ALL_MONTHS_MASK + 1):
        selected = np.asarray([monthly[month - 1] for month in mask_to_months(mask)])
        expected_count = np.sum(np.isfinite(selected), axis=0)
        required = required_valid_months(len(selected))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            expected = np.nanmedian(selected, axis=0)
        expected = np.where(expected_count >= required, expected, np.nan)

        result = median_for_month_mask(
            monthly,
            tuple(range(1, 13)),
            mask,
        )

        np.testing.assert_allclose(result.values, expected, equal_nan=True)
        np.testing.assert_array_equal(result.valid_month_count, expected_count)
        assert result.required_valid_month_count == required


def test_masked_median_is_independent_of_available_month_order() -> None:
    months = (1, 4, 9)
    values = np.asarray([[1.0], [7.0], [3.0]])
    mask = (1 << 0) | (1 << 3) | (1 << 8)

    forward = median_for_month_mask(values, months, mask)
    reverse = median_for_month_mask(values[::-1], tuple(reversed(months)), mask)

    np.testing.assert_array_equal(forward.values, reverse.values)


@pytest.mark.parametrize(
    ("months", "expected"),
    [
        ((1,), 1.0),
        ((1, 2), 1.5),
        ((1, 2, 3), 2.0),
        (tuple(range(1, 13)), 6.5),
    ],
)
def test_one_odd_even_and_all_year_medians(
    months: tuple[int, ...],
    expected: float,
) -> None:
    values = np.arange(1.0, 13.0).reshape(12, 1)
    mask = sum(1 << (month - 1) for month in months)

    result = median_for_month_mask(values, tuple(range(1, 13)), mask)

    assert result.values[0] == expected


def test_masked_median_rejects_unpublished_selected_month() -> None:
    with pytest.raises(MonthAvailabilityError, match="2"):
        median_for_month_mask(np.asarray([[1.0]]), (1,), 0x003)


@pytest.mark.parametrize(
    ("count", "fraction", "error"),
    [(0, 0.75, ValueError), (1, -0.1, ValueError), (1, 1.1, ValueError)],
)
def test_invalid_validity_configuration_fails(
    count: int,
    fraction: float,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        required_valid_months(count, fraction)
