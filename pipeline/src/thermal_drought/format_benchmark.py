"""Benchmark Sicily-shaped structural serving formats without climate observations."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from thermal_drought.scope import load_scope


def _xarray() -> Any:
    import xarray as xr

    return xr


def run_benchmark(scope_path: Path = Path("config/scope.json")) -> dict[str, object]:
    """Measure a deterministic, Sicily-shaped, conspicuously structural fixture."""

    xr = _xarray()
    scope = load_scope(scope_path)
    west, south, east, north = scope.acquisition_bbox
    latitudes = np.arange(north, south - 0.001, -scope.resolution_degrees)
    longitudes = np.arange(west, east + 0.001, scope.resolution_degrees)
    mask = np.asarray(
        [
            [scope.includes(float(longitude), float(latitude)) for longitude in longitudes]
            for latitude in latitudes
        ],
        dtype=np.uint8,
    )
    times = np.asarray([np.datetime64(f"2000-{month:02d}-01", "ns") for month in range(1, 13)])
    month_index = np.arange(12, dtype=np.float32)[:, None, None]
    row_index = np.arange(len(latitudes), dtype=np.float32)[None, :, None]
    column_index = np.arange(len(longitudes), dtype=np.float32)[None, None, :]
    structural_utci = 5 + month_index + row_index / 10 + column_index / 100
    structural_spei = -2 + month_index / 6 + row_index / 100 + column_index / 1000
    structural_utci = np.where(mask[None, :, :] == 1, structural_utci, np.nan)
    structural_spei = np.where(mask[None, :, :] == 1, structural_spei, np.nan)
    dataset = xr.Dataset(
        data_vars={
            "utci_daymax_median": (
                ("time", "latitude", "longitude"),
                structural_utci.astype(np.float32),
            ),
            "spei_3": (
                ("time", "latitude", "longitude"),
                structural_spei.astype(np.float32),
            ),
            "spei_3_quality": (
                ("time", "latitude", "longitude"),
                np.broadcast_to(
                    np.where(mask[None, :, :] == 1, 1, 255),
                    structural_utci.shape,
                ).astype(np.uint8),
            ),
            "sicily_scope_mask": (("latitude", "longitude"), mask),
        },
        coords={"time": times, "latitude": latitudes, "longitude": longitudes},
        attrs={
            "fixture": "STRUCTURAL FORMAT BENCHMARK — NOT CLIMATE OBSERVATIONS",
            "scope_id": scope.scope_id,
        },
    )
    sparse = {
        "fixture": True,
        "official_evidence": False,
        "scope_id": scope.scope_id,
        "cells": [
            {
                "longitude": float(longitude),
                "latitude": float(latitude),
                "utci": [float(value) for value in structural_utci[:, row, column]],
                "spei": [float(value) for value in structural_spei[:, row, column]],
            }
            for row, latitude in enumerate(latitudes)
            for column, longitude in enumerate(longitudes)
            if mask[row, column] == 1
        ],
    }
    sparse_bytes = json.dumps(sparse, sort_keys=True, separators=(",", ":")).encode()
    with tempfile.TemporaryDirectory(prefix="sicily-structural-format-") as directory:
        path = Path(directory) / "STRUCTURAL_NOT_CLIMATE.nc"
        encoding = {
            "utci_daymax_median": {"zlib": True, "complevel": 6},
            "spei_3": {"zlib": True, "complevel": 6},
            "spei_3_quality": {"zlib": True, "complevel": 6},
            "sicily_scope_mask": {"zlib": True, "complevel": 6},
        }
        write_started = time.perf_counter()
        dataset.to_netcdf(path, engine="h5netcdf", encoding=encoding)
        write_ms = (time.perf_counter() - write_started) * 1000
        point_started = time.perf_counter()
        with xr.open_dataset(path, engine="h5netcdf") as reopened:
            point = float(
                reopened["utci_daymax_median"].isel(time=0).sel(latitude=37.5, longitude=13.75)
            )
            parity = reopened.load().identical(dataset)
        point_read_ms = (time.perf_counter() - point_started) * 1000
        netcdf_bytes = path.stat().st_size

    if not parity or not math.isfinite(point):
        raise RuntimeError("structural NetCDF did not preserve exact data and nodata semantics")
    return {
        "schema_version": "1.0",
        "status": "complete",
        "fixture": True,
        "official_evidence": False,
        "fixture_label": "STRUCTURAL FORMAT BENCHMARK — NOT CLIMATE OBSERVATIONS",
        "scope_id": scope.scope_id,
        "shape": [12, len(latitudes), len(longitudes)],
        "included_scope_cells": int(mask.sum()),
        "compressed_netcdf_bytes": netcdf_bytes,
        "sparse_json_bytes": len(sparse_bytes),
        "sparse_json_gzip_bytes": len(gzip.compress(sparse_bytes, compresslevel=9, mtime=0)),
        "netcdf_write_ms": round(write_ms, 3),
        "netcdf_point_open_read_close_ms": round(point_read_ms, 3),
        "exact_round_trip_parity": parity,
        "decision": (
            "Use one compressed NetCDF product per Sicily year and lossless sparse JSON "
            "responses; retain Zarr/COG only as a future scale trigger."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=Path("config/scope.json"))
    args = parser.parse_args(argv)
    print(json.dumps(run_benchmark(args.scope), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
