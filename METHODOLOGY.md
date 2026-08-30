# Methodology and data dictionary

This application describes selected-year outdoor thermal conditions and
meteorological drought for the official Sicilia administrative extent. It is
not a forecast, personal heat-exposure estimate, crop-suitability score, water-
availability model, or health recommendation.

## Spatial scope

The scope starts from the Istat 2026 generalized Sicilia regional boundary.
It includes an ERA5 0.25° provider cell only when that cell’s center lies inside
the boundary, producing 44 cells. A cell represents its full reanalysis area
and can include sea. Small islands without an included provider-cell center are
not represented. The boundary is transformed from the Istat source; Istat data
are available under CC BY 4.0.

## Variables

| Public field | Meaning | Unit | Source treatment |
| --- | --- | --- | --- |
| `utci_daymax_median` | Typical daily peak Universal Thermal Climate Index | °C | Convert ERA5-HEAT daily-maximum UTCI from K to °C, then take each calendar month’s median |
| `spei_3` | Three-month Standardised Precipitation-Evapotranspiration Index | standard deviations | Retain the deterministic provider monthly SPEI-3 value; do not recompute its three-month window |
| `spei_3_quality_pass` | Provider SPEI normality test | boolean | Publish SPEI only where provider significance equals 1 |
| `sicily_scope_mask` | Membership in the published Sicilia grid | boolean | Cell center lies inside the Istat regional polygon |

SPEI-3 uses the provider’s 1991–2020 reference period. Negative SPEI values
are drier than the reference climate; this application never calls the
reference-period median “drought risk.”

## Selection and aggregation

All selected calendar months receive equal weight. The displayed value is the
median of their published monthly layers; an even selection uses the mean of
the two central values. At least `ceil(selected months × 0.75)` valid months
are required. Missing, out-of-scope, and provider-quality-failed values stay no
data and are never converted to zero. All 4,095 non-empty month masks are valid.

## Fixed classifications

SPEI-3 classes are no drought (`> -1`), moderate drought (`> -1.5` and
`<= -1`), and severe or extreme drought (`<= -1.5`). UTCI classes are cold
stress (`< 9 °C`), no thermal stress (`>= 9 °C` and `<= 26 °C`), and heat
stress (`> 26 °C`). Break ownership is tested at every boundary. The fixed 3×3
legend names every combined state and never relies on color alone.

## Provenance, licensing, and limits

ERA5-Drought is ECMWF/Copernicus Climate Change Service v1.0, DOI
`10.24381/9bea5e16`, licensed CC BY 4.0. ERA5-HEAT is v1.1, DOI
`10.24381/cds.553b7518`, under the Copernicus Products licence. The application
contains modified Copernicus Climate Change Service information 2026. Neither
the European Commission nor ECMWF is responsible for any use of the
information. Dataset pages, licences, versions, retrieval dates, and the Istat
boundary source are linked in the interface.

UTCI does not resolve shade, buildings, activity, clothing, local wind, urban
heat islands, or individual physiology. SPEI does not describe soil moisture,
reservoirs, irrigation, governance, or household water access. Consult the
checked manifests and `pipeline/reports/sicily-release-v1.json` for the exact
release contract and checksums.
