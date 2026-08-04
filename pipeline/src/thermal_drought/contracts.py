"""Validate versioned public variable manifests."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class ManifestValidationError(ValueError):
    """Raised when a public variable manifest violates the shared contract."""


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ManifestValidationError(f"{path}: expected a JSON object")
    return value


def schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "manifest.schema.json"


def build_validator(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_manifest(path: Path, validator: Draft202012Validator) -> dict[str, Any]:
    manifest = load_json(path)
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        details = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            details.append(f"{location}: {error.message}")
        raise ManifestValidationError(f"{path}:\n  " + "\n  ".join(details))

    breaks = manifest["classification"]["breaks"]
    if breaks != sorted(breaks) or len(set(breaks)) != len(breaks):
        raise ManifestValidationError(f"{path}: classification.breaks must be strictly ascending")
    assignments = manifest["classification"]["break_assignments"]
    if len(assignments) != len(breaks):
        raise ManifestValidationError(
            f"{path}: classification.break_assignments must match classification.breaks"
        )

    months = manifest["coverage"]["months"]
    if months != list(range(1, 13)):
        raise ManifestValidationError(
            f"{path}: coverage.months must list January through December in order"
        )
    quality = manifest["quality"]
    if quality["policy"] == "none":
        if quality["field"] is not None or quality["pass_values"]:
            raise ManifestValidationError(
                f"{path}: quality policy none requires a null field and no pass values"
            )
    elif quality["field"] is None or not quality["pass_values"]:
        raise ManifestValidationError(
            f"{path}: quality masking or flagging requires a field and pass values"
        )
    return manifest


def manifest_paths(targets: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for target in targets:
        if target.is_dir():
            paths.extend(sorted(target.glob("*.json")))
        else:
            paths.append(target)
    return paths


def validate_targets(targets: Iterable[Path], schema_file: Path | None = None) -> list[Path]:
    selected_schema = load_json(schema_file or schema_path())
    validator = build_validator(selected_schema)
    paths = manifest_paths(targets)
    if not paths:
        raise ManifestValidationError("no variable manifests found")
    for path in paths:
        validate_manifest(path, validator)
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="validate manifest files")
    validate_parser.add_argument("targets", nargs="+", type=Path)
    validate_parser.add_argument("--schema", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        try:
            paths = validate_targets(args.targets, args.schema)
        except (ManifestValidationError, json.JSONDecodeError) as error:
            print(error)
            return 1
        print(f"Validated {len(paths)} variable manifest(s).")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
