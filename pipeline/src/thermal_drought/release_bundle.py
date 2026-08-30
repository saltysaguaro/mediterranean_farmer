"""Package, install, promote, and roll back immutable Sicily release bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from thermal_drought.api.core import DataService
from thermal_drought.contracts import load_json

MAXIMUM_BUNDLE_BYTES = 16 * 1024 * 1024
MAXIMUM_EXPANDED_BYTES = 32 * 1024 * 1024
MAXIMUM_BUNDLE_FILES = 64
REQUIRED_SOURCE_PATHS = (
    "config/app.json",
    "config/manifest.schema.json",
    "config/scope.json",
    "config/storage-policy.json",
    "config/variables/spei_3.json",
    "config/variables/utci_daymax_median.json",
    "pipeline/reports/sicily-release-v1.json",
    "pipeline/reports/sicily-source-audit-v1.json",
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_paths(root: Path) -> tuple[Path, ...]:
    service = DataService.from_repository(root)
    paths = [root / relative for relative in REQUIRED_SOURCE_PATHS]
    paths.extend(product.path for product in service.release.products)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"release bundle input is missing: {missing[0]}")
    resolved_root = root.resolve()
    for path in paths:
        try:
            path.resolve().relative_to(resolved_root)
        except ValueError as error:
            raise ValueError(f"release bundle input escapes the repository: {path}") from error
    return tuple(sorted(set(paths)))


def _zip_info(relative: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def build_bundle(root: Path, output: Path) -> dict[str, object]:
    """Build one deterministic deployable archive without placing climate data in Git."""

    root = root.resolve()
    output_root = (root / "output").resolve()
    output = output.resolve()
    try:
        output.relative_to(output_root)
    except ValueError as error:
        raise ValueError("release bundles must be written below ignored output/") from error
    paths = _required_paths(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as bundle:
        for path in paths:
            relative = path.relative_to(root).as_posix()
            bundle.writestr(_zip_info(relative), path.read_bytes())
    if temporary.stat().st_size > MAXIMUM_BUNDLE_BYTES:
        temporary.unlink(missing_ok=True)
        raise ValueError("release bundle exceeds the configured byte limit")
    temporary.replace(output)
    manifest: dict[str, object] = {
        "status": "complete",
        "schema_version": "1.0",
        "dataset_version": "sicily-2024-2025-v1",
        "bundle": str(output.relative_to(root)),
        "bundle_bytes": output.stat().st_size,
        "bundle_sha256": sha256_file(output),
        "file_count": len(paths),
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in paths
        ],
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    temporary_manifest = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temporary_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary_manifest.replace(manifest_path)
    return manifest


def _validate_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe release bundle path: {info.filename}")
    file_type = (info.external_attr >> 16) & 0o170000
    if file_type not in {0, 0o100000}:
        raise ValueError(f"release bundle contains a non-regular file: {info.filename}")
    if info.flag_bits & 0x1:
        raise ValueError(f"release bundle contains an encrypted file: {info.filename}")


def inspect_bundle(bundle_path: Path, expected_sha256: str | None = None) -> dict[str, object]:
    """Validate archive identity, bounds, paths, duplicates, and required contents."""

    if not bundle_path.is_file():
        raise ValueError(f"release bundle is missing: {bundle_path}")
    size = bundle_path.stat().st_size
    if size > MAXIMUM_BUNDLE_BYTES:
        raise ValueError("release bundle exceeds the configured byte limit")
    digest = sha256_file(bundle_path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("release bundle checksum mismatch")
    with zipfile.ZipFile(bundle_path) as bundle:
        infos = bundle.infolist()
        if not infos or len(infos) > MAXIMUM_BUNDLE_FILES:
            raise ValueError("release bundle file count is invalid")
        if len({info.filename for info in infos}) != len(infos):
            raise ValueError("release bundle contains duplicate paths")
        for info in infos:
            _validate_member(info)
        expanded = sum(info.file_size for info in infos)
        if expanded > MAXIMUM_EXPANDED_BYTES:
            raise ValueError("release bundle exceeds the expanded byte limit")
        names = {info.filename for info in infos}
        missing = sorted(set(REQUIRED_SOURCE_PATHS) - names)
        if missing:
            raise ValueError(f"release bundle is missing required file: {missing[0]}")
    return {
        "status": "complete",
        "bundle_sha256": digest,
        "bundle_bytes": size,
        "file_count": len(infos),
        "expanded_bytes": expanded,
    }


def _download(source: str, destination: Path) -> None:
    parsed = urllib.parse.urlsplit(source)
    if parsed.scheme not in {"https", "file"}:
        raise ValueError("release bundle source must use https or an explicit file URL")
    request = urllib.request.Request(source, headers={"User-Agent": "sicily-climate-service/1.0"})
    total = 0
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAXIMUM_BUNDLE_BYTES:
                raise ValueError("remote release bundle exceeds the configured byte limit")
            handle.write(chunk)


@dataclass(frozen=True)
class ReleasePointer:
    current: str
    previous: str | None
    promoted_at: str


class ReleaseStore:
    """Versioned local materialization with one atomic mutable release pointer."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.releases = self.root / "releases"
        self.pointer_path = self.root / "current.json"

    def install(self, source: str, expected_sha256: str) -> Path:
        if len(expected_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in expected_sha256
        ):
            raise ValueError("expected release SHA-256 is invalid")
        target = self.releases / expected_sha256
        if target.is_dir():
            DataService.from_repository(target)
            return target
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="release-download-", dir=self.root) as temporary:
            temporary_root = Path(temporary)
            bundle_path = temporary_root / "release.zip"
            _download(source, bundle_path)
            inspect_bundle(bundle_path, expected_sha256)
            extracted = temporary_root / "extracted"
            extracted.mkdir()
            with zipfile.ZipFile(bundle_path) as bundle:
                for info in bundle.infolist():
                    _validate_member(info)
                    destination = extracted / PurePosixPath(info.filename)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with (
                        bundle.open(info) as source_handle,
                        destination.open("wb") as output_handle,
                    ):
                        shutil.copyfileobj(source_handle, output_handle)
            DataService.from_repository(extracted)
            self.releases.mkdir(parents=True, exist_ok=True)
            extracted.replace(target)
        return target

    def pointer(self) -> ReleasePointer | None:
        if not self.pointer_path.is_file():
            return None
        raw = load_json(self.pointer_path)
        return ReleasePointer(
            current=str(raw["current"]),
            previous=None if raw.get("previous") is None else str(raw["previous"]),
            promoted_at=str(raw["promoted_at"]),
        )

    def promote(self, release_id: str) -> ReleasePointer:
        target = self.releases / release_id
        if not target.is_dir():
            raise ValueError("cannot promote a release that is not installed")
        DataService.from_repository(target)
        existing = self.pointer()
        pointer = ReleasePointer(
            current=release_id,
            previous=None if existing is None else existing.current,
            promoted_at=datetime.now(timezone.utc).isoformat(),
        )
        self._write_pointer(pointer)
        return pointer

    def rollback(self) -> ReleasePointer:
        existing = self.pointer()
        if existing is None or existing.previous is None:
            raise ValueError("no previous release is available for rollback")
        if not (self.releases / existing.previous).is_dir():
            raise ValueError("the previous release is no longer installed")
        pointer = ReleasePointer(
            current=existing.previous,
            previous=existing.current,
            promoted_at=datetime.now(timezone.utc).isoformat(),
        )
        self._write_pointer(pointer)
        return pointer

    def current_root(self) -> Path:
        pointer = self.pointer()
        if pointer is None:
            raise ValueError("no release is currently promoted")
        target = self.releases / pointer.current
        DataService.from_repository(target)
        return target

    def _write_pointer(self, pointer: ReleasePointer) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.pointer_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "current": pointer.current,
                    "previous": pointer.previous,
                    "promoted_at": pointer.promoted_at,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        temporary.replace(self.pointer_path)


def materialize_environment_release(default_root: Path) -> Path:
    """Use a remote immutable release when configured, otherwise preserve local behavior."""

    source = os.environ.get("THERMAL_DROUGHT_RELEASE_BUNDLE_URL")
    expected = os.environ.get("THERMAL_DROUGHT_RELEASE_BUNDLE_SHA256")
    if source is None and expected is None:
        return default_root
    if not source or not expected:
        raise ValueError("both release bundle URL and SHA-256 must be configured")
    store_path = Path(os.environ.get("THERMAL_DROUGHT_RELEASE_STORE", "/var/lib/thermal-drought"))
    store = ReleaseStore(store_path)
    store.install(source, expected)
    pointer = store.pointer()
    if pointer is None or pointer.current != expected:
        store.promote(expected)
    return store.current_root()


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=repository_root())
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument(
        "--output",
        type=Path,
        default=Path("output/releases/sicily-2024-2025-v1.zip"),
    )
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("bundle", type=Path)
    inspect.add_argument("--sha256")
    install = subparsers.add_parser("install")
    install.add_argument("source")
    install.add_argument("sha256")
    install.add_argument("--store", type=Path, required=True)
    promote = subparsers.add_parser("promote")
    promote.add_argument("release_id")
    promote.add_argument("--store", type=Path, required=True)
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--store", type=Path, required=True)
    status = subparsers.add_parser("status")
    status.add_argument("--store", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repository_root.resolve()
    try:
        if args.command == "build":
            output = args.output if args.output.is_absolute() else root / args.output
            _print(build_bundle(root, output))
        elif args.command == "inspect":
            _print(inspect_bundle(args.bundle.resolve(), args.sha256))
        elif args.command == "install":
            target = ReleaseStore(args.store).install(args.source, args.sha256)
            _print({"status": "installed", "release_root": str(target)})
        elif args.command == "promote":
            _print(ReleaseStore(args.store).promote(args.release_id).__dict__)
        elif args.command == "rollback":
            _print(ReleaseStore(args.store).rollback().__dict__)
        elif args.command == "status":
            pointer = ReleaseStore(args.store).pointer()
            _print({"status": "ok", "pointer": None if pointer is None else pointer.__dict__})
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        _print({"status": "blocked", "reason": str(error)})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
