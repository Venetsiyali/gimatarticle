"""
Conformance tests for P-stream v1.0.

T1 future poisoning   — outputs at t must not move when the future is replaced
                        by absurd values
T2 truncation         — running on the truncated archive must equal running on
                        the full archive, up to the cut
T3 determinism        — identical inputs, identical outputs
T4 arrival order      — packets sharing an arrival dekad may come in any order

These four are the mechanical proof that no leakage channel (L1-L7) is open.
"""

import math
import random

from pstream import (
    DEKADS_PER_YEAR,
    Packet,
    RunConfig,
    comparable,
    doy,
    run_stream,
)

N_YEARS = 40
N = N_YEARS * DEKADS_PER_YEAR          # 1440 dekads
WARMUP_END = 10 * DEKADS_PER_YEAR      # 360
EVAL_END = N - 10


def synthetic(seed: int = 0, late_fraction: float = 0.0,
              max_delay: int = 3) -> list[Packet]:
    """Seasonal signal + AR(1) noise, optionally with late arrivals."""
    rng = random.Random(seed)
    packets, anom = [], 0.0
    for s in range(N):
        seasonal = 20.0 + 14.0 * math.sin(2 * math.pi * doy(s) / DEKADS_PER_YEAR)
        anom = 0.55 * anom + rng.gauss(0.0, 2.2)
        value = max(0.1, seasonal + anom)
        delay = rng.randint(1, max_delay) if rng.random() < late_fraction else 0
        packets.append(Packet(s=s, value=value, a_s=s + delay))
    return packets


def cfg(**kw) -> RunConfig:
    base = dict(warmup_end=WARMUP_END, eval_end=EVAL_END, update="C2")
    base.update(kw)
    return RunConfig(**base)


# ---------------------------------------------------------------- T1
def test_t1_future_poisoning_does_not_move_present():
    cut = WARMUP_END + 200
    clean = synthetic(seed=1)
    poisoned = [
        p if p.s <= cut else Packet(s=p.s, value=1e6, a_s=p.a_s)
        for p in clean
    ]

    a = run_stream(clean, cfg())
    b = run_stream(poisoned, cfg())

    assert comparable(a, upto=cut) == comparable(b, upto=cut)


def test_t1_holds_for_every_update_policy():
    cut = WARMUP_END + 120
    clean = synthetic(seed=2)
    poisoned = [
        p if p.s <= cut else Packet(s=p.s, value=-5e5, a_s=p.a_s)
        for p in clean
    ]
    for policy in ("C0", "C1", "C2", "C3", "C4"):
        a = run_stream(clean, cfg(update=policy))
        b = run_stream(poisoned, cfg(update=policy))
        assert comparable(a, upto=cut) == comparable(b, upto=cut), policy


# ---------------------------------------------------------------- T2
def test_t2_truncated_archive_matches_full_archive():
    cut = WARMUP_END + 300
    full = synthetic(seed=3)
    truncated = [p for p in full if p.a_s <= cut]

    a = run_stream(full, cfg())
    b = run_stream(truncated, cfg(eval_end=cut))

    assert comparable(a, upto=cut) == comparable(b, upto=cut)


def test_t2_holds_with_late_arrivals():
    cut = WARMUP_END + 300
    full = synthetic(seed=4, late_fraction=0.15)
    truncated = [p for p in full if p.a_s <= cut]

    a = run_stream(full, cfg())
    b = run_stream(truncated, cfg(eval_end=cut))

    assert comparable(a, upto=cut) == comparable(b, upto=cut)


# ---------------------------------------------------------------- T3
def test_t3_determinism():
    data = synthetic(seed=5, late_fraction=0.1)
    assert comparable(run_stream(data, cfg())) == comparable(run_stream(data, cfg()))


# ---------------------------------------------------------------- T4
def test_t4_arrival_order_is_irrelevant():
    rng = random.Random(99)
    data = synthetic(seed=6, late_fraction=0.3)

    grouped: dict[int, list[Packet]] = {}
    for p in data:
        grouped.setdefault(p.a_s, []).append(p)
    shuffled: list[Packet] = []
    for a_s in sorted(grouped):
        group = grouped[a_s][:]
        rng.shuffle(group)
        shuffled.extend(group)

    assert comparable(run_stream(data, cfg())) == comparable(run_stream(shuffled, cfg()))


# ------------------------------------------------- sanity: the loop runs
def test_screening_precedes_admission():
    """A single absurd spike must be quarantined, not silently absorbed."""
    data = synthetic(seed=7)
    spike_at = WARMUP_END + 500
    data = [
        Packet(s=p.s, value=5000.0, a_s=p.a_s) if p.s == spike_at else p
        for p in data
    ]
    rows = run_stream(data, cfg())
    row = next(r for r in rows if r["t"] == spike_at)
    assert row["n_quarantined"] == 1


def test_forecasts_exist_after_warmup():
    rows = run_stream(synthetic(seed=8), cfg())
    late = [r for r in rows if r["t"] > WARMUP_END + 50]
    assert all(r["forecast_l1"] is not None for r in late)


# ------------------------------------------------- ensemble conformance
def _ens():
    from ensemble import GimatEnsemble
    return GimatEnsemble(leads=(1, 2, 3))


def test_t1_holds_for_the_full_ensemble():
    cut = WARMUP_END + 150
    clean = synthetic(seed=11)
    poisoned = [
        p if p.s <= cut else Packet(s=p.s, value=1e6, a_s=p.a_s)
        for p in clean
    ]
    c = cfg(eval_end=cut + 40, update="C2", model_factory=_ens)
    assert comparable(run_stream(clean, c), upto=cut) == \
           comparable(run_stream(poisoned, c), upto=cut)


def test_t3_determinism_for_the_full_ensemble():
    c = cfg(eval_end=WARMUP_END + 200, update="C2", model_factory=_ens)
    data = synthetic(seed=12)
    assert comparable(run_stream(data, c)) == comparable(run_stream(data, c))


def test_ensemble_weights_stay_causal():
    """Before MIN_VERIFIED outcomes exist, XGB must carry zero weight."""
    from ensemble import GimatEnsemble
    e = GimatEnsemble(leads=(1,))
    assert e._weights(1) == (1.0, 0.0)


# ------------------------------------------------- ablation conformance
def test_ablation_variants_are_leak_free():
    """
    T1 must hold for every feature construction, including the NaN-aware ones
    where rows are no longer dropped. If a variant ever reached forward to
    fill a gap, poisoning the future would move the present.
    """
    import ablation
    from ensemble import GimatEnsemble

    cut = WARMUP_END + 150
    clean = synthetic(seed=21, late_fraction=0.1)
    poisoned = [
        p if p.s <= cut else Packet(s=p.s, value=1e6, a_s=p.a_s)
        for p in clean
    ]
    for variant in ("A1", "A2", "A3"):
        c = cfg(eval_end=cut + 40, update="C1",
                model_factory=lambda: GimatEnsemble(leads=(1, 2)))
        with ablation._Patch(variant):
            a = run_stream(clean, c)
            b = run_stream(poisoned, c)
        assert comparable(a, upto=cut) == comparable(b, upto=cut), variant


def test_nan_aware_variant_always_has_a_live_row():
    """A2 must be able to speak even when the lag window is full of holes."""
    import ablation
    design, live = ablation.make_builders("A2")
    series = [(100, 5.0), (103, 6.0), (106, 7.0)]      # deliberate gaps
    assert live(series, 1) is not None
    base_design, base_live = ablation.make_builders("A1")
    assert base_live(series, 1) is None                # A1 cannot
