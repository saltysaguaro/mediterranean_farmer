from datetime import date

from thermal_drought.refresh import candidate_complete_years, compare_outputs, refresh_plan


def _report(sha_2024: str = "a") -> dict[str, object]:
    return {
        "years": [2024, 2025],
        "outputs": [
            {
                "path": "data/published/release/v1/2024/sicily.nc",
                "sha256": sha_2024,
                "byte_size": 10,
                "months": list(range(1, 13)),
                "included_scope_cells": 44,
            },
            {
                "path": "data/published/release/v1/2025/sicily.nc",
                "sha256": "b",
                "byte_size": 11,
                "months": list(range(1, 13)),
                "included_scope_cells": 44,
            },
        ],
    }


def test_refresh_plan_uses_only_two_prior_calendar_years() -> None:
    assert candidate_complete_years(date(2026, 8, 30)) == (2025, 2024)
    plan = refresh_plan(date(2027, 1, 1))
    assert plan["candidate_years"] == [2026, 2025]
    assert len(plan["months"]) == 12


def test_refresh_comparison_detects_any_product_change() -> None:
    assert compare_outputs(_report(), _report())["status"] == "complete"
    assert compare_outputs(_report(), _report("changed"))["status"] == "blocked"
    equivalent = compare_outputs(
        _report(),
        _report("changed"),
        scientific_equivalence={2024: True, 2025: True},
    )
    assert equivalent["status"] == "complete"
    assert equivalent["outputs"][0]["byte_identical"] is False
