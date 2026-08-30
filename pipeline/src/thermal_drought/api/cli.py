"""Run or verify the bounded local aggregation service."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from thermal_drought.api.app import create_app
from thermal_drought.api.core import DataService
from thermal_drought.api.runtime import RuntimeSettings, create_production_app
from thermal_drought.release_bundle import materialize_environment_release


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Serve independent bounded requests concurrently."""

    daemon_threads = True


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=repository_root())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the registry and release products, print status, and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        print("Service startup failed: port must be between 1 and 65535")
        return 2
    try:
        active_root = materialize_environment_release(args.repository_root.resolve())
        service = DataService.from_repository(active_root)
        runtime_settings = RuntimeSettings.load(
            active_root / "config" / "app.json",
            active_root,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Service startup failed: {error}")
        return 2
    if args.check:
        print(
            json.dumps(
                {
                    "health": service.health(),
                    "availability": service.availability(),
                    "runtime": runtime_settings.public_metadata(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    application = create_production_app(
        create_app(service),
        runtime_settings,
        readiness=lambda: bool(service.release.products),
    )
    with make_server(
        args.host,
        args.port,
        application,
        server_class=ThreadingWSGIServer,
    ) as server:
        print(f"Serving on http://{args.host}:{args.port}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
