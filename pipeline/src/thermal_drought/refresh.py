"""Plan and rehearse a fail-closed two-year Sicily data refresh."""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from thermal_drought.contracts import load_json
from thermal_drought.normalize.core import normalize_sicily_release
from thermal_drought.release_bundle import repository_root


def candidate_complete_years(today: date) -> tuple[int, int]:
    """Choose only prior calendar years; provider completeness is still validated later."""

    return today.year - 1, today.year - 2


def refresh_plan(today: date) -> dict[str, object]:
    years = candidate_complete_years(today)
    return {
        "status": "planned",
        "schema_version": "1.0",
        "scope": "sicily",
        "candidate_years": list(years),
        "months": list(range(1, 13)),
        "publication_policy": (
            "Publish only after both variables, provider quality, all twelve months, "
            "scientific checks, class-distribution review, and immutable bundle validation pass."
        ),
        "promotion_policy": "Never mutate the active release; install and promote a new version.",
    }


def _outputs_by_year(report: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    outputs = report.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError("release report outputs are missing")
    indexed: dict[int, Mapping[str, Any]] = {}
    for output in outputs:
        if not isinstance(output, dict):
            raise ValueError("release output is invalid")
        try:
            year = int(Path(str(output["path"])).parent.name)
        except (KeyError, ValueError) as error:
            raise ValueError("release output year cannot be determined") from error
        indexed[year] = output
    return indexed


def compare_outputs(
    expected_report: Mapping[str, Any],
    candidate_report: Mapping[str, Any],
    *,
    scientific_equivalence: Mapping[int, bool] | None = None,
) -> dict[str, object]:
    expected = _outputs_by_year(expected_report)
    candidate = _outputs_by_year(candidate_report)
    years = sorted(expected)
    records: list[dict[str, object]] = []
    for year in years:
        if year not in candidate:
            raise ValueError(f"refresh candidate is missing year {year}")
        expected_output = expected[year]
        candidate_output = candidate[year]
        byte_identical = (
            candidate_output.get("sha256") == expected_output.get("sha256")
            and candidate_output.get("byte_size") == expected_output.get("byte_size")
            and candidate_output.get("months") == expected_output.get("months")
            and candidate_output.get("included_scope_cells")
            == expected_output.get("included_scope_cells")
        )
        equivalent = (
            byte_identical
            if scientific_equivalence is None
            else scientific_equivalence.get(year, False)
        )
        records.append(
            {
                "year": year,
                "scientifically_equivalent": equivalent,
                "byte_identical": byte_identical,
                "sha256": candidate_output.get("sha256"),
                "byte_size": candidate_output.get("byte_size"),
                "month_count": len(candidate_output.get("months", [])),
                "included_scope_cells": candidate_output.get("included_scope_cells"),
            }
        )
    return {
        "status": (
            "complete"
            if all(record["scientifically_equivalent"] for record in records)
            else "blocked"
        ),
        "years": years,
        "outputs": records,
    }


def scientifically_equivalent(left: Path, right: Path) -> bool:
    """Compare decoded scientific structure and values, not HDF5 container bytes."""

    xr = importlib.import_module("xarray")
    with xr.open_dataset(left, decode_cf=True, mask_and_scale=True) as left_dataset:
        with xr.open_dataset(right, decode_cf=True, mask_and_scale=True) as right_dataset:
            return bool(left_dataset.identical(right_dataset))


def rehearse(root: Path, report_path: Path) -> dict[str, object]:
    root = root.resolve()
    expected_path = root / "pipeline/reports/sicily-release-v1.json"
    expected = load_json(expected_path)
    expected_years = tuple(sorted((int(year) for year in expected["years"]), reverse=True))
    output_root = root / "output/m8-refresh-rehearsal/published"
    candidate = normalize_sicily_release(
        raw_root=root / "data/raw/sicily-release-v1",
        output_root=output_root,
        years=expected_years,
        months=tuple(range(1, 13)),
        manifests_root=root / "config/variables",
        scope_path=root / "config/scope.json",
    )
    expected_outputs = _outputs_by_year(expected)
    candidate_outputs = _outputs_by_year(candidate)
    equivalence = {
        year: scientifically_equivalent(
            root / str(expected_outputs[year]["path"]),
            Path(str(candidate_outputs[year]["path"])),
        )
        for year in expected_outputs
    }
    comparison = compare_outputs(
        expected,
        candidate,
        scientific_equivalence=equivalence,
    )
    report: dict[str, object] = {
        "status": comparison["status"],
        "schema_version": "1.0",
        "milestone": "M8-refresh-rehearsal",
        "fixture": False,
        "official_evidence": candidate.get("source_official_evidence") is True,
        "plan_sha256": candidate.get("plan_sha256"),
        "candidate_years": list(expected_years),
        "months": list(range(1, 13)),
        "comparison": comparison,
        "active_release_unchanged": True,
        "rehearsal_output": "output/m8-refresh-rehearsal/published",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(report_path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(report_path)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=repository_root())
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--date", type=date.fromisoformat, default=date.today())
    rehearsal = subparsers.add_parser("rehearse")
    rehearsal.add_argument(
        "--report",
        type=Path,
        default=Path("pipeline/reports/m8-refresh-rehearsal.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repository_root.resolve()
    try:
        if args.command == "plan":
            report = refresh_plan(args.date)
        else:
            report_path = args.report if args.report.is_absolute() else root / args.report
            report = rehearse(root, report_path)
    except (OSError, RuntimeError, ValueError) as error:
        report = {"status": "blocked", "reason": str(error)}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in {"planned", "complete"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
