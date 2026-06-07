"""Pure scoring functions for ``EligibilityCell``.

Kept LLM-free so the entire phenotype-multiplier pipeline is
deterministic and replayable from the MST event log. Per
ADR-2605172300 §3.1 + ADR-2605172000 (RW-free / pure-reducer rule).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

# Constitutional band, mirroring ``Constitution.sol`` defaults from S0.
# Off-chain code reads the chain to confirm; the constants here are
# documentation + a sane safety net.
PHENOTYPE_MIN_BPS_DEFAULT = 5_000   # 0.50x
PHENOTYPE_MAX_BPS_DEFAULT = 20_000  # 2.00x
PHENOTYPE_NEUTRAL_BPS = 10_000      # 1.00x

# Canonical event-type weights. Sum should be small; the multiplier
# computation is robust to additive changes via the cap below.
DEFAULT_EVENT_WEIGHTS: Mapping[str, float] = {
    "prayer": 1.0,
    "study": 1.2,
    "service": 1.5,
    "donation": 0.8,
}


@dataclass(frozen=True)
class AttestationEvent:
    """One on-chain attestation entry as the cell sees it.

    Read either from ``AdherentRegistry.Attested`` events on geth-private
    or, equivalently, from the AT Record stream on the adherent's PDS.
    Both surfaces carry the same information; the cell prefers the
    chain side when both are available (chain order is canonical).
    """

    token_id: int
    event_type: str
    evidence_cid: bytes  # 32-byte keccak / blake hash (zero = no evidence)
    attested_at: int  # unix seconds


@dataclass(frozen=True)
class EligibilityState:
    token_id: int
    window_start: int  # unix seconds; inclusive
    window_end: int    # unix seconds; inclusive
    events: tuple[AttestationEvent, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PhenotypeUpdate:
    token_id: int
    bps: int
    score: float
    breakdown: Mapping[str, float]


def score_participation(
    state: EligibilityState,
    weights: Mapping[str, float] = DEFAULT_EVENT_WEIGHTS,
) -> tuple[float, dict[str, float]]:
    """Score an adherent's participation in ``[window_start, window_end]``.

    Three orthogonal factors, multiplicatively combined:

      - ``breadth``: number of distinct event types touched, normalized
        against the count of canonical event types in ``weights``.
      - ``volume``: weight-summed event count, capped by a soft ceiling
        so a single-axis spammer cannot saturate.
      - ``consistency``: 1.0 if the adherent has at least one event in
        each quartile of the window; decays linearly otherwise.

    The result is in the open interval ``(0, ~3.5)`` for typical inputs;
    {multiplier_from_score} maps this to bps.
    """
    events = state.events
    breakdown: dict[str, float] = {}

    if not events:
        breakdown["breadth"] = 0.0
        breakdown["volume"] = 0.0
        breakdown["consistency"] = 0.0
        return 0.0, breakdown

    # breadth
    distinct = {e.event_type for e in events if e.event_type in weights}
    canonical_count = len(weights) or 1
    breadth = len(distinct) / canonical_count
    breakdown["breadth"] = breadth

    # volume — sum of weights, with a soft ceiling
    raw_volume = sum(weights.get(e.event_type, 0.0) for e in events)
    # Soft ceiling: 1 - exp(-x/8) saturates near ~1.0 around 24 events.
    import math

    volume = 1.0 - math.exp(-raw_volume / 8.0)
    breakdown["volume"] = volume

    # consistency — quartile coverage of [window_start, window_end]
    span = max(1, state.window_end - state.window_start)
    quartile_hits = [False, False, False, False]
    for e in events:
        rel = (e.attested_at - state.window_start) / span
        q = max(0, min(3, int(rel * 4)))
        quartile_hits[q] = True
    consistency = sum(quartile_hits) / 4.0
    breakdown["consistency"] = consistency

    score = breadth * volume * consistency * 3.5  # scale to ~max 3.5
    return score, breakdown


def multiplier_from_score(
    score: float,
    floor_bps: int = PHENOTYPE_MIN_BPS_DEFAULT,
    ceiling_bps: int = PHENOTYPE_MAX_BPS_DEFAULT,
    neutral_bps: int = PHENOTYPE_NEUTRAL_BPS,
) -> int:
    """Map a participation score to a basis-points multiplier.

    The mapping is intentionally simple and monotonic:

      - score ≤ 0.5  → floor_bps
      - score ≈ 1.0  → neutral_bps (≈ 1.0×)
      - score ≥ 3.0  → ceiling_bps
      - between, linearly interpolated and clamped.

    The constitutional clamp lives on-chain (``Phenotype.sol``); this
    function clamps the same way to avoid ever building a payload that
    would be rejected.
    """
    if score <= 0.5:
        return floor_bps
    if score >= 3.0:
        return ceiling_bps
    if score <= 1.0:
        # 0.5..1.0 → floor..neutral
        t = (score - 0.5) / 0.5
        return int(floor_bps + (neutral_bps - floor_bps) * t)
    # 1.0..3.0 → neutral..ceiling
    t = (score - 1.0) / 2.0
    bps = int(neutral_bps + (ceiling_bps - neutral_bps) * t)
    if bps < floor_bps:
        bps = floor_bps
    if bps > ceiling_bps:
        bps = ceiling_bps
    return bps


def collapse_events(events: Iterable[AttestationEvent]) -> tuple[AttestationEvent, ...]:
    """Sort + dedupe events by ``(token_id, attested_at, evidence_cid)``.

    Deterministic ordering matters for replayability — running the cell
    twice on the same MST view MUST produce byte-identical payloads.
    """
    seen: set[tuple[int, int, bytes]] = set()
    out: list[AttestationEvent] = []
    for e in sorted(events, key=lambda x: (x.token_id, x.attested_at, x.evidence_cid)):
        key = (e.token_id, e.attested_at, e.evidence_cid)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return tuple(out)
