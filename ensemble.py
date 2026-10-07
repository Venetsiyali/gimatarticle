"""
GIMAT v1.0 forecasting members and the causal inverse-RMSE ensemble.

Every feature, every target and every weight is built from the buffer the
runner hands in, i.e. from I(t). Nothing reaches back into the archive.

Leakage channels specifically guarded here:
    L2  scaling statistics        -> none applied; the tree member is
                                     invariant to monotone rescaling
    L6  gap filling               -> lags read backwards only; a missing lag
                                     drops the training row instead of being
                                     interpolated from later values
    L4  hyperparameters           -> frozen constants, never tuned on the
                                     evaluation window
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import xgboost as xgb

from pstream import DEKADS_PER_YEAR, MIN_HISTORY, ClimAR1, doy

N_LAGS = 6                 # HESS configuration, frozen
MIN_TRAIN_ROWS = 120
XGB_PARAMS = dict(
    n_estimators=120,
    max_depth=4,
    learning_rate=0.08,
    subsample=0.9,
    colsample_bytree=0.9,
    reg_lambda=1.0,
    random_state=0,
    n_jobs=1,
    verbosity=0,
)


# --------------------------------------------------------------------------
# feature construction
# --------------------------------------------------------------------------

def _design(series: Sequence[tuple[int, float]], lead: int,
            exog: dict[int, Sequence[float]] | None = None):
    """
    Build (X, y) for a given lead from the admitted series only.

    A row exists for anchor s only when every lag s-0..s-(N_LAGS-1) and the
    target s+lead are present. Gaps therefore remove rows; they are never
    filled from the future.
    """
    lookup = dict(series)
    rows, targets = [], []
    for s, _v in series:
        tgt = lookup.get(s + lead)
        if tgt is None:
            continue
        lags = [lookup.get(s - k) for k in range(N_LAGS)]
        if any(l is None for l in lags):
            continue
        d = doy(s + lead)
        feat = list(lags) + [
            math.sin(2 * math.pi * d / DEKADS_PER_YEAR),
            math.cos(2 * math.pi * d / DEKADS_PER_YEAR),
        ]
        if exog is not None:
            e = exog.get(s)
            if e is None:
                continue
            feat.extend(e)
        rows.append(feat)
        targets.append(tgt)
    if not rows:
        return None, None
    return np.asarray(rows, dtype=float), np.asarray(targets, dtype=float)


def _live_row(series: Sequence[tuple[int, float]], lead: int,
              exog: dict[int, Sequence[float]] | None = None):
    """Feature row for predicting target_s = last_s + lead."""
    lookup = dict(series)
    s = series[-1][0]
    lags = [lookup.get(s - k) for k in range(N_LAGS)]
    if any(l is None for l in lags):
        return None
    d = doy(s + lead)
    feat = list(lags) + [
        math.sin(2 * math.pi * d / DEKADS_PER_YEAR),
        math.cos(2 * math.pi * d / DEKADS_PER_YEAR),
    ]
    if exog is not None:
        e = exog.get(s)
        if e is None:
            return None
        feat.extend(e)
    return np.asarray([feat], dtype=float)


# --------------------------------------------------------------------------
# members
# --------------------------------------------------------------------------

class XGBMember:
    """One gradient-boosted model per lead."""

    def __init__(self, leads: Sequence[int] = (1, 2, 3),
                 exog: dict[int, Sequence[float]] | None = None) -> None:
        self.leads = tuple(leads)
        self.exog = exog
        self._models: dict[int, xgb.XGBRegressor] = {}
        self.fitted = False

    def fit(self, series: Sequence[tuple[int, float]]) -> None:
        self._models.clear()
        for lead in self.leads:
            X, y = _design(series, lead, self.exog)
            if X is None or len(X) < MIN_TRAIN_ROWS:
                continue
            m = xgb.XGBRegressor(**XGB_PARAMS)
            m.fit(X, y)
            self._models[lead] = m
        self.fitted = len(self._models) == len(self.leads)

    # trees do not update in place; C3 keeps the standing forest
    def partial_update(self, series: Sequence[tuple[int, float]]) -> None:
        if not self.fitted:
            self.fit(series)

    def predict(self, series: Sequence[tuple[int, float]],
                target_s: int) -> float | None:
        if not series:
            return None
        lead = target_s - series[-1][0]
        m = self._models.get(lead)
        if m is None:
            return None
        row = _live_row(series, lead, self.exog)
        if row is None:
            return None
        return float(m.predict(row)[0])


# --------------------------------------------------------------------------
# ensemble
# --------------------------------------------------------------------------

class GimatEnsemble:
    """
    Causal inverse-RMSE combination of ClimAR1 and XGBMember.

    Weights come only from forecasts that have already been verified against
    observations present in the buffer, so a weight used at time t never
    reflects an outcome that has not yet arrived.
    """

    MIN_VERIFIED = 24

    def __init__(self, leads: Sequence[int] = (1, 2, 3),
                 exog: dict[int, Sequence[float]] | None = None) -> None:
        self.leads = tuple(leads)
        self.base = ClimAR1()
        self.xgbm = XGBMember(leads, exog)
        self._pending: dict[tuple[int, int], dict[str, float]] = {}
        self._sse: dict[tuple[str, int], float] = {}
        self._cnt: dict[tuple[str, int], int] = {}
        self.last_weights: dict[int, tuple[float, float]] = {}

    # the runner treats any forecaster through this surface
    @property
    def fitted(self) -> bool:
        return self.base.fitted

    @property
    def phi(self) -> float:
        return self.base.phi

    def clim(self, s: int) -> float:
        return self.base.clim(s)

    def fit(self, series) -> None:
        self.base.fit(series)
        if len(series) >= MIN_HISTORY:
            self.xgbm.fit(series)

    def partial_update(self, series) -> None:
        self.base.partial_update(series)
        self.xgbm.partial_update(series)

    # -- verification ------------------------------------------------------
    def verify(self, series) -> None:
        """Score any pending forecast whose target has now been admitted."""
        if not self._pending:
            return
        lookup = dict(series)
        done = []
        for key, preds in self._pending.items():
            target_s, lead = key
            actual = lookup.get(target_s)
            if actual is None:
                continue
            for name in ("base", "xgb"):
                p = preds.get(name)
                if p is None:
                    continue
                mk = (name, int(lead))
                self._sse[mk] = self._sse.get(mk, 0.0) + (p - actual) ** 2
                self._cnt[mk] = self._cnt.get(mk, 0) + 1
            done.append(key)
        for k in done:
            del self._pending[k]

    def _weights(self, lead: int) -> tuple[float, float]:
        kb, kx = ("base", lead), ("xgb", lead)
        nb, nx = self._cnt.get(kb, 0), self._cnt.get(kx, 0)
        if min(nb, nx) < self.MIN_VERIFIED:
            return 1.0, 0.0
        rb = math.sqrt(self._sse[kb] / nb)
        rx = math.sqrt(self._sse[kx] / nx)
        if rb <= 0 or rx <= 0:
            return 1.0, 0.0
        wb, wx = 1.0 / rb, 1.0 / rx
        tot = wb + wx
        return wb / tot, wx / tot

    # -- prediction --------------------------------------------------------
    def predict(self, series, target_s: int) -> float:
        lead = target_s - series[-1][0]
        pb = self.base.predict(series, target_s)
        px = self.xgbm.predict(series, target_s)
        wb, wx = self._weights(lead)
        if px is None:
            wb, wx = 1.0, 0.0
        self.last_weights[lead] = (wb, wx)
        self._pending[(target_s, lead)] = {"base": pb, "xgb": px}
        return wb * pb + wx * (px if px is not None else 0.0)
