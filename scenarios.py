"""
Failure-mode generators for P-stream v1.0.

Each generator takes the clean packet stream of one catchment and returns a
perturbed stream. Perturbations touch arrivals and values only — never the
truth dictionary used for scoring, so a dropped or corrupted packet costs the
system skill exactly as it would in operation.

    S-base   nothing
    S-miss   independent dropouts
    S-gap    one contiguous outage
    S-late   a share of packets arrives k dekads late
    S-spike  isolated corrupted values
    S-drift  slow multiplicative drift over a window
"""

from __future__ import annotations

import random
from typing import Sequence

from pstream import Packet


def truth_of(packets: Sequence[Packet]) -> dict[int, float]:
    """Ground truth for scoring. Always taken from the CLEAN stream."""
    return {p.s: p.value for p in packets}


# --------------------------------------------------------------------------

def s_base(packets: Sequence[Packet], **_) -> list[Packet]:
    return list(packets)


def s_miss(packets: Sequence[Packet], rate: float = 0.10,
           seed: int = 0, protect: int = 0) -> list[Packet]:
    """Independent dropouts at the given rate, warm-up left intact."""
    rng = random.Random(seed)
    return [p for p in packets
            if p.s < protect or rng.random() >= rate]


def s_gap(packets: Sequence[Packet], length: int = 12,
          start: int | None = None, seed: int = 0,
          protect: int = 0) -> list[Packet]:
    """One contiguous outage of `length` dekads."""
    rng = random.Random(seed)
    idx = [p.s for p in packets if p.s >= protect]
    if not idx:
        return list(packets)
    if start is None:
        lo, hi = min(idx), max(idx) - length
        start = rng.randint(lo, max(lo, hi))
    stop = start + length
    return [p for p in packets if not (start <= p.s < stop)]


def s_late(packets: Sequence[Packet], share: float = 0.10,
           max_delay: int = 3, seed: int = 0,
           protect: int = 0) -> list[Packet]:
    """A share of packets reaches the system 1..max_delay dekads late."""
    rng = random.Random(seed)
    out = []
    for p in packets:
        if p.s >= protect and rng.random() < share:
            d = rng.randint(1, max_delay)
            out.append(Packet(s=p.s, value=p.value, a_s=p.a_s + d))
        else:
            out.append(p)
    return out


def s_spike(packets: Sequence[Packet], rate: float = 0.01,
            factor: float = 8.0, seed: int = 0,
            protect: int = 0) -> list[Packet]:
    """Isolated corrupted readings, multiplicative, sign preserved."""
    rng = random.Random(seed)
    out = []
    for p in packets:
        if p.s >= protect and rng.random() < rate:
            mult = factor if rng.random() < 0.5 else 1.0 / factor
            out.append(Packet(s=p.s, value=p.value * mult, a_s=p.a_s))
        else:
            out.append(p)
    return out


def s_drift(packets: Sequence[Packet], magnitude: float = 0.25,
            length: int = 36, start: int | None = None,
            seed: int = 0, protect: int = 0) -> list[Packet]:
    """
    Linear multiplicative drift from 1.0 to 1+magnitude over `length` dekads,
    then held at the drifted level — the signature of an uncalibrated sensor.
    """
    rng = random.Random(seed)
    idx = [p.s for p in packets if p.s >= protect]
    if not idx:
        return list(packets)
    if start is None:
        lo, hi = min(idx), max(idx) - length
        start = rng.randint(lo, max(lo, hi))
    out = []
    for p in packets:
        if p.s < start:
            out.append(p)
            continue
        frac = min(1.0, (p.s - start) / length)
        out.append(Packet(s=p.s, value=p.value * (1.0 + magnitude * frac),
                          a_s=p.a_s))
    return out


# --------------------------------------------------------------------------
# the grid reported in the paper
# --------------------------------------------------------------------------

GRID = [
    ("S-base",        s_base,  {}),
    ("S-miss-05",     s_miss,  dict(rate=0.05)),
    ("S-miss-10",     s_miss,  dict(rate=0.10)),
    ("S-miss-20",     s_miss,  dict(rate=0.20)),
    ("S-gap-03",      s_gap,   dict(length=3)),
    ("S-gap-06",      s_gap,   dict(length=6)),
    ("S-gap-12",      s_gap,   dict(length=12)),
    ("S-late-1",      s_late,  dict(share=0.10, max_delay=1)),
    ("S-late-2",      s_late,  dict(share=0.10, max_delay=2)),
    ("S-late-3",      s_late,  dict(share=0.10, max_delay=3)),
    ("S-spike-01",    s_spike, dict(rate=0.01)),
    ("S-spike-03",    s_spike, dict(rate=0.03)),
    ("S-drift-10",    s_drift, dict(magnitude=0.10)),
    ("S-drift-25",    s_drift, dict(magnitude=0.25)),
]


def apply_scenario(name: str, packets: Sequence[Packet],
                   seed: int = 0, protect: int = 0) -> list[Packet]:
    for label, fn, kw in GRID:
        if label == name:
            return fn(packets, seed=seed, protect=protect, **kw)
    raise KeyError(name)
