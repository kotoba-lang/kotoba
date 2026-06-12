"""junkan.models — shared dataclasses (kept dependency-light to avoid import cycles).

ADR-2605290927.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StockSeries:
    stock_id: str
    levels: list[int]
    unit: str
    desirability: int  # +1 higher-is-better, -1 lower-is-better
    source_cid: str  # G3 provenance (pre-published public archive)


@dataclass(frozen=True)
class LoopSpec:
    loop_id: str
    stock_cycle: list[str]  # ordered stock ids; edges are consecutive incl. wraparound


@dataclass(frozen=True)
class FindingBundle:
    """The sole output of junkan. Read-only; no outward channel (G4)."""

    causal_loop_findings: list[dict] = field(default_factory=list)
    leverage_findings: list[dict] = field(default_factory=list)
    regime_shifts: list[dict] = field(default_factory=list)
    discovered_loop_ids: list[str] = field(default_factory=list)
    actuation_taken: bool = False  # G4 const False — junkan never acts
