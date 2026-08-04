from __future__ import annotations

import pytest

from thermal_drought.months import (
    ALL_MONTHS_MASK,
    format_period,
    hex_to_mask,
    mask_to_hex,
    mask_to_months,
    months_to_mask,
)


def test_all_4095_masks_round_trip() -> None:
    for mask in range(1, ALL_MONTHS_MASK + 1):
        months = mask_to_months(mask)
        assert months_to_mask(months) == mask
        assert hex_to_mask(mask_to_hex(mask)) == mask


@pytest.mark.parametrize(
    ("months", "expected"),
    [
        ([1], "Jan"),
        ([1, 3, 4, 5, 9], "Jan, Mar–May, Sep"),
        ([1, 2, 11, 12], "Jan–Feb, Nov–Dec"),
        (range(1, 13), "All year"),
    ],
)
def test_period_formatting(months: object, expected: str) -> None:
    assert format_period(months_to_mask(months)) == expected


@pytest.mark.parametrize("months", [[], [0], [13]])
def test_invalid_month_sets_fail(months: list[int]) -> None:
    with pytest.raises(ValueError):
        months_to_mask(months)


@pytest.mark.parametrize("value", ["", "0", "000", "FFF", "1000", "xyz"])
def test_invalid_url_masks_fail(value: str) -> None:
    with pytest.raises(ValueError):
        hex_to_mask(value)
