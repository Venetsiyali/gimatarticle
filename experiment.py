"""
Experiment driver for GIMAT v1.0 / P-stream v1.0.

Stage 1: nine catchments x five update policies under S-base, giving the
update-policy table and the skill-versus-cost Pareto front.
Stage 2: the chosen policy (C1, the Pareto elbow) across the failure grid.

Everything is written to CSV as it is produced, so a run can be interrupted
and resumed without losing completed catchments.

Usage
    python experiment.py --gpkg PATH --era5 DIR --out results/
    python experiment.py ... --basins 17288 16279 --policies C2 C4
    python experiment.py ... --policies C1 --scenarios all
"""

from __future__ import annotations

import argparse
import csv
import os
import time
from typing import Sequence

from loaders import (BASINS, WINDOW_START, load_discharge, load_era5,
                     rebase, to_packets)
from metrics import (benjamini_hochberg, block_bootstrap_ci, clark_west,
                     align, dm_test, holm, nse, rmse, sign_test, skill_score)
from pstream import ClimAR1, RunConfig, run_stream
from ensemble import GimatEnsemble
from scenarios import GRID, apply_scenario, truth_of

WARMUP_END = 372          # first dekad after the 1969 outage in 17211
POLICIES = ("C0", "C1", "C2", "C3", "C4")
LEADS = (1, 2, 3)

SCENARIO_POLICY = "C1"     # Pareto elbow from stage 1

PER_RUN_FIELDS = [
    "basin", "policy", "scenario", "lead", "n",
    "nse", "nse_lo", "nse_hi", "rmse",
    "ss_clim", "dm", "dm_p", "dm_p_holm", "cw", "cw_p",
    "n_updates", "fit_ms_total", "fit_ms_mean", "wall_s",
    "buffer_end", "n_quarantined", "n_degraded",
]


# --------------------------------------------------------------------------

def prepare(gpkg: str, era5_dir: str, basins: Sequence[str]):
    """Load once, reuse across policies."""
    q = load_discharge(gpkg, basins)
    f = load_era5(era5_dir, basins)
    data = {}
    for code in basins:
        series = rebase(q[code])
        if not series:
            continue
        exog = {s - WINDOW_START: v for s, v in f.get(code, {}).items()}
        packets = to_packets(series)
        data[code] = {
            "series": series,
            "exog": exog,
            "packets": packets,
            "truth": truth_of(packets),
            "span": max(s for s, _ in series),
        }
    return data


def one_run(entry: dict, policy: str, basin: str,
            scenario: str = "S-base", seed: int = 0):
    """
    Reference and ensemble under one update policy and one failure scenario.

    The perturbation is applied to the packet stream only. The reference runs
    on the same perturbed stream, so the comparison isolates the effect of the
    failure on the ensemble rather than on the benchmark.
    """
    cfg_ref = RunConfig(warmup_end=WARMUP_END, eval_end=entry["span"],
                        update=policy, basin_id=basin,
                        model_factory=ClimAR1)
    exog = entry["exog"]
    cfg_ens = RunConfig(warmup_end=WARMUP_END, eval_end=entry["span"],
                        update=policy, basin_id=basin,
                        model_factory=lambda: GimatEnsemble(leads=LEADS,
                                                            exog=exog))
    packets = entry["packets"] if scenario == "S-base" else apply_scenario(
        scenario, entry["packets"], seed=seed, protect=WARMUP_END)
    ref_rows = run_stream(packets, cfg_ref)
    t0 = time.perf_counter()
    ens_rows = run_stream(packets, cfg_ens)
    wall = time.perf_counter() - t0
    return ref_rows, ens_rows, wall


def score(basin: str, policy: str, entry: dict, ref_rows, ens_rows,
          wall: float, scenario: str = "S-base") -> list[dict]:
    truth = entry["truth"]
    fits = [r["fit_ms"] for r in ens_rows if r["update_fired"]]
    rows = []
    for lead in LEADS:
        _t, o, s = align(ens_rows, truth, lead)
        _t2, o2, r2 = align(ref_rows, truth, lead)
        n = min(len(o), len(o2))
        if n < 48:
            continue
        o, s, r2 = o[-n:], s[-n:], r2[-n:]
        pt, lo, hi = block_bootstrap_ci(o, s, stat="nse", seed=lead)
        dm, dm_p = dm_test(o - s, o - r2, h=lead)
        cw, cw_p = clark_west(o, r2, s, h=lead)
        rows.append({
            "basin": basin, "policy": policy, "scenario": scenario,
            "lead": lead, "n": n,
            "nse": round(nse(o, s), 6),
            "nse_lo": round(lo, 6), "nse_hi": round(hi, 6),
            "rmse": round(rmse(o, s), 6),
            "ss_clim": round(skill_score(o, s, r2), 6),
            "dm": None if dm != dm else round(dm, 4),
            "dm_p": None if dm_p != dm_p else round(dm_p, 6),
            "dm_p_holm": None,
            "cw": None if cw != cw else round(cw, 4),
            "cw_p": None if cw_p != cw_p else round(cw_p, 6),
            "n_updates": len(fits),
            "fit_ms_total": round(sum(fits), 2),
            "fit_ms_mean": round(sum(fits) / len(fits), 3) if fits else 0.0,
            "wall_s": round(wall, 2),
            "buffer_end": ens_rows[-1]["buffer_size"] if ens_rows else 0,
            "n_quarantined": sum(r["n_quarantined"] for r in ens_rows),
            "n_degraded": sum(1 for r in ens_rows if r["degraded"]),
        })
    return rows


def adjust_within_policy(rows: list[dict]) -> None:
    """Holm across catchments, applied separately per policy and lead."""
    groups: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["policy"], r.get("scenario", "S-base"),
                           r["lead"]), []).append(r)
    for g in groups.values():
        adj = holm([r["dm_p"] if r["dm_p"] is not None else float("nan")
                    for r in g])
        for r, a in zip(g, adj):
            r["dm_p_holm"] = None if a != a else round(a, 6)


def pooled(rows: list[dict]) -> list[dict]:
    """Sign test over catchments, per policy and lead."""
    out = []
    groups: dict[tuple[str, str, int], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["policy"], r.get("scenario", "S-base"),
                           r["lead"]), []).append(r)
    for (policy, scenario, lead), g in sorted(groups.items()):
        pos, n, p = sign_test([r["ss_clim"] for r in g])
        ss = sorted(r["ss_clim"] for r in g)
        med = ss[len(ss) // 2] if ss else float("nan")
        out.append({
            "policy": policy, "scenario": scenario, "lead": lead,
            "n_basins": n,
            "n_positive": pos, "sign_p": None if p != p else round(p, 6),
            "median_ss": round(med, 6),
            "mean_fit_ms": round(sum(r["fit_ms_mean"] for r in g) / len(g), 3),
            "mean_updates": round(sum(r["n_updates"] for r in g) / len(g), 1),
        })
    return out


# --------------------------------------------------------------------------

def write_csv(path: str, rows: Sequence[dict], fields: Sequence[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--era5", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--basins", nargs="*", default=list(BASINS))
    ap.add_argument("--policies", nargs="*", default=list(POLICIES))
    ap.add_argument("--scenarios", nargs="*", default=["S-base"],
                    help="names from scenarios.GRID, or 'all'")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    scenarios = ([name for name, _f, _k in GRID]
                 if args.scenarios == ["all"] else args.scenarios)

    data = prepare(args.gpkg, args.era5, args.basins)
    if not args.quiet:
        print(f"loaded {len(data)} catchments, "
              f"{len(args.policies)} policies, {len(scenarios)} scenarios")

    all_rows: list[dict] = []
    per_run_path = os.path.join(args.out, "per_run.csv")

    for basin in args.basins:
        entry = data.get(basin)
        if entry is None:
            continue
        for policy in args.policies:
            for scenario in scenarios:
                ref_rows, ens_rows, wall = one_run(entry, policy, basin,
                                                   scenario, args.seed)
                rows = score(basin, policy, entry, ref_rows, ens_rows,
                             wall, scenario)
                all_rows.extend(rows)
                if not args.quiet:
                    for r in rows:
                        print(f"  {basin} {policy} {scenario:11} "
                              f"lead={r['lead']} NSE={r['nse']:.3f} "
                              f"SS={r['ss_clim']:+.3f} "
                              f"deg={r['n_degraded']:>3} "
                              f"qtn={r['n_quarantined']:>3} "
                              f"{r['wall_s']:.1f}s")
                write_csv(per_run_path, all_rows, PER_RUN_FIELDS)

    adjust_within_policy(all_rows)
    write_csv(per_run_path, all_rows, PER_RUN_FIELDS)

    summary = pooled(all_rows)
    write_csv(os.path.join(args.out, "pooled.csv"), summary,
              ["policy", "scenario", "lead", "n_basins", "n_positive",
               "sign_p", "median_ss", "mean_fit_ms", "mean_updates"])

    if not args.quiet:
        print("\npooled across catchments:")
        for r in summary:
            print(f"  {r['policy']} {r['scenario']:11} lead={r['lead']} "
                  f"median SS={r['median_ss']:+.3f} "
                  f"{r['n_positive']}/{r['n_basins']} positive "
                  f"sign p={r['sign_p']} "
                  f"mean fit={r['mean_fit_ms']}ms x{r['mean_updates']}")
        print(f"\nwritten to {args.out}/")


if __name__ == "__main__":
    main()
