"""
Interpolated values in the source record.

The discharge compilation fills isolated single-dekad gaps by linear
interpolation between the neighbouring values. A filled value at s depends on
the value at s + 1, so it is leakage that precedes the system and that the
conformance tests cannot see. The compilation does not mark filled values.

This module identifies candidates as values equal to the mean of their two
neighbours, excluding flat runs. That is an upper bound: recessions recorded
on a coarse measurement grid produce exact midpoints naturally.

Three modes:

    count     share of candidates per catchment (Table 3 of the paper)
    remove    rerun C1 / S-base with every candidate treated as never arrived
    control   rerun with the same number of randomly chosen records removed,
              drawn from the same parts of each record (warm-up / evaluation)

The difference between `remove` and `control` bounds the contribution of the
filled values to skill; see Sect. 5.1 of the paper.

    python fills.py --gpkg PATH --era5 DIR --mode count
    python fills.py --gpkg PATH --era5 DIR --mode remove  --out nofill/
    python fills.py --gpkg PATH --era5 DIR --mode control --out randctrl/
"""

from __future__ import annotations

import argparse
import random
from typing import Sequence

import experiment
import loaders
from loaders import BASINS

TOL = 1e-6


def candidates(series: Sequence[tuple[int, float]]) -> set[int]:
    """Indices whose value equals the mean of both neighbours (flat runs excluded)."""
    d = dict(series)
    return {t for t in d
            if t - 1 in d and t + 1 in d
            and abs(d[t] - (d[t - 1] + d[t + 1]) / 2) < TOL
            and not (d[t - 1] == d[t] == d[t + 1])}


def _loader(mode: str, warmup: int):
    original = loaders.load_discharge

    def load(gpkg, basins):
        out = {}
        for code, ser in original(gpkg, basins).items():
            mids = candidates(ser)
            if mode == "remove":
                drop = mids
            else:
                d = dict(ser)
                s0 = min(d)
                rng = random.Random(int(code))
                drop = set()
                for in_warm in (True, False):
                    k = sum(1 for t in mids if (t - s0 < warmup) == in_warm)
                    pool = sorted(t for t in d
                                  if (t - s0 < warmup) == in_warm and t not in mids)
                    drop |= set(rng.sample(pool, k))
            out[code] = [(t, v) for t, v in ser if t not in drop]
        return out
    return load


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--era5", required=True)
    ap.add_argument("--mode", choices=("count", "remove", "control"), default="count")
    ap.add_argument("--out", default="fills")
    ap.add_argument("--basins", nargs="*", default=list(BASINS))
    args = ap.parse_args(argv)

    if args.mode == "count":
        q = loaders.load_discharge(args.gpkg, args.basins)
        print(f"{'code':6} {'n':>5} {'cand':>5} {'share':>7}")
        for code in args.basins:
            ser = q.get(code)
            if not ser:
                continue
            k = len(candidates(ser))
            print(f"{code:6} {len(ser):5d} {k:5d} {k / len(ser):7.1%}")
        return

    experiment.load_discharge = _loader(args.mode, experiment.WARMUP_END)
    experiment.main(["--gpkg", args.gpkg, "--era5", args.era5, "--out", args.out,
                     "--policies", "C1", "--scenarios", "S-base", "--quiet",
                     "--basins", *args.basins])


if __name__ == "__main__":
    main()
