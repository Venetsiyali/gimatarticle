"""
Policy table for the paper: significance after Holm, median skill, cost.

Reads the per_run.csv files produced by experiment.py (one or more output
directories) and prints the table in the form it will appear in the paper.

    python report_policy.py results/ results_c34/
"""
from __future__ import annotations

import csv
import os
import sys

ORDER = ["C0", "C1", "C2", "C3", "C4"]


def load(dirs):
    rows = []
    for d in dirs:
        p = os.path.join(d, "per_run.csv") if os.path.isdir(d) else d
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                rows.append(r)
    return rows


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main(dirs):
    rows = load(dirs)
    groups = {}
    for r in rows:
        groups.setdefault((r["policy"], int(r["lead"])), []).append(r)

    print(f"{'policy':6} {'lead':>4} {'n':>3} {'med SS':>8} {'raw<.05':>8} "
          f"{'Holm<.05':>9} {'fits':>5} {'ms/fit':>7} {'total s':>8}")
    print("-" * 68)
    for policy in ORDER:
        for lead in (1, 2, 3):
            g = groups.get((policy, lead))
            if not g:
                continue
            ss = sorted(num(r["ss_clim"]) for r in g)
            med = ss[len(ss) // 2]
            raw = sum(1 for r in g if num(r["dm_p"]) < 0.05)
            adj = sum(1 for r in g if num(r["dm_p_holm"]) < 0.05)
            fits = num(g[0]["n_updates"])
            msfit = sum(num(r["fit_ms_mean"]) for r in g) / len(g)
            total = sum(num(r["fit_ms_total"]) for r in g) / len(g) / 1000.0
            print(f"{policy:6} {lead:>4} {len(g):>3} {med:>+8.3f} "
                  f"{raw:>8} {adj:>9} {fits:>5.0f} {msfit:>7.2f} {total:>8.1f}")
        print()

    print("positive in all nine catchments:")
    for policy in ORDER:
        for lead in (1, 2, 3):
            g = groups.get((policy, lead))
            if not g:
                continue
            pos = sum(1 for r in g if num(r["ss_clim"]) > 0)
            print(f"  {policy} lead={lead}: {pos}/{len(g)}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["results"])
