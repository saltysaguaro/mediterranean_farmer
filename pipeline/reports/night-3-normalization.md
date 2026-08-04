# Night 3 representative normalization report

Checked: 2026-07-27 America/Phoenix

## Outcome

The exact 24-artifact Night 2 official sample was re-audited before any climate
array was read. All eight region/month triples then normalized successfully into
four local monthly NetCDF products under ignored `data/published/`.

This is a bounded official-data development sample, not a global backfill. No
synthetic fixture contributed values or provenance to the report.

## Locked source adapters

- ERA5-HEAT product 1.1 must contain `utci_daily_max` with
  `cell_methods = "time: maximum"`. Its observed unit attribute is absent, so
  the adapter applies only the catalogue-bound v1.1 Kelvin contract. A present
  unexpected unit fails. All requested calendar days must be present exactly
  once before the monthly per-cell median is calculated and converted to °C.
- ERA5-Drought product 1.0 must contain deterministic provider `SPEI3`. Its
  observed unit attribute is absent, so the adapter applies only the
  product-bound dimensionless contract. The provider value and selected-year
  month are retained; the accumulation window is never recomputed.
- The separate reference-period `significance` layer must have unit `1` and
  contain only 0, 1, or nodata. The source SPEI value remains available in
  `spei_3_source`; published `spei_3` is no data unless significance is 1.

## Canonical representation

- Grid: `era5_latlon_0_25`
- CRS: EPSG:4326
- Latitude: north to south
- Longitude: ascending in `[-180, 180)`
- Calendar/time: Gregorian calendar month start
- Variables: monthly UTCI, valid-day count, source SPEI-3, provider quality
  flag, and quality-masked published SPEI-3
- Writes: atomic; an identical existing dataset is left untouched

The four two-month, 3 × 3 regional products total 120,656 bytes. Their
individual paths, sizes, SHA-256 checksums, and eight center-cell golden samples
are in
[`night-3-normalization.json`](./night-3-normalization.json).

The independent test path opens the source ZIPs separately, calculates UTCI
medians with Python's reference median, reads provider SPEI and quality values
directly, and compares them with the normalized center cells at 1e-5 °C and
1e-6 SPEI tolerance.

## Southern-edge evidence

At latitude -59.75°, longitude 0.25°, UTCI remains valid in both January and
July. Provider SPEI-3 is nodata and `significance` is 0 in both months, so the
published drought value remains no data. No missing or low-quality value becomes
zero.

## Selected-month validity

The shared array helper implements the locked
`ceil(selected_month_count × 0.75)` valid-month rule with minimum one. Tests
cover one, two, odd, even, and all-year counts; the below-threshold case remains
no data, while a real numeric zero is preserved.

## Dependency blocker

The declared `zarr>=2.18,<3` and `numcodecs>=0.15,<1` dependencies were absent.
The sandboxed installation attempt could not resolve the package index, and the
required network escalation was rejected as an unreviewed third-party install.
No workaround or external asset was used. The bounded local publication
therefore uses compressed NetCDF through the already installed xarray,
h5netcdf, h5py, and NumPy stack. Production Zarr publication remains pending;
it does not block the Night 3 representative normalization acceptance gate.
