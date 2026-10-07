# GIMAT v1.0

GIMAT is a streaming framework for ten-day (dekadal) streamflow forecasting and
discharge record screening in data-scarce catchments. It implements P-stream
v1.0, an evaluation protocol under which every number the system emits at step
*t* is computed only from the information it held at *t*:

    I(t) = {(s, v) : s ≤ t and a(s) ≤ t}

where *s* is the date a value describes and *a(s)* the date it arrived.
Compliance is not asserted but tested: the conformance suite replaces every
future value with an absurd number and requires the forecasts issued at all
earlier steps to be bitwise identical.

This repository contains the code and the replay harness used in

> Nasridinov, R.: GIMAT v1.0: an operational streaming framework for
> leakage-free ten-day streamflow forecasting and discharge record screening
> in data-scarce Central Asian catchments, Geosci. Model Dev., submitted, 2026.

## Contents

| Path | Purpose |
|---|---|
| `pstream.py` | the protocol: information set, step loop, update policies C0–C4 |
| `ensemble.py` | climatology·AR(1) benchmark, boosted member, causal weights |
| `scenarios.py` | the fourteen delivery-failure scenarios |
| `loaders.py` | discharge and ERA5-Land readers, dekad calendar |
| `metrics.py` | NSE, skill score, Diebold–Mariano, Clark–West, Holm, block bootstrap |
| `experiment.py` | update policies and failure grid |
| `diagnose.py` | availability of the boosted member against p^N_LAGS |
| `ablation.py` | the four lag-feature constructions A0–A3 |
| `signatures.py` | catchment signatures against skill |
| `report_policy.py` | the policy table of the paper |
| `reproduce.py` | runs every stage of the paper in order |
| `tests/` | conformance tests T1–T4 |
| `figures/` | scripts for every figure in the paper |

## Installation

Python 3.11 or later.

    git clone https://github.com/Venetsiyali/gimat.git
    cd gimat
    pip install -r requirements.txt

No GPU is used. The full experiment runs on two CPU cores.

## Data

The data are not redistributed here. See `data/README.md` for the sources and
the layout the loaders expect. In short, two inputs are needed:

- the Central Asia discharge GeoPackage, with dekadal series in the
  `discharge_time_series` layer;
- ERA5-Land daily catchment means, one CSV per year, with columns `CODE`,
  `date`, `temperature_2m`, `total_precipitation_sum`,
  `snow_depth_water_equivalent`.

## Running

Check that the protocol holds before anything else:

    python -m pytest tests

All thirteen cases should pass in under a minute.

Reproduce every result in the paper:

    python reproduce.py --gpkg PATH/CA-discharge.gpkg --era5 PATH/era5/ --out results/

The script runs the conformance tests, the catchment audit, the five update
policies, the failure grid, the availability diagnostics, the lag-window
ablation and the catchment signatures, and writes one CSV per stage. It stops
if the conformance tests fail. A completed stage is skipped on the next run,
so an interrupted run resumes where it stopped; `--force` recomputes. Add
`--quick` to check the pipeline on two catchments in a few minutes, or
`--only ablation signatures` to run selected stages.

Individual stages can also be run directly, for example:

    python experiment.py --gpkg PATH --era5 DIR --out results/ --policies C1 --scenarios all
    python ablation.py   --gpkg PATH --era5 DIR --out abl/ --variants A0 A2

## Configuration

Model hyperparameters are frozen in `ensemble.py` and are not tuned on the
evaluation window. The evaluation window and warm-up are set in `loaders.py`
(`COMMON_START`, `COMMON_END`) and `experiment.py` (`WARMUP_END`). Appendix B
of the paper lists every value.

## Figures

`figures/matlab/` produces Figs. 3–7. Each script carries its input numbers
inline, so it runs without the result files and needs base MATLAB only.
`figures/diagrams/` produces Figs. 1 and 2 as SVG from plain Python.

## Citing

Please cite the paper above and the archived release of this code; see
`CITATION.cff`.

## Licence

MIT. See `LICENSE`.
