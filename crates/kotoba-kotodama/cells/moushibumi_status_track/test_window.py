"""Tests for the moushibumi participation-window pure computation core
(ADR-2605312400).

Locks the G5 invariant (never a legal opinion), the G9 invariant (never renders
advice / never campaigns), both input modes (open_date + window_days vs. explicit
close_date), the inclusive/exclusive calendar distinction, window boundaries
(exactly-on-close / day-after), and integration against the worldwide moushibumi
participation registry. Pure stdlib, deterministic, no network — runs in CI.

These do NOT import ``.cell`` (which is import-time RuntimeError until Council
ratification); the pure core lives in ``.window`` precisely so it is testable
without activating the gated Pregel wrapper.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from .window import (
    CALENDAR_EXCLUSIVE,
    CALENDAR_INCLUSIVE,
    WindowInput,
    compute_close,
    compute_window,
    to_window_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/moushibumi/registry/targets.seed.json"


# ── G5 / G9: never a legal opinion, never renders advice ────────────────


@pytest.mark.parametrize("counting", [CALENDAR_INCLUSIVE, CALENDAR_EXCLUSIVE])
def test_g5_g9_invariants_window_days(counting):
    s = compute_window(WindowInput(
        target_id="x", open_date=date(2026, 6, 1), as_of=date(2026, 6, 3),
        window_days=30, counting=counting,
    ))
    assert s.is_legal_opinion is False
    assert s.renders_advice is False


def test_g5_g9_invariants_close_date():
    s = compute_window(WindowInput(
        target_id="x", open_date=date(2026, 6, 1), as_of=date(2026, 6, 3),
        close_date=date(2026, 7, 1),
    ))
    assert s.is_legal_opinion is False
    assert s.renders_advice is False


@pytest.mark.parametrize("as_of_day", [1, 15, 30, 31, 100])
def test_g_invariants_can_never_be_true(as_of_day):
    # No as-of date, open/closed state, or input mode can flip the invariants.
    s = compute_window(WindowInput(
        target_id="x", open_date=date(2026, 6, 1), as_of=date(2026, 6, as_of_day if as_of_day <= 30 else 30),
        window_days=15,
    ))
    assert s.is_legal_opinion is False
    assert s.renders_advice is False
    rec = to_window_record(
        s, member_did="did:web:m.example", target_ref="at://x/y/z",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["rendersAdvice"] is False


def test_record_shape_and_iso():
    s = compute_window(WindowInput(
        target_id="eu-have-your-say-consultation", open_date=date(2026, 6, 1),
        as_of=date(2026, 6, 3), window_days=14, member_confirmed=True,
    ))
    rec = to_window_record(
        s, member_did="did:web:m.example", target_ref="at://x/y/z",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
        session_ref="sess-1", encrypted_detail_ref="at://enc/1",
    )
    assert rec["isLegalOpinion"] is False
    assert rec["rendersAdvice"] is False
    assert rec["isOpen"] is True
    assert rec["computedClose"] == "2026-06-14T00:00:00Z"  # inclusive: day 1 = 06-01
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["daysRemaining"] == 11
    assert rec["source"] == "window_days"
    assert rec["memberConfirmed"] is True
    assert rec["sessionRef"] == "sess-1"
    assert rec["encryptedDetailRef"] == "at://enc/1"


# ── window_days mode: inclusive vs exclusive calendar ───────────────────


def test_inclusive_open_day_is_day_one():
    # 30-day inclusive window opening Mon 2026-06-01 → close 2026-06-30
    assert compute_close(date(2026, 6, 1), 30, CALENDAR_INCLUSIVE) == date(2026, 6, 30)


def test_exclusive_clock_starts_next_day():
    # 30-day exclusive window opening 2026-06-01 → close 2026-07-01
    assert compute_close(date(2026, 6, 1), 30, CALENDAR_EXCLUSIVE) == date(2026, 7, 1)


def test_window_open_with_days_remaining():
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 6, 10),
        window_days=30, counting=CALENDAR_INCLUSIVE,
    ))
    assert s.computed_close == date(2026, 6, 30)
    assert s.is_open is True
    assert s.days_remaining == 20
    assert s.source == "window_days"


# ── boundary: exactly-on-close / day-after (overdue) ────────────────────


def test_boundary_last_day_is_open():
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 6, 30),
        window_days=30,
    ))
    assert s.is_open is True
    assert s.days_remaining == 0


def test_boundary_day_after_close_is_closed():
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 7, 1),
        window_days=30,
    ))
    assert s.is_open is False
    assert s.days_remaining == -1


def test_long_overdue_window():
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 1, 1), as_of=date(2026, 6, 1),
        window_days=14,
    ))
    assert s.is_open is False
    assert s.days_remaining < 0


# ── pre-open: as_of precedes open_date (regression — must NOT report open) ──


def test_pre_open_window_is_not_open():
    # as_of a full month BEFORE the window opens: must be not-yet-open, not open.
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 5, 1),
        window_days=30, counting=CALENDAR_INCLUSIVE,
    ))
    assert s.not_yet_open is True
    assert s.is_open is False  # regression: previously wrongly True
    assert "not yet open" in s.computation_note.lower()


def test_pre_open_close_date_mode_is_not_open():
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 5, 20),
        close_date=date(2026, 6, 30),
    ))
    assert s.not_yet_open is True
    assert s.is_open is False


def test_open_day_is_open_not_pre_open():
    # the exact open day is in-window (boundary of the pre-open fix)
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 6, 1),
        window_days=30,
    ))
    assert s.not_yet_open is False
    assert s.is_open is True


def test_pre_open_record_carries_not_yet_open():
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 5, 1),
        window_days=30,
    ))
    rec = to_window_record(
        s, member_did="did:web:m.example", target_ref="at://x/y/z",
        created_at=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
    )
    assert rec["isOpen"] is False
    assert rec["notYetOpen"] is True


# ── explicit close_date mode ────────────────────────────────────────────


def test_close_date_mode_open():
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 6, 20),
        close_date=date(2026, 6, 30),
    ))
    assert s.computed_close == date(2026, 6, 30)
    assert s.is_open is True
    assert s.days_remaining == 10
    assert s.source == "close_date"


def test_close_date_mode_boundary_and_closed():
    on = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 6, 30),
        close_date=date(2026, 6, 30),
    ))
    assert on.is_open is True and on.days_remaining == 0
    after = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 7, 1),
        close_date=date(2026, 6, 30),
    ))
    assert after.is_open is False and after.days_remaining == -1


# ── validation (G8 — verified, well-formed, unambiguous input only) ─────


def test_neither_window_input_raises():
    with pytest.raises(ValueError):
        compute_window(WindowInput(
            target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 6, 3),
        ))


def test_both_window_inputs_raise():
    with pytest.raises(ValueError):
        compute_window(WindowInput(
            target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 6, 3),
            window_days=14, close_date=date(2026, 6, 30),
        ))


@pytest.mark.parametrize("bad", [0, -1, -30])
def test_nonpositive_window_days_raises(bad):
    with pytest.raises(ValueError):
        compute_close(date(2026, 6, 1), bad, CALENDAR_INCLUSIVE)


def test_bool_window_days_rejected():
    # bool is an int subclass; must not be silently accepted as 1 day.
    with pytest.raises(ValueError):
        compute_close(date(2026, 6, 1), True, CALENDAR_INCLUSIVE)


def test_unknown_counting_raises():
    with pytest.raises(ValueError):
        compute_close(date(2026, 6, 1), 14, "lunar_calendar")


def test_close_before_open_raises():
    with pytest.raises(ValueError):
        compute_window(WindowInput(
            target_id="t", open_date=date(2026, 6, 30), as_of=date(2026, 6, 1),
            close_date=date(2026, 6, 1),
        ))


def test_note_flags_neutrality_and_not_legal_opinion():
    s = compute_window(WindowInput(
        target_id="t", open_date=date(2026, 6, 1), as_of=date(2026, 6, 3),
        window_days=14,
    ))
    note = s.computation_note.lower()
    assert "not a legal opinion" in note
    assert "get-out-the-vote" in note  # G9 political neutrality flagged


# ── integration: drive real registry targets through the core ───────────


def test_registry_targets_feed_the_core():
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    targets = data["targets"]
    assert len(targets) >= 20  # worldwide coverage, not JP-only
    # The registry deliberately holds NO numeric window field — windows are院/
    # jurisdiction-specific free text. The window length is therefore supplied as a
    # member-confirmed/verified INPUT (G8). Feed each real target's structural id +
    # a confirmed 30-day window into the core.
    checked = 0
    for t in targets:
        tid = t["targetId"]
        assert "windowDays" not in t and "closeDate" not in t  # G8: never pre-baked
        s = compute_window(WindowInput(
            target_id=tid, open_date=date(2026, 6, 1), as_of=date(2026, 6, 1),
            window_days=30, member_confirmed=True,
        ))
        assert s.target_id == tid
        assert s.is_open is True  # day 1 (inclusive) is within any positive window
        assert s.is_legal_opinion is False
        assert s.renders_advice is False
        checked += 1
    assert checked == len(targets)


def test_registry_public_comment_window_via_explicit_close():
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    pc = next(t for t in data["targets"] if t["channelKind"] == "public-comment")
    # Member confirms an explicit close date from the cited provenance.
    s = compute_window(WindowInput(
        target_id=pc["targetId"], open_date=date(2026, 6, 1),
        as_of=date(2026, 6, 15), close_date=date(2026, 6, 30), member_confirmed=True,
    ))
    assert s.source == "close_date"
    assert s.is_open is True
    assert s.days_remaining == 15
    assert s.is_legal_opinion is False
    assert s.renders_advice is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
