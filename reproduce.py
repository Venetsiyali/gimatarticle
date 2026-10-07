#!/usr/bin/env python3
"""
Reproduction script for GIMAT v1.0 / P-stream v1.0.

Runs everything reported in the paper, in order, from the two source datasets:

    0  conformance tests          T1-T4, including the ablation variants
    1  catchment audit            record completeness and forcing coverage
    2  update policies            nine catchments x C0-C4, S-base
    3  failure grid               C1 x fourteen scenarios
    4  mechanism diagnostics      member availability against the lag window
    5  lag-window ablation        A0-A3 across the failure subset
    6  catchment signatures       and their rank correlation with skill
    7  policy table               the table as printed in the paper

Every stage writes its own CSV under --out and can be re-run alone with
--only; a stage whose output already exists is skipped unless --force is
given, so an interrupted run resumes where it stopped.

    python reproduce.py --gpkg PATH/CA-discharge.gpkg --era5 PATH/era5_gee \
                        --out results/
    python reproduce.py ... --quick     # two catchments, two policies
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = ("tests", "audit", "policies", "failures", "diagnostics",
          "ablation", "signatures", "table")


def banner(n: int, name: str) -> None:
    print(f"\n{'=' * 68}\n[{n}] {name}\n{'=' * 68}", flush=True)


def done(path: str, force: bool) -> bool:
    if os.path.exists(path) and not force:
        print(f"    exists, skipping: {path}")
        return True
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True, help="CA-discharge GeoPackage")
    ap.add_argument("--era5", required=True, help="directory of ERA5 yearly CSVs")
    ap.add_argument("--out", default="results")
    ap.add_argument("--only", nargs="*", choices=STAGES, default=list(STAGES))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="small grid, for checking the pipeline runs")
    args = ap.parse_args(argv)

    sys.path.insert(0, HERE)
    os.makedirs(args.out, exist_ok=True)
    src = ["--gpkg", args.gpkg, "--era5", args.era5]
    basins = ["--basins", "17288", "16279"] if args.quick else []
    t_start = time.time()

    if "tests" in args.only:
        banner(0, "conformance tests")
        r = subprocess.run([sys.executable, "-m", "pytest", "-q",
                            os.path.join(HERE, "tests")],
                           cwd=HERE)
        if r.returncode != 0:
            print("conformance tests failed; stopping")
            return r.returncode

    if "audit" in args.only:
        banner(1, "catchment audit")
        from loaders import BASINS, audit, load_discharge, load_era5
        from experiment import write_csv
        codes = BASINS[:2] if args.quick else BASINS
        q = load_discharge(args.gpkg, codes)
        f = load_era5(args.era5, codes)
        rows = audit(q, f)
        for r in rows:
            print("   ", r)
        write_csv(os.path.join(args.out, "audit.csv"), rows, list(rows[0]))

    if "policies" in args.only:
        banner(2, "update policies, S-base")
        import experiment
        out = os.path.join(args.out, "policies")
        if not done(os.path.join(out, "per_run.csv"), args.force):
            pol = ["C0", "C1"] if args.quick else ["C0", "C1", "C2", "C3", "C4"]
            experiment.main(src + ["--out", out, "--policies", *pol] + basins)

    if "failures" in args.only:
        banner(3, "failure grid, C1")
        import experiment
        out = os.path.join(args.out, "failures")
        if not done(os.path.join(out, "per_run.csv"), args.force):
            scen = ["S-base", "S-miss-20"] if args.quick else ["all"]
            experiment.main(src + ["--out", out, "--policies", "C1",
                                   "--scenarios", *scen] + basins)

    if "diagnostics" in args.only:
        banner(4, "mechanism diagnostics")
        import diagnose
        out = os.path.join(args.out, "diagnostics")
        if not done(os.path.join(out, "diagnostics.csv"), args.force):
            scen = (["S-base", "S-miss-20"] if args.quick else
                    ["S-base", "S-miss-05", "S-miss-10", "S-miss-20",
                     "S-gap-03", "S-gap-12", "S-late-3"])
            diagnose.main(src + ["--out", out, "--scenarios", *scen] + basins)

    if "ablation" in args.only:
        banner(5, "lag-window ablation")
        import ablation
        out = os.path.join(args.out, "ablation")
        if not done(os.path.join(out, "ablation.csv"), args.force):
            var = ["A0", "A2"] if args.quick else ["A0", "A1", "A2", "A3"]
            scen = (["S-base", "S-miss-20"] if args.quick else
                    ["S-base", "S-miss-05", "S-miss-10", "S-miss-20", "S-late-3"])
            ablation.main(src + ["--out", out, "--variants", *var,
                                 "--scenarios", *scen] + basins)

    if "signatures" in args.only:
        banner(6, "catchment signatures")
        import signatures
        out = os.path.join(args.out, "signatures")
        skill = os.path.join(args.out, "policies", "per_run.csv")
        if not done(os.path.join(out, "signatures.csv"), args.force):
            extra = ["--skill", skill] if os.path.exists(skill) else []
            signatures.main(src + ["--out", out] + extra + basins)

    if "table" in args.only:
        banner(7, "policy table")
        import report_policy
        paths = [p for p in (os.path.join(args.out, "policies"),
                             os.path.join(args.out, "failures"))
                 if os.path.exists(os.path.join(p, "per_run.csv"))]
        if paths:
            report_policy.main(paths)

    mins = (time.time() - t_start) / 60
    print(f"\nall requested stages complete in {mins:.1f} min; "
          f"outputs under {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
