"""Dependency-light WSGI routing for the bounded local data service."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs

from thermal_drought.api.core import DataService, ServiceError
from thermal_drought.months import hex_to_mask

StartResponse = Callable[[str, list[tuple[str, str]]], Any]
WsgiApplication = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


class Application:
    """Small WSGI application whose handlers delegate all science to DataService."""

    def __init__(self, service: DataService) -> None:
        self.service = service

    def __call__(
        self,
        environ: dict[str, Any],
        start_response: StartResponse,
    ) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        if method != "GET":
            return _respond(
                start_response,
                405,
                {
                    "status": "error",
                    "error": {
                        "code": "method_not_allowed",
                        "detail": "only GET is supported",
                    },
                },
                extra_headers=[("Allow", "GET")],
            )
        path = str(environ.get("PATH_INFO", ""))
        query_string = str(environ.get("QUERY_STRING", ""))
        try:
            if path == "/v1/health":
                _reject_query(query_string)
                return _respond(
                    start_response,
                    200,
                    self.service.health(),
                    cache_control="no-store",
                )
            if path == "/v1/availability":
                _reject_query(query_string)
                return _respond(
                    start_response,
                    200,
                    self.service.availability(),
                    cache_control="public, max-age=300",
                )
            if path == "/v1/sample":
                params = _query(
                    query_string,
                    required={"x", "year", "months", "lng", "lat"},
                    optional={"y"},
                )
                variables = [params["x"]]
                if params.get("y"):
                    variables.append(params["y"])
                payload, etag = self.service.sample(
                    variables,
                    _integer(params["year"], "year"),
                    _month_mask(params["months"]),
                    _coordinate(params["lat"], "latitude"),
                    _coordinate(params["lng"], "longitude"),
                )
                return _respond(
                    start_response,
                    200,
                    payload,
                    etag=etag,
                    cache_control="public, max-age=300",
                )
            parts = path.strip("/").split("/")
            if len(parts) == 10 and parts[:2] == ["v1", "tiles"]:
                _reject_query(query_string)
                y_variable = parts[4]
                variables = [parts[3]]
                if y_variable != "-":
                    variables.append(y_variable)
                payload, etag = self.service.tile(
                    parts[2],
                    variables,
                    _integer(parts[5], "year"),
                    _month_mask(parts[6]),
                    _integer(parts[7], "zoom"),
                    _integer(parts[8], "tile x"),
                    _integer(parts[9], "tile y"),
                )
                return _respond(
                    start_response,
                    200,
                    payload,
                    etag=etag,
                    cache_control="public, max-age=31536000, immutable",
                )
            raise ServiceError(404, "not_found", "endpoint not found")
        except ServiceError as error:
            return _respond(
                start_response, error.status, error.response(), cache_control="no-store"
            )


def _query(
    query_string: str,
    *,
    required: set[str],
    optional: set[str],
) -> dict[str, str]:
    parsed = parse_qs(query_string, keep_blank_values=True, strict_parsing=False)
    unknown = sorted(set(parsed) - required - optional)
    if unknown:
        raise ServiceError(
            400,
            "unknown_parameter",
            f"unknown query parameter: {unknown[0]}",
        )
    missing = sorted(required - set(parsed))
    if missing:
        raise ServiceError(
            400,
            "missing_parameter",
            f"missing query parameter: {missing[0]}",
        )
    duplicate = sorted(key for key, values in parsed.items() if len(values) != 1)
    if duplicate:
        raise ServiceError(
            400,
            "duplicate_parameter",
            f"query parameter must occur once: {duplicate[0]}",
        )
    return {key: values[0] for key, values in parsed.items()}


def _reject_query(query_string: str) -> None:
    if query_string:
        raise ServiceError(400, "unexpected_query", "this endpoint accepts no query parameters")


def _integer(value: str, name: str) -> int:
    if not value or any(character not in "0123456789" for character in value):
        raise ServiceError(400, f"invalid_{name.replace(' ', '_')}", f"{name} must be an integer")
    return int(value)


def _coordinate(value: str, name: str) -> float:
    try:
        coordinate = float(value)
    except ValueError as error:
        raise ServiceError(400, f"invalid_{name}", f"{name} must be numeric") from error
    if not math.isfinite(coordinate):
        raise ServiceError(400, f"invalid_{name}", f"{name} must be finite")
    return coordinate


def _month_mask(value: str) -> int:
    try:
        return hex_to_mask(value)
    except ValueError as error:
        raise ServiceError(400, "invalid_month_mask", str(error)) from error


def _respond(
    start_response: StartResponse,
    status: int,
    payload: dict[str, object],
    *,
    etag: str | None = None,
    cache_control: str = "no-store",
    extra_headers: list[tuple[str, str]] | None = None,
) -> Iterable[bytes]:
    body = (json.dumps(payload, sort_keys=True, allow_nan=False) + "\n").encode()
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", cache_control),
        ("X-Content-Type-Options", "nosniff"),
    ]
    if etag is not None:
        headers.append(("ETag", f'"{etag}"'))
    if extra_headers is not None:
        headers.extend(extra_headers)
    phrase = HTTPStatus(status).phrase
    start_response(f"{status} {phrase}", headers)
    return [body]


def create_app(service: DataService) -> WsgiApplication:
    return Application(service)
