"""Privacy-safe production health, freshness, and observability probe."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAXIMUM_MONITOR_RESPONSE_BYTES = 1024 * 1024
ENDPOINTS = ("live", "ready", "availability", "metrics")


def _base_url(value: str, *, allow_http: bool) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("monitor base URL must not contain credentials, a query, or a fragment")
    if parsed.scheme == "https" and parsed.netloc:
        return value.rstrip("/")
    if allow_http and parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}:
        return value.rstrip("/")
    raise ValueError("monitor base URL must use https; only explicit loopback checks may use http")


def _json_request(url: str, timeout: float) -> tuple[dict[str, Any], float]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "sicily-climate-monitor/1.0"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAXIMUM_MONITOR_RESPONSE_BYTES:
            raise ValueError("monitor response exceeds the configured byte limit")
        body = response.read(MAXIMUM_MONITOR_RESPONSE_BYTES + 1)
        if len(body) > MAXIMUM_MONITOR_RESPONSE_BYTES:
            raise ValueError("monitor response exceeds the configured byte limit")
        if response.status != 200:
            raise ValueError(f"monitor endpoint returned HTTP {response.status}")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("monitor endpoint did not return a JSON object")
    return payload, (time.perf_counter() - started) * 1_000


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("availability variable has no retrieval timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("availability variable retrieval timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("availability variable retrieval timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def evaluate(
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
    maximum_freshness_days: int,
) -> dict[str, object]:
    failures: list[str] = []
    live = payloads["live"]
    ready = payloads["ready"]
    availability = payloads["availability"]
    metrics = payloads["metrics"]
    if live.get("status") != "ok" or live.get("live") is not True:
        failures.append("liveness_failed")
    if ready.get("status") != "ok" or ready.get("ready") is not True:
        failures.append("readiness_failed")
    if availability.get("status") != "ok":
        failures.append("availability_failed")
    if (
        availability.get("fixture") is not False
        or availability.get("official_evidence") is not True
    ):
        failures.append("official_release_not_active")
    if not isinstance(availability.get("latest_complete_year"), int):
        failures.append("latest_complete_year_missing")
    variables = availability.get("variables")
    freshness_days: dict[str, float] = {}
    if not isinstance(variables, list) or not variables:
        failures.append("availability_variables_missing")
    else:
        for variable in variables:
            if not isinstance(variable, dict):
                failures.append("availability_variable_invalid")
                continue
            variable_id = str(variable.get("id", "unknown"))
            try:
                retrieved = _parse_timestamp(variable.get("sample_retrieved_at"))
                age = (now.astimezone(timezone.utc) - retrieved).total_seconds() / 86_400
            except ValueError:
                failures.append(f"freshness_invalid:{variable_id}")
                continue
            freshness_days[variable_id] = round(age, 3)
            if age < 0 or age > maximum_freshness_days:
                failures.append(f"freshness_out_of_bounds:{variable_id}")
    if metrics.get("status") != "ok" or not isinstance(metrics.get("counts"), dict):
        failures.append("metrics_failed")
    privacy = metrics.get("privacy")
    if not isinstance(privacy, str) or "coordinates are not recorded" not in privacy:
        failures.append("privacy_contract_missing")
    return {
        "status": "ok" if not failures else "blocked",
        "official_evidence": availability.get("official_evidence") is True,
        "dataset_version": availability.get("dataset_version"),
        "latest_complete_year": availability.get("latest_complete_year"),
        "freshness_days": freshness_days,
        "maximum_freshness_days": maximum_freshness_days,
        "failures": failures,
        "privacy": "No coordinates or query strings are collected by this monitor.",
    }


def probe(
    base_url: str,
    *,
    timeout: float,
    maximum_freshness_days: int,
    allow_http: bool,
) -> dict[str, object]:
    selected_base = _base_url(base_url, allow_http=allow_http)
    payloads: dict[str, Mapping[str, Any]] = {}
    latency: dict[str, float] = {}
    for endpoint in ENDPOINTS:
        payload, elapsed = _json_request(f"{selected_base}/v1/{endpoint}", timeout)
        payloads[endpoint] = payload
        latency[endpoint] = round(elapsed, 3)
    result = evaluate(
        payloads,
        now=datetime.now(timezone.utc),
        maximum_freshness_days=maximum_freshness_days,
    )
    result["latency_ms"] = latency
    result["maximum_endpoint_latency_ms"] = round(max(latency.values()), 3)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--maximum-freshness-days", type=int, default=120)
    parser.add_argument("--allow-http", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 0.1 <= args.timeout <= 30:
        print(json.dumps({"status": "blocked", "reason": "timeout must be 0.1-30 seconds"}))
        return 2
    if not 1 <= args.maximum_freshness_days <= 730:
        print(json.dumps({"status": "blocked", "reason": "freshness limit must be 1-730 days"}))
        return 2
    try:
        report = probe(
            args.base_url,
            timeout=args.timeout,
            maximum_freshness_days=args.maximum_freshness_days,
            allow_http=args.allow_http,
        )
    except (json.JSONDecodeError, OSError, urllib.error.URLError, ValueError) as error:
        report = {"status": "blocked", "reason": str(error)}
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered)
        temporary.replace(args.output)
    print(rendered, end="")
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
