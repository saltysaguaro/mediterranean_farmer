"""Normalize the bounded official acquisition proof into local monthly products."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from thermal_drought.acquire.inspection import InspectionError
from thermal_drought.normalize.core import (
    NormalizationError,
    normalize_representative_sample,
)
from thermal_drought.storage import StorageLimitError, StoragePolicyError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--months", type=int, nargs="+", default=[1, 7])
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/published/night-3-official-sample"),
    )
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = normalize_representative_sample(
            raw_root=args.raw_root,
            output_root=args.output_root,
            year=args.year,
            months=tuple(args.months),
        )
    except (
        InspectionError,
        NormalizationError,
        StorageLimitError,
        StoragePolicyError,
        ValueError,
    ) as error:
        if isinstance(error, StorageLimitError):
            print(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "status": "blocked",
                        "fixture": False,
                        "failure": error.as_dict(),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"Official-sample normalization failed: {error}")
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report is None:
        print(rendered, end="")
    else:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
