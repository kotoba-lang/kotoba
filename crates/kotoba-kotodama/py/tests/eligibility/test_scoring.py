"""Determinism + band invariants for EligibilityCell scoring.

S2 of ADR-2605172300 hangs kisha rate on a multiplier produced by a pure
reducer over the adherent's MST event stream. The on-chain `Phenotype`
contract enforces a constitutional band ([5_000, 20_000] bps); these
tests assert the Python side never produces a value outside that band
and that two runs over the same input produce byte-identical output.
"""

from __future__ import annotations

import pytest

from kotodama.eligibility.scoring import (
    PHENOTYPE_MAX_BPS_DEFAULT,
    PHENOTYPE_MIN_BPS_DEFAULT,
    PHENOTYPE_NEUTRAL_BPS,
    AttestationEvent,
    EligibilityState,
    collapse_events,
    multiplier_from_score,
    score_participation,
)


# ─── Helpers ─────────────────────────────────────────────────────────


def _ev(token_id: int, t: int, kind: str = "prayer") -> AttestationEvent:
    return AttestationEvent(
        token_id=token_id,
        event_type=kind,
        evidence_cid=b"\x00" * 32,
        attested_at=t,
    )


def _state(token_id: int, events: list[AttestationEvent], start: int, end: int) -> EligibilityState:
    return EligibilityState(
        token_id=token_id,
        window_start=start,
        window_end=end,
        events=tuple(collapse_events(events)),
    )


# ─── multiplier_from_score: constitutional band invariant ────────────


@pytest.mark.parametrize("score", [-10.0, -1.0, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 100.0])
def test_multiplier_within_band(score: float) -> None:
    """For any score, multiplier must be clipped to [floor, ceiling].

    This mirrors the on-chain ``Phenotype.OutOfBand`` revert: if the
    Python side ever returned a value outside [5_000, 20_000], the
    contract would reject the resulting `setMultiplier` payload.
    """
    bps = multiplier_from_score(score)
    assert PHENOTYPE_MIN_BPS_DEFAULT <= bps <= PHENOTYPE_MAX_BPS_DEFAULT
    assert isinstance(bps, int)


def test_multiplier_monotonic_in_score() -> None:
    """Higher score → equal or higher multiplier (no inversions)."""
    scores = [-1.0, 0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
    bps = [multiplier_from_score(s) for s in scores]
    for prev, curr in zip(bps, bps[1:]):
        assert curr >= prev, f"multiplier decreased at boundary: {prev} → {curr}"


def test_multiplier_anchor_points() -> None:
    """Known anchor points: ≤0.5 → floor; ≥3.0 → ceiling; ≈1.0 → neutral."""
    assert multiplier_from_score(0.0) == PHENOTYPE_MIN_BPS_DEFAULT
    assert multiplier_from_score(0.5) == PHENOTYPE_MIN_BPS_DEFAULT
    assert multiplier_from_score(3.0) == PHENOTYPE_MAX_BPS_DEFAULT
    assert multiplier_from_score(10.0) == PHENOTYPE_MAX_BPS_DEFAULT
    assert multiplier_from_score(1.0) == PHENOTYPE_NEUTRAL_BPS


# ─── score_participation: determinism + structure ─────────────────────


def test_score_empty_window_is_zero() -> None:
    s = _state(1, [], 0, 30 * 86400)
    score, breakdown = score_participation(s)
    assert score == 0.0
    assert breakdown["breadth"] == 0.0
    assert breakdown["volume"] == 0.0
    assert breakdown["consistency"] == 0.0


def test_score_deterministic_byte_identical() -> None:
    """Same input → byte-identical output across runs.

    Required for the EligibilityCell to be replayable from the MST
    event log alone (ADR-2605172000 RW-free hard rule).
    """
    events = [_ev(1, 86400 * i, "prayer") for i in range(0, 30)]
    s1 = _state(1, events, 0, 30 * 86400)
    s2 = _state(1, events, 0, 30 * 86400)

    score1, breakdown1 = score_participation(s1)
    score2, breakdown2 = score_participation(s2)

    assert score1 == score2
    assert breakdown1 == breakdown2


def test_score_independent_of_event_input_order() -> None:
    """Permutations of the same events yield the same score —
    ``collapse_events`` sorts before reducing."""
    base = [_ev(1, 86400 * i, "prayer") for i in range(0, 30)]
    reversed_ = list(reversed(base))
    shuffled = base[15:] + base[:15]

    s1 = _state(1, base, 0, 30 * 86400)
    s2 = _state(1, reversed_, 0, 30 * 86400)
    s3 = _state(1, shuffled, 0, 30 * 86400)

    assert score_participation(s1) == score_participation(s2) == score_participation(s3)


def test_score_breadth_uses_canonical_types_only() -> None:
    """Unknown event types do not inflate breadth; they sit in weights=0
    territory and don't unlock new canonical buckets."""
    events = [
        _ev(1, 86400 * 0, "prayer"),
        _ev(1, 86400 * 1, "made-up-type"),
    ]
    s = _state(1, events, 0, 30 * 86400)
    _, breakdown = score_participation(s)
    # breadth = distinct_canonical_types / canonical_count  → 1 / 4 = 0.25
    assert breakdown["breadth"] == pytest.approx(0.25)


def test_score_consistency_quartile_coverage() -> None:
    """One event in each quartile of the window → consistency = 1.0."""
    window = 30 * 86400
    events = [
        _ev(1, 1 * 86400, "prayer"),               # Q1
        _ev(1, 9 * 86400, "study"),                # Q2
        _ev(1, 17 * 86400, "service"),             # Q3
        _ev(1, 25 * 86400, "donation"),            # Q4
    ]
    s = _state(1, events, 0, window)
    _, breakdown = score_participation(s)
    assert breakdown["consistency"] == pytest.approx(1.0)


def test_active_adherent_lands_in_band() -> None:
    """A realistic 30-day active adherent should produce a multiplier
    inside the constitutional band (never escape clamp)."""
    window = 30 * 86400
    # mixed-axis steady participation
    events: list[AttestationEvent] = []
    for day in range(0, 30, 2):
        events.append(_ev(1, day * 86400, "prayer"))
    for day in range(1, 30, 5):
        events.append(_ev(1, day * 86400, "study"))
    events.append(_ev(1, 27 * 86400, "service"))
    events.append(_ev(1, 14 * 86400, "donation"))

    s = _state(1, events, 0, window)
    score, _ = score_participation(s)
    bps = multiplier_from_score(score)
    assert PHENOTYPE_MIN_BPS_DEFAULT <= bps <= PHENOTYPE_MAX_BPS_DEFAULT


# ─── collapse_events: sort + dedupe ──────────────────────────────────


def test_collapse_events_dedupes_identical() -> None:
    e = _ev(1, 100, "prayer")
    out = collapse_events([e, e, e])
    assert len(out) == 1


def test_collapse_events_sorts_canonically() -> None:
    """Ordering is (token_id, attested_at, evidence_cid) ascending."""
    out = collapse_events([
        _ev(2, 100, "prayer"),
        _ev(1, 200, "prayer"),
        _ev(1, 100, "prayer"),
    ])
    assert [(e.token_id, e.attested_at) for e in out] == [(1, 100), (1, 200), (2, 100)]
