"""
Evaluation module for GIMAT v1.0 / P-stream v1.0.

The statistical apparatus used throughout the paper:

    Diebold-Mariano   squared errors, Newey-West variance truncated at h-1,
                      Harvey-Leybourne-Newbold small-sample correction,
                      Student-t with T-1 degrees of freedom
    Clark-West        one-sided, for the nested case (climatology * AR(1) is
                      a member of the ensemble, so DM alone is not enough)
    multiplicity      Holm across catchments, Benjamini-Hochberg reported
                      alongside
    uncertainty       moving-block bootstrap, block = 36 dekads (one year,
                      preserving the seasonal cycle), 2000 resamples
    pooled evidence   two-sided sign test across catchments
"""

from __future__ import annotations

import math
import random
from typing import Sequence

import numpy as np
from scipy import stats

BLOCK = 36          # one year of dekads
N_BOOT = 2000


# --------------------------------------------------------------------------
# point metrics
# --------------------------------------------------------------------------

def nse(obs: np.ndarray, sim: np.ndarray) -> float:
    obs = np.asarray(obs, float); sim = np.asarray(sim, float)
    denom = np.sum((obs - obs.mean()) ** 2)
    if denom <= 0:
        return float("nan")
    return float(1.0 - np.sum((obs - sim) ** 2) / denom)


def rmse(obs, sim) -> float:
    obs = np.asarray(obs, float); sim = np.asarray(sim, float)
    return float(np.sqrt(np.mean((obs - sim) ** 2)))


def skill_score(obs, sim, ref) -> float:
    """SS = 1 - MSE(model) / MSE(reference). Reference is climatology*AR(1)."""
    obs = np.asarray(obs, float)
    mse_m = np.mean((obs - np.asarray(sim, float)) ** 2)
    mse_r = np.mean((obs - np.asarray(ref, float)) ** 2)
    if mse_r <= 0:
        return float("nan")
    return float(1.0 - mse_m / mse_r)


# --------------------------------------------------------------------------
# Diebold-Mariano
# --------------------------------------------------------------------------

def dm_test(e1, e2, h: int = 1, power: int = 2) -> tuple[float, float]:
    """
    e1, e2 are error series (obs - sim) of the two competing forecasts.
    A negative statistic favours the first-named model.
    """
    e1 = np.asarray(e1, float); e2 = np.asarray(e2, float)
    d = np.abs(e1) ** power - np.abs(e2) ** power
    T = len(d)
    if T < 8:
        return float("nan"), float("nan")
    dbar = d.mean()
    lags = max(int(h) - 1, 0)
    g = [np.sum((d[k:] - dbar) * (d[:T - k] - dbar)) / T for k in range(lags + 1)]
    V = (g[0] + 2.0 * sum(g[1:])) / T
    if not np.isfinite(V) or V <= 0:
        return float("nan"), float("nan")
    stat = dbar / math.sqrt(V)
    corr = math.sqrt(max((T + 1 - 2 * h + h * (h - 1) / T) / T, 1e-12))
    stat *= corr
    p = 2.0 * (1.0 - stats.t.cdf(abs(stat), df=T - 1))
    return float(stat), float(p)


def clark_west(obs, sim_small, sim_large, h: int = 1) -> tuple[float, float]:
    """
    One-sided Clark-West test for nested models.

    sim_small is the restricted forecast (climatology * AR(1)); sim_large is
    the ensemble that nests it. H0: equal MSPE; H1: the larger model is better.
    """
    obs = np.asarray(obs, float)
    s = np.asarray(sim_small, float)
    l = np.asarray(sim_large, float)
    f = (obs - s) ** 2 - ((obs - l) ** 2 - (s - l) ** 2)
    T = len(f)
    if T < 8:
        return float("nan"), float("nan")
    fbar = f.mean()
    lags = max(int(h) - 1, 0)
    g = [np.sum((f[k:] - fbar) * (f[:T - k] - fbar)) / T for k in range(lags + 1)]
    V = (g[0] + 2.0 * sum(g[1:])) / T
    if not np.isfinite(V) or V <= 0:
        return float("nan"), float("nan")
    stat = fbar / math.sqrt(V)
    p = 1.0 - stats.t.cdf(stat, df=T - 1)      # one-sided
    return float(stat), float(p)


# --------------------------------------------------------------------------
# multiplicity
# --------------------------------------------------------------------------

def holm(pvals: Sequence[float]) -> list[float]:
    p = list(pvals)
    idx = [i for i, v in enumerate(p) if v == v]       # drop NaN
    m = len(idx)
    out = [float("nan")] * len(p)
    if m == 0:
        return out
    order = sorted(idx, key=lambda i: p[i])
    running = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * p[i])
        running = max(running, adj)
        out[i] = running
    return out


def benjamini_hochberg(pvals: Sequence[float]) -> list[float]:
    p = list(pvals)
    idx = [i for i, v in enumerate(p) if v == v]
    m = len(idx)
    out = [float("nan")] * len(p)
    if m == 0:
        return out
    order = sorted(idx, key=lambda i: p[i], reverse=True)
    running = 1.0
    for rank, i in enumerate(order):
        k = m - rank
        adj = min(1.0, p[i] * m / k)
        running = min(running, adj)
        out[i] = running
    return out


# --------------------------------------------------------------------------
# moving-block bootstrap
# --------------------------------------------------------------------------

def block_bootstrap_ci(obs, sim, ref=None, stat: str = "nse",
                       block: int = BLOCK, n_boot: int = N_BOOT,
                       alpha: float = 0.05, seed: int = 0):
    """
    Percentile interval for NSE or SS under a moving-block bootstrap.

    Blocks of 36 dekads keep the seasonal cycle intact; sampling blocks rather
    than points also keeps the serial dependence that makes naive intervals
    far too narrow.
    """
    obs = np.asarray(obs, float); sim = np.asarray(sim, float)
    ref = None if ref is None else np.asarray(ref, float)
    T = len(obs)
    if T < block * 2:
        block = max(2, T // 4)
    n_blocks = int(math.ceil(T / block))
    starts = max(T - block + 1, 1)
    rng = random.Random(seed)

    def value(o, s, r):
        if stat == "nse":
            return nse(o, s)
        return skill_score(o, s, r)

    point = value(obs, sim, ref)
    draws = []
    for _ in range(n_boot):
        pick = [rng.randrange(starts) for _ in range(n_blocks)]
        idx = np.concatenate([np.arange(b, min(b + block, T)) for b in pick])[:T]
        v = value(obs[idx], sim[idx], None if ref is None else ref[idx])
        if v == v:
            draws.append(v)
    if not draws:
        return point, float("nan"), float("nan")
    lo = float(np.percentile(draws, 100 * alpha / 2))
    hi = float(np.percentile(draws, 100 * (1 - alpha / 2)))
    return float(point), lo, hi


# --------------------------------------------------------------------------
# pooled evidence across catchments
# --------------------------------------------------------------------------

def sign_test(diffs: Sequence[float]) -> tuple[int, int, float]:
    """Two-sided sign test. Returns (n_positive, n_used, p)."""
    d = [x for x in diffs if x == x and x != 0.0]
    n = len(d)
    if n == 0:
        return 0, 0, float("nan")
    pos = sum(1 for x in d if x > 0)
    p = float(min(1.0, 2.0 * stats.binom.cdf(min(pos, n - pos), n, 0.5)))
    return pos, n, p


# --------------------------------------------------------------------------
# assembling a run's log into evaluation arrays
# --------------------------------------------------------------------------

def align(rows: Sequence[dict], truth: dict[int, float], lead: int,
          skip_degraded: bool = False):
    """
    Pairs each logged forecast with the observation it was aiming at.

    A forecast issued at t for t+lead is scored against truth[t+lead]; rows
    without a forecast, or whose target was never observed, are dropped. With
    skip_degraded, steps taken while the system was running on substituted
    input are excluded as well.
    """
    key = f"forecast_l{lead}"
    ts, obs, sim = [], [], []
    for r in rows:
        f = r.get(key)
        if f is None:
            continue
        if skip_degraded and r.get("degraded"):
            continue
        target = r["t"] + lead
        actual = truth.get(target)
        if actual is None:
            continue
        ts.append(target); obs.append(actual); sim.append(f)
    return np.asarray(ts), np.asarray(obs, float), np.asarray(sim, float)


def summarise(rows, truth, ref_rows=None, leads=(1, 2, 3), seed: int = 0):
    """One row per lead: NSE, SS vs reference, bootstrap interval, n."""
    out = []
    for lead in leads:
        _t, o, s = align(rows, truth, lead)
        if len(o) < 24:
            continue
        rec = {"lead": lead, "n": len(o), "nse": nse(o, s), "rmse": rmse(o, s)}
        if ref_rows is not None:
            _t2, o2, r2 = align(ref_rows, truth, lead)
            common = min(len(o), len(o2))
            rec["ss_ref"] = skill_score(o[-common:], s[-common:], r2[-common:])
            rec["dm"], rec["dm_p"] = dm_test(o[-common:] - s[-common:],
                                             o[-common:] - r2[-common:], h=lead)
            rec["cw"], rec["cw_p"] = clark_west(o[-common:], r2[-common:],
                                                s[-common:], h=lead)
        pt, lo, hi = block_bootstrap_ci(o, s, stat="nse", seed=seed + lead)
        rec["nse_lo"], rec["nse_hi"] = lo, hi
        out.append(rec)
    return out
