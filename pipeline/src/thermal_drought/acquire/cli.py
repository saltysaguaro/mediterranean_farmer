"""Inspect credentials, emit the bounded request plan, or run official retrieval."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from thermal_drought.acquire.inspection import InspectionError, inspect_raw_root
from thermal_drought.acquire.requests import (
    SOURCE_METADATA,
    AcquisitionRequest,
    build_representative_requests,
    build_sicily_requests,
    plan_sha256,
)
from thermal_drought.acquire.runner import (
    AcquisitionError,
    execute_requests,
    retrieve_with_cdsapi,
)
from thermal_drought.storage import (
    StorageLimitError,
    StoragePolicyError,
    load_storage_policy,
)


@dataclass(frozen=True)
class CredentialStatus:
    """Secret-safe availability status; values are never read or printed."""

    cdsapirc_present: bool
    cdsapirc_nonempty: bool
    environment_url_present: bool
    environment_key_present: bool
    cdsapi_installed: bool

    @property
    def usable_configuration_present(self) -> bool:
        file_ready = self.cdsapirc_present and self.cdsapirc_nonempty
        environment_ready = self.environment_url_present and self.environment_key_present
        return file_ready or environment_ready


def credential_status(
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> CredentialStatus:
    selected_home = Path.home() if home is None else home
    selected_environment = os.environ if environ is None else environ
    credential_file = selected_home / ".cdsapirc"
    return CredentialStatus(
        cdsapirc_present=credential_file.is_file(),
        cdsapirc_nonempty=(credential_file.is_file() and credential_file.stat().st_size > 0),
        environment_url_present=bool(selected_environment.get("CDSAPI_URL")),
        environment_key_present=bool(selected_environment.get("CDSAPI_KEY")),
        cdsapi_installed=importlib.util.find_spec("cdsapi") is not None,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="show only secret-safe access availability")

    plan_parser = subparsers.add_parser("plan", help="emit bounded request metadata")
    plan_parser.add_argument("--scope", choices=["sicily", "representative"], default="sicily")
    plan_parser.add_argument("--years", type=int, nargs="+", default=[2025, 2024])
    plan_parser.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)))
    plan_parser.add_argument("--output", type=Path)

    fetch_parser = subparsers.add_parser("fetch", help="retrieve a bounded acquisition plan")
    fetch_parser.add_argument("--scope", choices=["sicily", "representative"], default="sicily")
    fetch_parser.add_argument("--years", type=int, nargs="+", default=[2025, 2024])
    fetch_parser.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)))
    fetch_parser.add_argument("--raw-root", type=Path, default=Path("data/raw/sicily-release-v1"))
    fetch_parser.add_argument("--storage-policy", type=Path)
    fetch_parser.add_argument(
        "--dataset-id",
        choices=sorted(SOURCE_METADATA),
        help=(
            "retrieve only one official dataset from the exact bounded plan; "
            "the default retrieves both"
        ),
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="inspect verified official NetCDF headers and compare paired grids",
    )
    inspect_parser.add_argument("--scope", choices=["sicily", "representative"], default="sicily")
    inspect_parser.add_argument("--years", type=int, nargs="+", default=[2025, 2024])
    inspect_parser.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)))
    inspect_parser.add_argument("--raw-root", type=Path, default=Path("data/raw/sicily-release-v1"))
    inspect_parser.add_argument("--output", type=Path)
    return parser


def _build_requests(
    scope: str,
    years: tuple[int, ...],
    months: tuple[int, ...],
) -> tuple[AcquisitionRequest, ...]:
    if scope == "sicily":
        return build_sicily_requests(years=years, months=months)
    if len(years) != 1:
        raise ValueError("the representative evidence scope requires exactly one year")
    return build_representative_requests(year=years[0], months=months)


def _plan_json(scope: str, years: tuple[int, ...], months: tuple[int, ...]) -> str:
    requests = _build_requests(scope, years, months)
    plan = {
        "schema_version": "1.0",
        "fixture": False,
        "scope": scope,
        "purpose": (
            "Sicily-only official release acquisition"
            if scope == "sicily"
            else "bounded representative official-data access proof"
        ),
        "plan_sha256": plan_sha256(requests),
        "requests": [request.as_dict() for request in requests],
    }
    return json.dumps(plan, indent=2, sort_keys=True) + "\n"


def _select_dataset(
    requests: Sequence[AcquisitionRequest],
    dataset_id: str | None,
) -> tuple[AcquisitionRequest, ...]:
    if dataset_id is None:
        return tuple(requests)
    selected = tuple(request for request in requests if request.dataset_id == dataset_id)
    if not selected:
        raise ValueError(f"no planned requests found for dataset {dataset_id}")
    return selected


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        status = credential_status()
        print(json.dumps(asdict(status), indent=2, sort_keys=True))
        return 0

    if args.command == "inspect":
        try:
            expected_requests = _build_requests(
                args.scope,
                tuple(args.years),
                months=tuple(args.months),
            )
            report = inspect_raw_root(
                args.raw_root,
                expected_requests=expected_requests,
            )
        except (InspectionError, StorageLimitError, StoragePolicyError, ValueError) as error:
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
                print(f"Official-data inspection failed: {error}")
            return 2
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output is None:
            print(rendered, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        return 0 if report["complete"] is True else 2

    months = tuple(args.months)
    years = tuple(args.years)
    if args.command == "plan":
        plan = _plan_json(args.scope, years, months)
        if args.output is None:
            print(plan, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(plan, encoding="utf-8")
        return 0

    if args.command == "fetch":
        status = credential_status()
        if not status.usable_configuration_present:
            print(
                "Official retrieval blocked: no non-empty .cdsapirc or complete "
                "CDSAPI_URL/CDSAPI_KEY environment configuration was found."
            )
            return 2
        if not status.cdsapi_installed:
            print(
                "Official retrieval blocked: cdsapi is not installed; "
                "install the pipeline data extra."
            )
            return 2
        requests = _select_dataset(
            _build_requests(args.scope, years, months),
            args.dataset_id,
        )
        try:
            policy = load_storage_policy(args.storage_policy)
            results = execute_requests(
                requests,
                args.raw_root,
                retrieve_with_cdsapi,
                storage_policy=policy,
            )
        except (AcquisitionError, StorageLimitError, StoragePolicyError) as error:
            failure = (
                error.as_dict()
                if isinstance(error, (AcquisitionError, StorageLimitError))
                else {
                    "reason_code": "storage_policy_invalid",
                    "detail": str(error),
                }
            )
            print(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "status": "blocked",
                        "fixture": False,
                        "failure": failure,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2
        for result in results:
            duration = (
                "verified receipt"
                if result.retrieval_duration_seconds is None
                else f"{result.retrieval_duration_seconds:.3f}s"
            )
            print(
                f"{result.status}: {result.request_id} "
                f"({result.byte_size} bytes, {duration}, sha256={result.sha256})"
            )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
