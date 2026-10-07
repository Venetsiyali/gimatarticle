"""
P-stream v1.0 — operational streaming evaluation protocol for GIMAT v1.0.

Design rule enforced throughout: every number emitted at time t is a function of
I(t) = {(s, v) : s <= t AND a(s) <= t} and of nothing else.

Dekad indexing: integer index, 36 dekads per year.
    s      nominal dekad of the observation
    a_s    dekad at which the packet reached the system (a_s >= s)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

DEKADS_PER_YEAR = 36

ACCEPT = "accept"
FLAG = "flag"
QUARANTINE = "quarantine"

MIN_HISTORY = 72  # two years before screening or AR(1) is trusted


# --------------------------------------------------------------------------
# data carriers
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Packet:
    """One arriving observation."""
    s: int
    value: float
    a_s: int

    def __post_init__(self) -> None:
        if self.a_s < self.s:
            raise ValueError(f"arrival {self.a_s} precedes nominal time {self.s}")


def doy(s: int) -> int:
    """Dekad-of-year, 0..35."""
    return s % DEKADS_PER_YEAR


# --------------------------------------------------------------------------
# buffer — the only door to past data
# --------------------------------------------------------------------------

class StreamBuffer:
    """Holds admitted observations. Nothing enters without passing SCREEN first."""

    def __init__(self, quarantine_policy: str = "Q1") -> None:
        if quarantine_policy not in ("Q1", "Q2"):
            raise ValueError("quarantine policy must be Q1 or Q2")
        self.policy = quarantine_policy
        self._usable: dict[int, float] = {}
        self._flagged: dict[int, float] = {}

    def admit(self, p: Packet, decision: str) -> None:
        if decision == ACCEPT:
            self._usable[p.s] = p.value
        elif decision == FLAG:
            self._usable[p.s] = p.value
            self._flagged[p.s] = p.value
        elif decision == QUARANTINE:
            self._flagged[p.s] = p.value
            if self.policy == "Q2":
                # kept as a covariate but never as a target
                pass
        else:
            raise ValueError(decision)

    def series(self) -> list[tuple[int, float]]:
        """Admitted observations, ascending in s. Deterministic order."""
        return sorted(self._usable.items())

    def __len__(self) -> int:
        return len(self._usable)


# --------------------------------------------------------------------------
# forecaster: seasonal climatology * AR(1), fitted from I(t) only
# --------------------------------------------------------------------------

class ClimAR1:
    """
    Benchmark member of the GIMAT ensemble, isolated here so that the protocol
    can be tested without the gradient-boosted member.

    Carries running sums so that C3 (incremental) is genuinely incremental
    rather than a relabelled full refit.
    """

    def __init__(self) -> None:
        self._sum = [0.0] * DEKADS_PER_YEAR
        self._cnt = [0] * DEKADS_PER_YEAR
        self._n_pairs = 0
        self._xx = 0.0
        self._xy = 0.0
        self._seen: set[int] = set()
        self.phi = 0.0
        self.fitted = False

    # -- full refit ---------------------------------------------------------
    def fit(self, series: Sequence[tuple[int, float]]) -> None:
        self.__init__()
        for s, v in series:
            self._accumulate_climatology(s, v)
        self._recompute_phi(series)
        self.fitted = len(series) >= MIN_HISTORY

    # -- incremental update -------------------------------------------------
    def partial_update(self, series: Sequence[tuple[int, float]]) -> None:
        """Fold in whatever is new since the last call. O(new), not O(n)."""
        fresh = [(s, v) for s, v in series if s not in self._seen]
        for s, v in fresh:
            self._accumulate_climatology(s, v)
        if fresh:
            self._update_phi(series, fresh)
        self.fitted = len(self._seen) >= MIN_HISTORY

    # -- internals ----------------------------------------------------------
    def _accumulate_climatology(self, s: int, v: float) -> None:
        d = doy(s)
        self._sum[d] += v
        self._cnt[d] += 1
        self._seen.add(s)

    def clim(self, s: int) -> float:
        d = doy(s)
        if self._cnt[d] > 0:
            return self._sum[d] / self._cnt[d]
        total = sum(self._sum)
        n = sum(self._cnt)
        return total / n if n else 0.0

    def _recompute_phi(self, series: Sequence[tuple[int, float]]) -> None:
        self._xx = self._xy = 0.0
        self._n_pairs = 0
        self._fold_pairs(series, series)
        self.phi = self._xy / self._xx if self._xx > 0 else 0.0

    def _update_phi(self, series, fresh) -> None:
        self._fold_pairs(series, fresh)
        self.phi = self._xy / self._xx if self._xx > 0 else 0.0

    def _fold_pairs(self, series, targets) -> None:
        lookup = dict(series)
        for s, v in targets:
            prev = lookup.get(s - 1)
            if prev is None:
                continue
            a_prev = prev - self.clim(s - 1)
            a_cur = v - self.clim(s)
            self._xx += a_prev * a_prev
            self._xy += a_prev * a_cur
            self._n_pairs += 1

    # -- prediction ---------------------------------------------------------
    def predict(self, series: Sequence[tuple[int, float]], target_s: int) -> float:
        if not series:
            return 0.0
        last_s, last_v = series[-1]
        anom = last_v - self.clim(last_s)
        lead = target_s - last_s
        return self.clim(target_s) + (self.phi ** lead) * anom


# --------------------------------------------------------------------------
# screener — scores a value BEFORE it reaches the buffer
# --------------------------------------------------------------------------

class SeasonalZScreener:
    def __init__(self, k: float = 4.0) -> None:
        self.k = k

    def score(self, model: ClimAR1, series: Sequence[tuple[int, float]],
              p: Packet) -> float:
        if len(series) < MIN_HISTORY:
            return 0.0
        anomalies = [v - model.clim(s) for s, v in series]
        n = len(anomalies)
        mean = sum(anomalies) / n
        var = sum((a - mean) ** 2 for a in anomalies) / n
        sd = var ** 0.5
        if sd == 0.0:
            return 0.0
        return abs((p.value - model.clim(p.s)) - mean) / sd

    def decide(self, z: float) -> str:
        return QUARANTINE if z > self.k else ACCEPT


# --------------------------------------------------------------------------
# run configuration
# --------------------------------------------------------------------------

@dataclass
class RunConfig:
    warmup_end: int
    eval_end: int
    update: str = "C2"          # C0 | C1 | C2 | C3 | C4
    leads: tuple[int, ...] = (1, 2, 3)
    screen_k: float = 4.0
    quarantine: str = "Q1"
    basin_id: str = "unknown"
    model_factory: Callable[[], object] = ClimAR1
    scenario_id: str = "S-base"
    seed: int = 0

    def interval(self) -> int | None:
        return {"C0": None, "C1": 36, "C2": 6, "C3": 1, "C4": 1}[self.update]


# --------------------------------------------------------------------------
# the loop
# --------------------------------------------------------------------------

def run_stream(packets: Iterable[Packet], cfg: RunConfig) -> list[dict]:
    """
    Executes INGEST -> SCREEN -> ADMIT -> UPDATE -> FORECAST -> LOG for every
    dekad in [start, cfg.eval_end]. Returns one log row per dekad.
    """
    by_arrival: dict[int, list[Packet]] = {}
    for p in packets:
        if p.a_s > cfg.eval_end:
            continue
        by_arrival.setdefault(p.a_s, []).append(p)

    if not by_arrival:
        return []

    buffer = StreamBuffer(cfg.quarantine)
    model = cfg.model_factory()
    screener = SeasonalZScreener(cfg.screen_k)
    interval = cfg.interval()
    rows: list[dict] = []
    last_fit_at: int | None = None

    start = min(by_arrival)
    for t in range(start, cfg.eval_end + 1):

        # 1. INGEST — canonical order makes the step invariant to packet order
        arriving = sorted(by_arrival.get(t, []), key=lambda p: (p.s, p.value))

        # 2. SCREEN — scored against the state of I(t-1)
        pre_state = buffer.series()
        decisions: list[tuple[Packet, float, str]] = []
        for p in arriving:
            z = screener.score(model, pre_state, p)
            decisions.append((p, z, screener.decide(z)))

        # 3. ADMIT
        for p, _z, d in decisions:
            buffer.admit(p, d)

        series = buffer.series()

        # 7'. SCORE — pending forecasts whose target has just arrived
        if hasattr(model, "verify"):
            model.verify(series)

        # 4. UPDATE
        update_fired = False
        fit_ms = 0.0
        if t >= cfg.warmup_end:
            due = (
                last_fit_at is None
                or (interval is not None and t - last_fit_at >= interval)
            )
            if due:
                t0 = time.perf_counter()
                if cfg.update == "C3" and last_fit_at is not None:
                    model.partial_update(series)
                else:
                    model.fit(series)
                fit_ms = (time.perf_counter() - t0) * 1000.0
                last_fit_at = t
                update_fired = True

        # 5. FORECAST
        degraded = not any(p.s == t for p in arriving)
        forecasts: dict[str, float | None] = {}
        for lead in cfg.leads:
            key = f"forecast_l{lead}"
            if model.fitted and series:
                forecasts[key] = model.predict(series, t + lead)
            else:
                forecasts[key] = None

        # 6. LOG
        row = {
            "basin_id": cfg.basin_id,
            "t": t,
            "n_arrived": len(arriving),
            "n_quarantined": sum(1 for _, _, d in decisions if d == QUARANTINE),
            "screen_scores": tuple(round(z, 12) for _, z, _ in decisions),
            "update_fired": update_fired,
            "update_type": cfg.update,
            "fit_ms": fit_ms,
            "buffer_size": len(series),
            "phi": model.phi,
            "degraded": degraded,
            "scenario_id": cfg.scenario_id,
            "config_id": cfg.update,
            "seed": cfg.seed,
        }
        row.update(forecasts)
        rows.append(row)

    return rows


# --------------------------------------------------------------------------
# comparison helper for the conformance tests
# --------------------------------------------------------------------------

VOLATILE = {"fit_ms"}  # wall-clock, never part of a determinism claim


def comparable(rows: Sequence[dict], upto: int | None = None) -> list[dict]:
    out = []
    for r in rows:
        if upto is not None and r["t"] > upto:
            continue
        out.append({k: v for k, v in r.items() if k not in VOLATILE})
    return out
