"""Tests for the toritsugi statutory filing-deadline pure core (ADR-2605312030).

Locks the G5 invariant (never a legal opinion / never advice / never 作成代理), the
counting conventions (inclusive-calendar / exclusive-calendar / business-day),
window boundaries (exactly-on-deadline / overdue), and integration against the
worldwide government-procedure registry. Pure stdlib, deterministic, no network —
runs in CI.

These do NOT import ``.cell`` (which is import-time RuntimeError until Council
ratification); the pure core lives in ``.deadline`` precisely so it is testable
without activating the gated Pregel wrapper.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from .deadline import (
    BUSINESS_EXCLUSIVE,
    BUSINESS_INCLUSIVE,
    CALENDAR_EXCLUSIVE,
    CALENDAR_INCLUSIVE,
    FilingDeadlineInput,
    compute_deadline_status,
    compute_filing_due_date,
    to_status_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/toritsugi/registry/procedures.seed.json"


# ── G5: never a legal opinion (no code path can set it True) ─────────────


@pytest.mark.parametrize("counting", [
    CALENDAR_INCLUSIVE, CALENDAR_EXCLUSIVE, BUSINESS_INCLUSIVE, BUSINESS_EXCLUSIVE,
])
def test_g5_is_never_a_legal_opinion(counting):
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="x", filing_window_days=14,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 3), counting=counting,
    ))
    assert s.is_legal_opinion is False


@pytest.mark.parametrize("window_days", [1, 7, 14, 30, 60, 365])
def test_g5_invariant_across_windows(window_days):
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="x", filing_window_days=window_days,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 1),
    ))
    assert s.is_legal_opinion is False


def test_g5_record_isLegalOpinion_always_false():
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="jp-tennyu-todoke", filing_window_days=14,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 3),
    ))
    rec = to_status_record(
        s, member_did="did:web:member.example", procedure_ref="at://x/y/z",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["overdue"] is False
    # 起算 2026-06-01 (day 1) + 14 calendar-inclusive → 2026-06-14
    assert rec["filingDueDate"] == "2026-06-14T00:00:00Z"
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"


def test_g5_record_carries_optional_refs():
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="p", filing_window_days=14,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 3),
    ))
    rec = to_status_record(
        s, member_did="did:web:m", procedure_ref="at://x/y/z",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        session_ref="sess-1", encrypted_result_ref="at://enc/r",
    )
    assert rec["sessionRef"] == "sess-1"
    assert rec["encryptedResultRef"] == "at://enc/r"
    assert rec["isLegalOpinion"] is False


# ── inclusive calendar: window day counted as day 1 (illustrative: 転入届 14d) ──


def test_inclusive_14day_within():
    # 起算 Mon 2026-06-01 (day 1) → due 2026-06-14; today 2026-06-05
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="jp-tennyu-todoke", filing_window_days=14,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 5),
        counting=CALENDAR_INCLUSIVE,
    ))
    assert s.filing_due_date == date(2026, 6, 14)
    assert s.overdue is False
    assert s.days_remaining == 9


def test_boundary_exactly_on_deadline_is_not_overdue():
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="jp-tennyu-todoke", filing_window_days=14,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 14),
    ))
    assert s.overdue is False
    assert s.days_remaining == 0


def test_overdue_day_after_deadline():
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="jp-tennyu-todoke", filing_window_days=14,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 15),
    ))
    assert s.overdue is True
    assert s.days_remaining == -1
    assert "window appears to have closed" in s.computation_note.lower()


def test_window_edge_one_day_window_inclusive():
    # a 1-day inclusive window: due = the event day itself
    assert compute_filing_due_date(date(2026, 6, 1), 1, CALENDAR_INCLUSIVE) == date(2026, 6, 1)


# ── exclusive calendar: clock starts the day after the event ─────────────


def test_exclusive_calendar_clock_starts_next_day():
    # event 2026-06-01, +14 exclusive → due 2026-06-15
    assert compute_filing_due_date(date(2026, 6, 1), 14, CALENDAR_EXCLUSIVE) == date(2026, 6, 15)
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="p", filing_window_days=14,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 15),
        counting=CALENDAR_EXCLUSIVE,
    ))
    assert s.overdue is False
    s2 = compute_deadline_status(FilingDeadlineInput(
        procedure_id="p", filing_window_days=14,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 16),
        counting=CALENDAR_EXCLUSIVE,
    ))
    assert s2.overdue is True


# ── business-day counting (Mon–Fri; holidays not modeled) ────────────────


def test_business_days_inclusive():
    # Mon 06-01 counts as day 1 → Mon(1) Tue(2) Wed(3) → due Wed 2026-06-03
    assert compute_filing_due_date(date(2026, 6, 1), 3, BUSINESS_INCLUSIVE) == date(2026, 6, 3)


def test_business_days_exclusive():
    # clock starts Tue → Tue(1) Wed(2) Thu(3) → due Thu 2026-06-04
    assert compute_filing_due_date(date(2026, 6, 1), 3, BUSINESS_EXCLUSIVE) == date(2026, 6, 4)


def test_business_days_skip_weekend():
    # Fri 06-05 inclusive, 3 business days → Fri(1) Mon(2) Tue(3) → Tue 2026-06-09
    assert compute_filing_due_date(date(2026, 6, 5), 3, BUSINESS_INCLUSIVE) == date(2026, 6, 9)


def test_business_note_flags_holidays_not_modeled():
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id="p", filing_window_days=3,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 2),
        counting=BUSINESS_INCLUSIVE,
    ))
    assert "holidays" in s.computation_note.lower()
    assert "not a legal opinion" in s.computation_note.lower()
    assert "self-submit" in s.computation_note.lower()


# ── validation (G8 — verified, well-formed input only; never guess) ──────


@pytest.mark.parametrize("bad", [0, -1, -14])
def test_nonpositive_window_raises(bad):
    with pytest.raises(ValueError):
        compute_filing_due_date(date(2026, 6, 1), bad, CALENDAR_INCLUSIVE)


def test_non_int_window_raises():
    with pytest.raises(ValueError):
        compute_filing_due_date(date(2026, 6, 1), 14.0, CALENDAR_INCLUSIVE)  # type: ignore[arg-type]


def test_bool_window_rejected():
    # bool is an int subclass; True must not be silently accepted as a 1-day window.
    with pytest.raises(ValueError):
        compute_filing_due_date(date(2026, 6, 1), True, CALENDAR_INCLUSIVE)  # type: ignore[arg-type]


def test_unknown_counting_raises():
    with pytest.raises(ValueError):
        compute_filing_due_date(date(2026, 6, 1), 14, "lunar_calendar")


def test_non_date_event_raises():
    with pytest.raises(ValueError):
        compute_filing_due_date("2026-06-01", 14, CALENDAR_INCLUSIVE)  # type: ignore[arg-type]


# ── integration: drive REAL registry values through the core ─────────────


def test_registry_loads_and_has_procedures():
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    assert data["$schema"] == "com.etzhayyim.toritsugi.procedure"
    assert isinstance(data["procedures"], list) and len(data["procedures"]) > 0


def test_registry_procedures_feed_the_core_with_member_confirmed_window():
    # IMPORTANT (concept hygiene, G8): the registry's `statutoryProcessingDays` is the
    # AUTHORITY's issuance/processing time, NOT the member's FILING window — they are
    # distinct legal quantities. The member's filing window (e.g. JP 転入届 within 14
    # days) is supplied as a verified/member-confirmed INPUT, structurally keyed to a
    # real procedureId. We assert here that we do NOT misuse statutoryProcessingDays
    # as a filing window.
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    procedures = data["procedures"]
    assert len(procedures) >= 3  # worldwide coverage, not a single-procedure fixture
    MEMBER_CONFIRMED_WINDOW = 14  # illustrative INPUT, NOT read from the registry
    checked = 0
    for p in procedures[:10]:
        s = compute_deadline_status(FilingDeadlineInput(
            procedure_id=p["procedureId"], filing_window_days=MEMBER_CONFIRMED_WINDOW,
            event_date=date(2026, 6, 1), as_of=date(2026, 6, 1),
        ))
        # day 1 (calendar-inclusive) is always on time for any positive window
        assert s.overdue is False
        assert s.is_legal_opinion is False
        assert s.filing_due_date >= date(2026, 6, 1)
        checked += 1
    assert checked >= 3


def test_registry_entry_drives_full_record():
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    entry = data["procedures"][0]
    days = 14  # member-confirmed filing window INPUT, not the registry's processing time
    s = compute_deadline_status(FilingDeadlineInput(
        procedure_id=entry["procedureId"], filing_window_days=days,
        event_date=date(2026, 6, 1), as_of=date(2026, 6, 1),
        member_confirmed=True,
    ))
    rec = to_status_record(
        s, member_did="did:web:member.example",
        procedure_ref=f"at://registry/{entry['procedureId']}",
        created_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["memberConfirmed"] is True
    assert rec["procedureRef"].endswith(entry["procedureId"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
