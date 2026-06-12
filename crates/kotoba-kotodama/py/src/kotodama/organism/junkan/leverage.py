"""junkan.leverage — Meadows leverage-point CANDIDATES (descriptive, never directive).

ADR-2605290927. G11 (no prescription): junkan offers leverage *candidates* with
an uncertainty band — it never prescribes an intervention or issues a directive.
``LeveragePointCandidate.prescription_given`` is a const False; there is no code
path that sets it True.

Meadows' 12 leverage points (12 = weakest/parameters … 1 = strongest/paradigm),
referenced (Donella Meadows, *Leverage Points: Places to Intervene in a System*),
not vendored.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .loops import CausalLoop

# Meadows' 12 (level -> short label). Lower number = deeper leverage.
MEADOWS_LEVELS: dict[int, str] = {
    12: "Constants, parameters, numbers",
    11: "Buffer sizes / stabilizing stocks",
    10: "Stock-and-flow structure",
    9: "Length of delays",
    8: "Strength of balancing feedback loops",
    7: "Gain of reinforcing feedback loops",
    6: "Information flows (who has access to what)",
    5: "Rules of the system (incentives, constraints)",
    4: "Power to add/change/evolve system structure",
    3: "Goals of the system",
    2: "Mindset/paradigm the system arises from",
    1: "Power to transcend paradigms",
}

UNCERTAINTY = ("wide", "moderate", "narrow")


@dataclass(frozen=True)
class LeveragePointCandidate:
    target_loop_id: str
    meadows_level: int
    description: str
    uncertainty_band: str  # "wide" | "moderate" | "narrow"
    would_flip_to: str  # "virtuous" | "vicious" | "neutral" | "unknown"
    prescription_given: bool = field(default=False)  # G11 const False

    def __post_init__(self) -> None:
        if self.prescription_given:  # pragma: no cover - guard
            raise ValueError("G11: junkan offers candidates, never prescriptions")
        if self.meadows_level not in MEADOWS_LEVELS:
            raise ValueError("meadows_level must be 1..12")
        if self.uncertainty_band not in UNCERTAINTY:
            raise ValueError(f"uncertainty_band must be one of {UNCERTAINTY}")


def rank_leverage_candidates(loop: CausalLoop) -> list[LeveragePointCandidate]:
    """Descriptive candidate set for where ``loop`` could plausibly flip regime.

    Heuristic, hypothesis-grade, ordered deepest-leverage-first. For a vicious
    reinforcing loop the natural candidates are: weaken the reinforcing gain
    (L7), open the information flow that feeds it (L6), and re-examine the goal
    that the loop is optimizing (L3). Each carries an honest uncertainty band.
    """
    flip_to = "neutral"
    if loop.regime == "vicious":
        flip_to = "virtuous"
    elif loop.regime == "virtuous":
        flip_to = "vicious"  # what could degrade it — also worth surfacing

    candidates: list[LeveragePointCandidate] = []
    if loop.loop_type == "reinforcing":
        candidates.append(
            LeveragePointCandidate(loop.loop_id, 7, MEADOWS_LEVELS[7], "moderate", flip_to)
        )
    else:
        candidates.append(
            LeveragePointCandidate(loop.loop_id, 8, MEADOWS_LEVELS[8], "moderate", flip_to)
        )
    candidates.append(
        LeveragePointCandidate(loop.loop_id, 6, MEADOWS_LEVELS[6], "wide", flip_to)
    )
    candidates.append(
        LeveragePointCandidate(loop.loop_id, 3, MEADOWS_LEVELS[3], "wide", flip_to)
    )
    # deepest-leverage-first
    return sorted(candidates, key=lambda c: c.meadows_level)
