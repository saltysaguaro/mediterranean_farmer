"""Canonical month-set representation and formatting."""

from __future__ import annotations

from collections.abc import Iterable

MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
ALL_MONTHS_MASK = 0xFFF


def validate_mask(mask: int) -> int:
    if isinstance(mask, bool) or not isinstance(mask, int):
        raise TypeError("month mask must be an integer")
    if not 1 <= mask <= ALL_MONTHS_MASK:
        raise ValueError("month mask must be between 1 and 4095")
    return mask


def months_to_mask(months: Iterable[int]) -> int:
    mask = 0
    for month in months:
        if isinstance(month, bool) or not isinstance(month, int):
            raise TypeError("months must be integers")
        if not 1 <= month <= 12:
            raise ValueError("months must be between 1 and 12")
        mask |= 1 << (month - 1)
    return validate_mask(mask)


def mask_to_months(mask: int) -> tuple[int, ...]:
    validate_mask(mask)
    return tuple(month for month in range(1, 13) if mask & (1 << (month - 1)))


def mask_to_hex(mask: int) -> str:
    return f"{validate_mask(mask):03x}"


def hex_to_mask(value: str) -> int:
    if len(value) != 3 or value.lower() != value:
        raise ValueError("month mask URL value must be three lowercase hexadecimal digits")
    try:
        mask = int(value, 16)
    except ValueError as error:
        raise ValueError("month mask URL value is not hexadecimal") from error
    return validate_mask(mask)


def _format_run(run: list[int]) -> str:
    if len(run) == 1:
        return MONTH_NAMES[run[0] - 1]
    return f"{MONTH_NAMES[run[0] - 1]}–{MONTH_NAMES[run[-1] - 1]}"


def format_period(mask: int) -> str:
    months = mask_to_months(mask)
    if mask == ALL_MONTHS_MASK:
        return "All year"

    runs: list[list[int]] = []
    for month in months:
        if not runs or month != runs[-1][-1] + 1:
            runs.append([month])
        else:
            runs[-1].append(month)
    return ", ".join(_format_run(run) for run in runs)
