# Data

Neither input is included in this repository.

## Discharge

The loaders read a GeoPackage with three layers:

| Layer | Columns used |
|---|---|
| `gauges` | `CODE`, `NAME_ENG`, `BASIN`, `q_m3s` |
| `basin_attributes` | `CODE`, `area_km2`, `h_mean`, `gl_fr`, and the attributes listed in the paper |
| `discharge_time_series` | `CODE`, `res`, `date`, `value` |

Only rows with `res = 'decade'` are read. Dates fall on the 5th, 15th and 25th
of each month and are mapped to dekad indices by `loaders.dekad_index`.

Source: Central Asia discharge compilation, [DATASET DOI].

## Forcing

ERA5-Land (Muñoz-Sabater et al., 2021, https://doi.org/10.5194/essd-13-4349-2021),
aggregated to daily means over each catchment polygon in Google Earth Engine
and exported as one CSV per year:

    CODE, date, temperature_2m, total_precipitation_sum, snow_depth_water_equivalent

`loaders.load_era5` aggregates the daily values to dekads. A dekad with any
missing day is left without forcing rather than interpolated.

## Catchments

    17288  16279  16290  16300  16936  17202  17211  16176  16202

Common window 1959-10 to 1990-12 (1125 dekads); warm-up to the end of 1969
(372 dekads); evaluation 1970-01 to 1990-12 (753 steps).
