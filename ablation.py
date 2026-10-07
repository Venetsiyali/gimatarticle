"""
Lag-window ablation.

Compares four ways of building the lag features of the boosted member under
the same streaming protocol. Under scattered loss, availability of the member
follows the lag window (p ** N_LAGS) rather than the amount of data retained;
the constructions below differ in how they treat an incomplete window. All
of them are causal:

    A0  baseline      six consecutive lags required; a row with any gap is
                      dropped, and no live forecast is issued
    A1  short window  three lags instead of six
    A2  nan-aware     six lags, missing values passed through as NaN, which
                      the boosted member handles natively through its default
                      split direction; rows are never dropped for gaps and a
                      live row is always available
    A3  indicators    A2 plus one binary column per lag marking whether it was
                      observed, so the model can separate "low flow" from
                      "no reading"

None of them reads a value dated later than the anchor, so the conformance
guarantee is unchanged; tests/test_conformance.py re-checks that mechanically.

    python ablation.py --gpkg PATH --era5 DIR --out abl/ \
                       --variants A0 A2 --scenarios S-base S-miss-10 S-miss-20
"""

from __future__ import annotations

import argparse
import math
import os

import numpy as np

import ensemble as E
from experiment import WARMUP_END, prepare, score, write_csv
from loaders import BASINS
from metrics import holm
from pstream import ClimAR1, DEKADS_PER_YEAR, RunConfig, doy, run_stream
from scenarios import apply_scenario

LEADS = (1, 2, 3)
VARIANTS = ("A0", "A1", "A2", "A3")
SHORT_LAGS = 3

FIELDS = ["basin", "variant", "policy", "scenario", "lead", "n", "nse", "nse_lo",
          "nse_hi", "rmse", "ss_clim", "dm", "dm_p", "dm_p_holm", "cw", "cw_p",
          "n_updates", "fit_ms_total", "fit_ms_mean", "wall_s", "buffer_end",
          "n_quarantined", "n_degraded"]


# --------------------------------------------------------------------------
# feature builders — each returns (X, y) for training and a live row
# --------------------------------------------------------------------------

def _season(target_s: int) -> list[float]:
    d = doy(target_s)
    return [math.sin(2 * math.pi * d / DEKADS_PER_YEAR),
            math.cos(2 * math.pi * d / DEKADS_PER_YEAR)]


def _lags(lookup: dict, s: int, n: int, nan_ok: bool):
    out = []
    for k in range(n):
        v = lookup.get(s - k)
        if v is None:
            if not nan_ok:
                return None
            out.append(float("nan"))
        else:
            out.append(float(v))
    return out


def make_builders(variant: str):
    """Returns (design, live_row) closures matching the variant."""
    n_lags = SHORT_LAGS if variant == "A1" else E.N_LAGS
    nan_ok = variant in ("A2", "A3")
    indicators = variant == "A3"

    def feats(lookup, s, target_s, exog):
        lags = _lags(lookup, s, n_lags, nan_ok)
        if lags is None:
            return None
        row = list(lags) + _season(target_s)
        if indicators:
            row += [0.0 if (v != v) else 1.0 for v in lags]
        if exog is not None:
            e = exog.get(s)
            if e is None:
                if not nan_ok:
                    return None
                row += [float("nan")] * len(next(iter(exog.values()), ()))
            else:
                row += list(e)
        return row

    def design(series, lead, exog=None):
        lookup = dict(series)
        X, y = [], []
        for s, _v in series:
            tgt = lookup.get(s + lead)
            if tgt is None:
                continue
            row = feats(lookup, s, s + lead, exog)
            if row is None:
                continue
            X.append(row); y.append(tgt)
        if not X:
            return None, None
        return np.asarray(X, float), np.asarray(y, float)

    def live_row(series, lead, exog=None):
        if not series:
            return None
        lookup = dict(series)
        s = series[-1][0]
        row = feats(lookup, s, s + lead, exog)
        if row is None:
            return None
        return np.asarray([row], float)

    return design, live_row


class _Patch:
    """Swaps the feature builders inside the ensemble module for one run."""

    def __init__(self, variant: str):
        self.variant = variant

    def __enter__(self):
        self._d, self._l = E._design, E._live_row
        if self.variant != "A0":
            E._design, E._live_row = make_builders(self.variant)
        return self

    def __exit__(self, *exc):
        E._design, E._live_row = self._d, self._l
        return False


# --------------------------------------------------------------------------

def one_run(entry, basin, variant, scenario, seed=0):
    packets = (entry["packets"] if scenario == "S-base"
               else apply_scenario(scenario, entry["packets"],
                                   seed=seed, protect=WARMUP_END))
    exog = entry["exog"]
    ref = run_stream(packets, RunConfig(warmup_end=WARMUP_END,
                                        eval_end=entry["span"], update="C1",
                                        basin_id=basin, model_factory=ClimAR1))
    import time
    with _Patch(variant):
        t0 = time.perf_counter()
        ens = run_stream(packets, RunConfig(
            warmup_end=WARMUP_END, eval_end=entry["span"], update="C1",
            basin_id=basin,
            model_factory=lambda: E.GimatEnsemble(leads=LEADS, exog=exog)))
        wall = time.perf_counter() - t0
    return ref, ens, wall


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--era5", required=True)
    ap.add_argument("--out", default="abl")
    ap.add_argument("--basins", nargs="*", default=list(BASINS))
    ap.add_argument("--variants", nargs="*", default=list(VARIANTS))
    ap.add_argument("--scenarios", nargs="*",
                    default=["S-base", "S-miss-05", "S-miss-10", "S-miss-20",
                             "S-late-3"])
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    data = prepare(args.gpkg, args.era5, args.basins)
    rows = []
    path = os.path.join(args.out, "ablation.csv")

    for basin in args.basins:
        entry = data.get(basin)
        if entry is None:
            continue
        for variant in args.variants:
            for scenario in args.scenarios:
                ref, ens, wall = one_run(entry, basin, variant, scenario,
                                         args.seed)
                got = score(basin, "C1", entry, ref, ens, wall, scenario)
                for r in got:
                    r["variant"] = variant
                rows.extend(got)
                r1 = next((r for r in got if r["lead"] == 1), None)
                if r1:
                    print(f"  {basin} {variant} {scenario:11} "
                          f"lead=1 NSE={r1['nse']:.3f} SS={r1['ss_clim']:+.3f}")
                write_csv(path, rows, FIELDS)

    groups = {}
    for r in rows:
        groups.setdefault((r["variant"], r["scenario"], r["lead"]), []).append(r)
    for g in groups.values():
        for r, a in zip(g, holm([r["dm_p"] if r["dm_p"] is not None
                                 else float("nan") for r in g])):
            r["dm_p_holm"] = None if a != a else round(a, 6)
    write_csv(path, rows, FIELDS)

    print("\nmedian SS by variant and scenario (lead 1):")
    print(f"  {'scenario':12}" + "".join(f"{v:>9}" for v in args.variants))
    for scenario in args.scenarios:
        line = f"  {scenario:12}"
        for variant in args.variants:
            g = groups.get((variant, scenario, 1))
            if not g:
                line += f"{'-':>9}"
                continue
            ss = sorted(r["ss_clim"] for r in g)
            line += f"{ss[len(ss) // 2]:>+9.3f}"
        print(line)
    print(f"\nwritten to {path}")


if __name__ == "__main__":
    main()
