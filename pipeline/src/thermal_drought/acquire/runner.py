"""Execute acquisition partitions atomically and retain verifiable receipts."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from thermal_drought.acquire.requests import SOURCE_METADATA, AcquisitionRequest
from thermal_drought.storage import (
    StorageLimitError,
    StoragePolicy,
    load_storage_policy,
    managed_scope_root,
    preflight_managed_write,
)


class AcquisitionError(RuntimeError):
    """A secret-safe provider failure tied to one planned request."""

    def __init__(
        self,
        request: AcquisitionRequest,
        reason_code: str,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.request_id = request.request_id
        self.dataset_id = request.dataset_id
        self.reason_code = reason_code
        self.detail = detail

    def as_dict(self) -> dict[str, str]:
        """Return an automation-friendly error without provider credentials."""

        return {
            "request_id": self.request_id,
            "dataset_id": self.dataset_id,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "dataset_url": SOURCE_METADATA[self.dataset_id].dataset_url,
        }


class Retriever(Protocol):
    """A provider client that writes one request response to a target path."""

    def __call__(
        self,
        dataset_id: str,
        request: Mapping[str, object],
        target: Path,
    ) -> None: ...


@dataclass(frozen=True)
class AcquisitionResult:
    """Outcome of one restartable acquisition attempt."""

    request_id: str
    status: str
    target: Path
    receipt: Path
    sha256: str
    byte_size: int
    retrieval_duration_seconds: float | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_sha256(request: AcquisitionRequest) -> str:
    encoded = json.dumps(
        {
            "dataset_id": request.dataset_id,
            "request": request.request,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def receipt_path(target: Path) -> Path:
    return target.with_suffix(f"{target.suffix}.receipt.json")


def _load_receipt(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _verified_receipt(
    request: AcquisitionRequest,
    target: Path,
    sidecar: Path,
    fixture: bool,
) -> tuple[str, int] | None:
    if not target.is_file() or not sidecar.is_file():
        return None
    receipt = _load_receipt(sidecar)
    if (
        receipt is None
        or receipt.get("request_sha256") != request_sha256(request)
        or receipt.get("fixture") is not fixture
    ):
        return None
    file_metadata = receipt.get("file")
    if not isinstance(file_metadata, dict):
        return None
    expected_digest = file_metadata.get("sha256")
    expected_size = file_metadata.get("byte_size")
    if not isinstance(expected_digest, str) or not isinstance(expected_size, int):
        return None
    actual_size = target.stat().st_size
    if actual_size != expected_size:
        return None
    actual_digest = sha256_file(target)
    if actual_digest != expected_digest:
        return None
    return actual_digest, actual_size


def _write_receipt_atomic(path: Path, receipt: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.part")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _provider_error(request: AcquisitionRequest, error: Exception) -> AcquisitionError:
    message = str(error).lower()
    if ("licence" in message or "license" in message) and "not accepted" in message:
        return AcquisitionError(
            request,
            "licence_not_accepted",
            "required dataset licence(s) are not accepted for this CDS account",
        )
    if "401" in message or "unauthorized" in message:
        return AcquisitionError(
            request,
            "authentication_rejected",
            "CDS rejected the configured authentication",
        )
    if "403" in message or "forbidden" in message:
        return AcquisitionError(
            request,
            "access_denied",
            "CDS denied access to the requested dataset",
        )
    return AcquisitionError(
        request,
        "provider_error",
        f"CDS retrieval failed with {type(error).__name__}",
    )


def execute_request(
    request: AcquisitionRequest,
    raw_root: Path,
    retriever: Retriever,
    now: Callable[[], datetime] | None = None,
    fixture: bool = False,
    storage_policy: StoragePolicy | None = None,
) -> AcquisitionResult:
    """Retrieve once, then skip later runs only when data and receipt still verify."""

    target = raw_root / request.target_relative_path
    sidecar = receipt_path(target)

    verified = _verified_receipt(request, target, sidecar, fixture)
    if verified is not None:
        digest, byte_size = verified
        return AcquisitionResult(
            request_id=request.request_id,
            status="verified-existing",
            target=target,
            receipt=sidecar,
            sha256=digest,
            byte_size=byte_size,
            retrieval_duration_seconds=None,
        )

    policy = storage_policy or load_storage_policy()
    partition_reservation = (
        policy.fixture_partition_reservation_bytes
        if fixture
        else policy.maximum_acquisition_partition_bytes
    )
    reservation = partition_reservation + policy.acquisition_receipt_reservation_bytes
    raw_scope = managed_scope_root(policy, "raw", raw_root)
    storage_preflight = preflight_managed_write(
        policy,
        "raw",
        raw_scope,
        reservation,
        operation=f"acquisition:{request.request_id}",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(f"{target.suffix}.part")
    partial.unlink(missing_ok=True)
    retrieval_started = time.perf_counter()
    try:
        try:
            retriever(request.dataset_id, request.request, partial)
        except Exception as error:
            raise _provider_error(request, error) from error
        if not partial.is_file() or partial.stat().st_size == 0:
            raise RuntimeError(f"provider returned no data for {request.request_id}")
        byte_size = partial.stat().st_size
        if byte_size > policy.maximum_acquisition_partition_bytes:
            raise StorageLimitError(
                f"acquisition:{request.request_id}",
                "acquisition_partition_limit",
                (
                    f"provider response is {byte_size} bytes; partition limit is "
                    f"{policy.maximum_acquisition_partition_bytes} bytes"
                ),
                {
                    **storage_preflight,
                    "status": "blocked",
                    "approved": False,
                    "observed_partition_bytes": byte_size,
                    "maximum_acquisition_partition_bytes": (
                        policy.maximum_acquisition_partition_bytes
                    ),
                    "violations": [
                        {
                            "reason_code": "acquisition_partition_limit",
                            "detail": "provider response exceeded the configured partition limit",
                        }
                    ],
                },
            )
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    retrieval_duration_seconds = time.perf_counter() - retrieval_started

    digest = sha256_file(target)
    byte_size = target.stat().st_size
    retrieved_at = (now or (lambda: datetime.now(timezone.utc)))()
    if retrieved_at.tzinfo is None:
        raise ValueError("retrieval timestamp must include a timezone")
    source = SOURCE_METADATA[request.dataset_id]
    receipt = {
        "schema_version": "1.1",
        "fixture": fixture,
        "request_id": request.request_id,
        "dataset_id": request.dataset_id,
        "variable_id": request.variable_id,
        "product_version": source.product_version,
        "request": request.request,
        "request_sha256": request_sha256(request),
        "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat(),
        "retrieval_duration_seconds": round(retrieval_duration_seconds, 6),
        "period": {
            "year": request.year,
            "month": request.month,
        },
        "region": {
            "id": request.region.id,
            "label": request.region.label,
            "purpose": request.region.purpose,
        },
        "source": source.as_dict(),
        "file": {
            "path": target.relative_to(raw_root).as_posix(),
            "byte_size": byte_size,
            "sha256": digest,
        },
        "observed_netcdf_metadata": None,
        "metadata_note": (
            "Expected units and coordinate names come from the provider catalogue. "
            "Run the acquisition inspect command to populate observed NetCDF metadata "
            "before normalization."
        ),
        "storage_policy": {
            "policy_id": policy.policy_id,
            "partition_reservation_bytes": partition_reservation,
            "receipt_reservation_bytes": (policy.acquisition_receipt_reservation_bytes),
            "maximum_acquisition_partition_bytes": (policy.maximum_acquisition_partition_bytes),
        },
    }
    _write_receipt_atomic(sidecar, receipt)
    return AcquisitionResult(
        request_id=request.request_id,
        status="downloaded",
        target=target,
        receipt=sidecar,
        sha256=digest,
        byte_size=byte_size,
        retrieval_duration_seconds=retrieval_duration_seconds,
    )


def execute_requests(
    requests: Sequence[AcquisitionRequest],
    raw_root: Path,
    retriever: Retriever,
    *,
    storage_policy: StoragePolicy | None = None,
) -> tuple[AcquisitionResult, ...]:
    policy = storage_policy or load_storage_policy()
    return tuple(
        execute_request(
            request,
            raw_root,
            retriever,
            storage_policy=policy,
        )
        for request in requests
    )


def retrieve_with_cdsapi(
    dataset_id: str,
    request: Mapping[str, object],
    target: Path,
) -> None:
    """Use the optional official client without importing it during normal checks."""

    try:
        cdsapi = importlib.import_module("cdsapi")
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "cdsapi is not installed; install the pipeline data extra before retrieval"
        ) from error
    client = cdsapi.Client(retry_max=3, sleep_max=10, timeout=120)
    client.retrieve(dataset_id, dict(request), str(target))
