"""Tests for the kurashimori cooling-off pure computation core (ADR-2605312500 §3).

Locks the G5 invariant (never a legal opinion), the per-jurisdiction counting
conventions (JP inclusive-calendar / EU exclusive-calendar / US FTC business-day),
window boundaries, and integration against the worldwide remedy registry. Pure
stdlib, deterministic, no network — runs in CI.

These do NOT import ``.cell`` (which is import-time RuntimeError until Council
ratification); the pure core lives in ``.cooloff`` precisely so it is testable
without activating the gated Pregel wrapper.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from .cooloff import (
    BUSINESS_EXCLUSIVE,
    BUSINESS_INCLUSIVE,
    CALENDAR_EXCLUSIVE,
    CALENDAR_INCLUSIVE,
    CooloffInput,
    compute_assessment,
    compute_deadline,
    to_assessment_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/kurashimori/registry/targets.seed.json"


# ── G5: never a legal opinion ───────────────────────────────────────────


@pytest.mark.parametrize("counting", [
    CALENDAR_INCLUSIVE, CALENDAR_EXCLUSIVE, BUSINESS_INCLUSIVE, BUSINESS_EXCLUSIVE,
])
def test_g5_is_never_a_legal_opinion(counting):
    a = compute_assessment(CooloffInput(
        remedy_id="x", statutory_window_days=8,
        window_start=date(2026, 6, 1), as_of=date(2026, 6, 3), counting=counting,
    ))
    assert a.is_legal_opinion is False


def test_g5_record_isLegalOpinion_always_false():
    a = compute_assessment(CooloffInput(
        remedy_id="jp-houmon-cooloff", statutory_window_days=8,
        window_start=date(2026, 6, 1), as_of=date(2026, 6, 3),
    ))
    rec = to_assessment_record(
        a, member_did="did:web:member.example", remedy_ref="at://x/y/z",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["withinWindow"] is True
    assert rec["computedDeadline"] == "2026-06-08T00:00:00Z"
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"


# ── JP 特商法: 8-day calendar, start day = day 1 ─────────────────────────


def test_jp_houmon_8day_inclusive_within():
    # 起算 Mon 2026-06-01 (day 1) → deadline 2026-06-08; today Fri 2026-06-05
    a = compute_assessment(CooloffInput(
        remedy_id="jp-houmon-cooloff", statutory_window_days=8,
        window_start=date(2026, 6, 1), as_of=date(2026, 6, 5),
        counting=CALENDAR_INCLUSIVE,
    ))
    assert a.computed_deadline == date(2026, 6, 8)
    assert a.within_window is True
    assert a.days_remaining == 3


def test_jp_boundary_last_day_is_within():
    a = compute_assessment(CooloffInput(
        remedy_id="jp-houmon-cooloff", statutory_window_days=8,
        window_start=date(2026, 6, 1), as_of=date(2026, 6, 8),
    ))
    assert a.within_window is True
    assert a.days_remaining == 0


def test_jp_expired_day_after_deadline():
    a = compute_assessment(CooloffInput(
        remedy_id="jp-houmon-cooloff", statutory_window_days=8,
        window_start=date(2026, 6, 1), as_of=date(2026, 6, 9),
    ))
    assert a.within_window is False
    assert a.days_remaining == -1


# ── EU CRD / DE Widerruf: 14-day calendar, clock starts next day ─────────


def test_eu_crd_14day_exclusive():
    a = compute_assessment(CooloffInput(
        remedy_id="eu-crd-right-of-withdrawal-14day", statutory_window_days=14,
        window_start=date(2026, 6, 1), as_of=date(2026, 6, 15),
        counting=CALENDAR_EXCLUSIVE,
    ))
    assert a.computed_deadline == date(2026, 6, 15)
    assert a.within_window is True
    a2 = compute_assessment(CooloffInput(
        remedy_id="eu-crd-right-of-withdrawal-14day", statutory_window_days=14,
        window_start=date(2026, 6, 1), as_of=date(2026, 6, 16),
        counting=CALENDAR_EXCLUSIVE,
    ))
    assert a2.within_window is False


# ── US FTC: 3 business days (Mon–Fri) ───────────────────────────────────


def test_us_ftc_3_business_days_inclusive():
    # Mon 06-01 counts as day 1 → Mon(1) Tue(2) Wed(3) → deadline Wed 2026-06-03
    assert compute_deadline(date(2026, 6, 1), 3, BUSINESS_INCLUSIVE) == date(2026, 6, 3)


def test_us_ftc_3_business_days_exclusive():
    # clock starts Tue → Tue(1) Wed(2) Thu(3) → deadline Thu 2026-06-04
    assert compute_deadline(date(2026, 6, 1), 3, BUSINESS_EXCLUSIVE) == date(2026, 6, 4)


def test_business_day_skips_weekend():
    # Fri 06-05 inclusive, 3 business days → Fri(1) Mon(2) Tue(3) → Tue 2026-06-09
    assert compute_deadline(date(2026, 6, 5), 3, BUSINESS_INCLUSIVE) == date(2026, 6, 9)


def test_business_note_flags_holidays_not_modeled():
    a = compute_assessment(CooloffInput(
        remedy_id="us-ftc-cooling-off-rule", statutory_window_days=3,
        window_start=date(2026, 6, 1), as_of=date(2026, 6, 2),
        counting=BUSINESS_INCLUSIVE,
    ))
    assert "holidays" in a.computation_note.lower()
    assert "not a legal opinion" in a.computation_note.lower()


# ── validation (G8 — verified, well-formed input only) ──────────────────


@pytest.mark.parametrize("bad", [0, -1])
def test_nonpositive_window_raises(bad):
    with pytest.raises(ValueError):
        compute_deadline(date(2026, 6, 1), bad, CALENDAR_INCLUSIVE)


def test_unknown_counting_raises():
    with pytest.raises(ValueError):
        compute_deadline(date(2026, 6, 1), 8, "lunar_calendar")


# ── integration: drive the worldwide registry's verified windows ────────


def test_registry_cooloff_entries_feed_the_core():
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    cooloff = [t for t in data["targets"] if t.get("remedyKind") == "cooling-off"]
    assert len(cooloff) >= 5  # worldwide coverage, not JP-only
    for t in cooloff:
        days = t.get("statutoryWindowDays")
        assert isinstance(days, int) and days > 0, f"{t['remedyId']} bad window"
        a = compute_assessment(CooloffInput(
            remedy_id=t["remedyId"], statutory_window_days=days,
            window_start=date(2026, 6, 1), as_of=date(2026, 6, 1),
        ))
        # day 1 (calendar-inclusive) is always within any positive window
        assert a.within_window is True
        assert a.is_legal_opinion is False


def test_registry_jp_houmon_is_8_days():
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    entry = next(t for t in data["targets"] if t["remedyId"] == "jp-houmon-cooloff")
    assert entry["statutoryWindowDays"] == 8


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
