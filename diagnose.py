"""
Availability diagnostics for the boosted member.

The boosted member needs N_LAGS consecutive dekads to issue a forecast, so
under independent losses its availability is expected to fall roughly as
p ** N_LAGS, and under a single contiguous outage only in proportion to the
outage length. This module instruments a run and reports:

    availability  share of evaluation steps at which the member could produce
                  a forecast at all
    fallback      steps where the ensemble silently reduced to climatology
    weight        mean causal weight the member actually carried
    predicted     p**N_LAGS, the availability the lag window alone implies

    python diagnose.py --gpkg PATH --era5 DIR --out diag/ \
                       --scenarios S-base S-miss-10 S-miss-20 S-gap-12
"""

from __future__ import annotations

import argparse
import csv
import os
from typing import Sequence

from ensemble import N_LAGS, GimatEnsemble, _live_row
from experiment import WARMUP_END, prepare, write_csv
from loaders import BASINS
from pstream import RunConfig, run_stream
from scenarios import apply_scenario

LEADS = (1, 2, 3)
FIELDS = ["basin", "scenario", "n_steps", "n_obs_kept", "retention",
          "xgb_available", "availability", "predicted_availability",
          "fallback_steps", "mean_w_xgb", "mean_w_base", "n_quarantined"]


class Probe(GimatEnsemble):
    """Counts, per step, whether the boosted member was able to speak."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.steps = 0
        self.available = 0
        self.fallback = 0
        self.w_xgb_sum = 0.0
        self.w_base_sum = 0.0

    def predict(self, series, target_s: int) -> float:
        lead = target_s - series[-1][0]
        if lead == LEADS[0]:
            self.steps += 1
            row = _live_row(series, lead, self.xgbm.exog)
            ok = (self.xgbm._models.get(lead) is not None and row is not None)
            self.available += int(ok)
            if not ok:
                self.fallback += 1
        out = super().predict(series, target_s)
        if lead == LEADS[0]:
            wb, wx = self.last_weights.get(lead, (1.0, 0.0))
            self.w_base_sum += wb
            self.w_xgb_sum += wx
        return out


def diagnose(entry: dict, basin: str, scenario: str, seed: int = 0) -> dict:
    packets = (entry["packets"] if scenario == "S-base"
               else apply_scenario(scenario, entry["packets"],
                                   seed=seed, protect=WARMUP_END))
    probe_holder = {}

    def factory():
        p = Probe(leads=LEADS, exog=entry["exog"])
        probe_holder["p"] = p
        return p

    rows = run_stream(packets, RunConfig(warmup_end=WARMUP_END,
                                         eval_end=entry["span"],
                                         update="C1", basin_id=basin,
                                         model_factory=factory))
    p = probe_holder["p"]
    kept = len(packets)
    total = len(entry["packets"])
    retention = kept / total if total else 0.0
    steps = max(p.steps, 1)
    return {
        "basin": basin,
        "scenario": scenario,
        "n_steps": p.steps,
        "n_obs_kept": kept,
        "retention": round(retention, 4),
        "xgb_available": p.available,
        "availability": round(p.available / steps, 4),
        "predicted_availability": round(retention ** N_LAGS, 4),
        "fallback_steps": p.fallback,
        "mean_w_xgb": round(p.w_xgb_sum / steps, 4),
        "mean_w_base": round(p.w_base_sum / steps, 4),
        "n_quarantined": sum(r["n_quarantined"] for r in rows),
    }


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--era5", required=True)
    ap.add_argument("--out", default="diag")
    ap.add_argument("--basins", nargs="*", default=list(BASINS))
    ap.add_argument("--scenarios", nargs="*",
                    default=["S-base", "S-miss-05", "S-miss-10", "S-miss-20",
                             "S-gap-03", "S-gap-12", "S-late-3"])
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    data = prepare(args.gpkg, args.era5, args.basins)
    out = []
    for basin in args.basins:
        entry = data.get(basin)
        if entry is None:
            continue
        for scenario in args.scenarios:
            rec = diagnose(entry, basin, scenario, args.seed)
            out.append(rec)
            print(f"  {basin} {scenario:11} retention={rec['retention']:.3f} "
                  f"avail={rec['availability']:.3f} "
                  f"(lag-window predicts {rec['predicted_availability']:.3f}) "
                  f"fallback={rec['fallback_steps']:>3} "
                  f"w_xgb={rec['mean_w_xgb']:.3f}")
        write_csv(os.path.join(args.out, "diagnostics.csv"), out, FIELDS)

    print("\nmedian across catchments:")
    by_scen = {}
    for r in out:
        by_scen.setdefault(r["scenario"], []).append(r)
    for scen in args.scenarios:
        g = by_scen.get(scen)
        if not g:
            continue
        def med(key):
            v = sorted(x[key] for x in g)
            return v[len(v) // 2]
        print(f"  {scen:11} retention={med('retention'):.3f} "
              f"avail={med('availability'):.3f} "
              f"predicted={med('predicted_availability'):.3f} "
              f"w_xgb={med('mean_w_xgb'):.3f}")
    print(f"\nwritten to {args.out}/")


if __name__ == "__main__":
    main()
