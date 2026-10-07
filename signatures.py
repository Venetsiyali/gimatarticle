"""
Catchment signatures and their rank correlation with streaming skill.

Computes a small set of signatures for each catchment from the discharge and
forcing series, and relates them to the skill reported by experiment.py. Used
in the paper to test whether catchment properties explain where skill is low.

Signatures are deliberately simple and derived from the discharge and forcing
series themselves, so no additional data or GIS layers are required:

    q_mean, q_cv         magnitude and relative variability
    seasonality          share of variance explained by the seasonal cycle
    anom_ar1             lag-1 autocorrelation of the seasonal anomalies
    flashiness           Richards-Baker index on dekad differences
    center_of_mass       dekad-of-year at which half the annual flow has passed
    low_flow_share       share of dekads below a tenth of the median
    p_mean, t_mean       mean dekadal precipitation and temperature (ERA5)
    swe_mean, swe_amp    mean and seasonal amplitude of snow water equivalent

With nine catchments, a rank correlation is a hypothesis, not a result; the
output is reported as such.
"""

from __future__ import annotations

import argparse
import math
import os
from typing import Sequence

from experiment import prepare, write_csv
from loaders import BASINS
from pstream import DEKADS_PER_YEAR, doy

SIG_FIELDS = ["basin", "n", "q_mean", "q_cv", "seasonality", "anom_ar1",
              "flashiness", "center_of_mass", "low_flow_share",
              "p_mean", "t_mean", "swe_mean", "swe_amp"]


def _clim(series: Sequence[tuple[int, float]]) -> list[float]:
    tot = [0.0] * DEKADS_PER_YEAR
    cnt = [0] * DEKADS_PER_YEAR
    for s, v in series:
        d = doy(s)
        tot[d] += v
        cnt[d] += 1
    grand = sum(tot) / max(sum(cnt), 1)
    return [tot[d] / cnt[d] if cnt[d] else grand for d in range(DEKADS_PER_YEAR)]


def signatures(series: Sequence[tuple[int, float]],
               exog: dict[int, Sequence[float]] | None = None) -> dict:
    vals = [v for _s, v in series]
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    sd = var ** 0.5

    clim = _clim(series)
    anoms = [v - clim[doy(s)] for s, v in series]
    var_anom = sum(a * a for a in anoms) / n - (sum(anoms) / n) ** 2
    seasonality = 1.0 - var_anom / var if var > 0 else float("nan")

    lookup = dict(series)
    xx = xy = 0.0
    amap = {s: v - clim[doy(s)] for s, v in series}
    for s in lookup:
        prev = amap.get(s - 1)
        if prev is None:
            continue
        xx += prev * prev
        xy += prev * amap[s]
    ar1 = xy / xx if xx > 0 else float("nan")

    diffs = [abs(lookup[s] - lookup[s - 1]) for s in lookup if s - 1 in lookup]
    flashiness = sum(diffs) / sum(vals) if vals else float("nan")

    # centre of mass of the mean annual hydrograph
    total = sum(clim)
    run = 0.0
    com = float("nan")
    for d, c in enumerate(clim):
        run += c
        if run >= total / 2:
            com = float(d)
            break

    med = sorted(vals)[n // 2]
    low = sum(1 for v in vals if v < 0.1 * med) / n

    rec = {
        "n": n,
        "q_mean": round(mean, 4),
        "q_cv": round(sd / mean, 4) if mean else float("nan"),
        "seasonality": round(seasonality, 4),
        "anom_ar1": round(ar1, 4),
        "flashiness": round(flashiness, 4),
        "center_of_mass": com,
        "low_flow_share": round(low, 4),
    }

    if exog:
        bands = list(zip(*[exog[s] for s, _v in series if s in exog]))
        names = ["t_mean", "p_mean", "swe_mean"]      # order of ERA5_BANDS
        for name, band in zip(names, bands):
            rec[name] = round(sum(band) / len(band), 5)
        if len(bands) >= 3:                           # seasonal amplitude of SWE
            swe = {}
            for (s, _v), val in zip([x for x in series if x[0] in exog], bands[2]):
                swe.setdefault(doy(s), []).append(val)
            monthly = [sum(v) / len(v) for v in swe.values()]
            rec["swe_amp"] = round(max(monthly) - min(monthly), 5)
    return rec


# --------------------------------------------------------------------------

def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    pairs = [(a, b) for a, b in zip(x, y) if a == a and b == b]
    n = len(pairs)
    if n < 4:
        return float("nan")

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    a = ranks([p[0] for p in pairs])
    b = ranks([p[1] for p in pairs])
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((ai - ma) * (bi - mb) for ai, bi in zip(a, b))
    den = math.sqrt(sum((ai - ma) ** 2 for ai in a)
                    * sum((bi - mb) ** 2 for bi in b))
    return num / den if den > 0 else float("nan")


def load_skill(path: str, policy: str = "C1", lead: int = 1) -> dict[str, float]:
    import csv
    out = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("policy") == policy and int(r["lead"]) == lead:
                scen = r.get("scenario", "S-base")
                if scen == "S-base":
                    out[r["basin"]] = float(r["ss_clim"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--era5", required=True)
    ap.add_argument("--skill", help="per_run.csv from experiment.py")
    ap.add_argument("--policy", default="C1")
    ap.add_argument("--lead", type=int, default=1)
    ap.add_argument("--out", default="sig")
    ap.add_argument("--basins", nargs="*", default=list(BASINS))
    args = ap.parse_args(argv)

    data = prepare(args.gpkg, args.era5, args.basins)
    rows = []
    for basin in args.basins:
        e = data.get(basin)
        if e is None:
            continue
        rec = signatures(e["series"], e["exog"])
        rec["basin"] = basin
        rows.append(rec)
    write_csv(os.path.join(args.out, "signatures.csv"), rows, SIG_FIELDS)

    head = [f for f in SIG_FIELDS if f not in ("basin", "n")]
    print(f"{'basin':8}" + "".join(f"{h[:9]:>11}" for h in head))
    for r in sorted(rows, key=lambda r: r["basin"]):
        line = f"{r['basin']:8}"
        for h in head:
            v = r.get(h, float('nan'))
            line += f"{v:>11.4f}" if v == v else f"{'-':>11}"
        print(line)

    if not args.skill:
        return
    skill = load_skill(args.skill, args.policy, args.lead)
    rows = [r for r in rows if r["basin"] in skill]
    ss = [skill[r["basin"]] for r in rows]

    print(f"\nskill ({args.policy}, lead {args.lead}), ascending:")
    for r in sorted(rows, key=lambda r: skill[r["basin"]]):
        print(f"  {r['basin']}  SS={skill[r['basin']]:+.3f}")

    print("\nrank correlation with skill (n = %d; hypothesis only):" % len(rows))
    for h in head:
        rho = spearman([r.get(h, float("nan")) for r in rows], ss)
        if rho == rho:
            print(f"  {h:16} rho = {rho:+.3f}")


if __name__ == "__main__":
    main()
