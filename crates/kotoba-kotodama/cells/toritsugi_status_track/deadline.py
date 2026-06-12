"""Pure statutory filing-deadline computation core for ``toritsugi_status_track``.

Per ADR-2605312030 (取次 toritsugi — citizen-facing government-procedure
concierge), §status_track filing-clock.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * G5 — this module performs INFORMATIONAL date arithmetic only (triggering-event
    date + statutory filing window 日数 → filing-due date + overdue?). It is NOT a
    legal opinion, advice, or 作成代理 (preparation-by-proxy):
    ``is_legal_opinion`` / ``isLegalOpinion`` is ALWAYS ``False`` and there is NO
    code path that can set it ``True``. Borderline / complex / time-critical /
    refusal cases route to chigiri + licensed counsel via ``computation_note``.
  * 行政書士法 / UPL boundary: information + wayfinding + form-fill assist ONLY; the
    member self-submits. This computes an INFORMATIONAL filing deadline so a member
    can decide for themselves — it does NOT advise, does NOT file, and does NOT
    prepare the application by proxy.
  * G8 — non-fabrication: a procedure's statutory filing window differs by
    procedure AND by counting convention (起算日 inclusive vs the day after;
    calendar vs business days). The window is an explicit INPUT (from a verified
    procedure entry or a member-confirmed fact) — it is NEVER hard-coded or guessed
    here. (Illustrative only, never baked in: JP 転入届 within 14 days of moving.)
    Business-day counting is Mon–Fri only and does NOT model public holidays — the
    note says so loudly so the result is treated as indicative.
  * No PII persistence, no network, no inference, no dispatch. Pure stdlib.

R0/R2 BOUNDARY (CRITICAL): this pure core is importable independently of the gated
Pregel wrapper. ``cell.py`` (``ToritsugiStatusTrackCell``) remains import-time
``RuntimeError`` until Council ratifies ADR-2605312030 (Lv6+ ≥4 + 30-day public
comment, status_track ships with R2) AND the G6 encrypted-envelope backend is live.
Landing + testing this core does NOT activate the cell; once Council activates,
``super_step`` will call :func:`compute_deadline_status` and
:func:`to_status_record`.

Output shape mirrors Lexicon ``com.etzhayyim.toritsugi.statusTrack``
(the filing-clock subset).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# ── counting conventions ────────────────────────────────────────────────
CALENDAR_INCLUSIVE = "calendar_inclusive"  # 起算日を1日目に算入
CALENDAR_EXCLUSIVE = "calendar_exclusive"  # clock starts the day AFTER the event
BUSINESS_INCLUSIVE = "business_inclusive"  # Mon–Fri; the event day counts as day 1
BUSINESS_EXCLUSIVE = "business_exclusive"  # Mon–Fri; clock starts the next business day

_COUNTING = frozenset(
    {CALENDAR_INCLUSIVE, CALENDAR_EXCLUSIVE, BUSINESS_INCLUSIVE, BUSINESS_EXCLUSIVE}
)
_BUSINESS = frozenset({BUSINESS_INCLUSIVE, BUSINESS_EXCLUSIVE})


@dataclass(frozen=True)
class FilingDeadlineInput:
    """Member-confirmed facts + the verified procedure's statutory filing window.

    ``filing_window_days`` is an INPUT (from a verified procedure entry or a
    member-confirmed fact). It is never invented by this module (G8).
    """

    procedure_id: str
    filing_window_days: int  # from a verified procedure entry / member-confirmed (G8)
    event_date: date  # the triggering event (e.g. move-in / birth date) — 起算日 source
    as_of: date  # the date the status is computed for ("today")
    counting: str = CALENDAR_INCLUSIVE
    member_confirmed: bool = False  # G8 — member confirmed the input facts


@dataclass(frozen=True)
class FilingDeadlineStatus:
    procedure_id: str
    is_legal_opinion: bool  # ALWAYS False (G5)
    filing_due_date: date
    overdue: bool
    days_remaining: int  # calendar days to the due date; negative if overdue
    counting: str
    member_confirmed: bool
    computation_note: str


def _add_business_days(start: date, n: int, inclusive: bool) -> date:
    """Date on which the ``n``-th business day (Mon–Fri) falls. Holidays NOT modeled."""
    count = 0
    d = start
    if inclusive and d.weekday() < 5:
        count = 1
        if count >= n:
            return d
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d


def compute_filing_due_date(event_date: date, window_days: int, counting: str) -> date:
    """Last day on which the filing may still be made on time, per ``counting``."""
    if not isinstance(event_date, date):
        raise ValueError("event_date must be a datetime.date")
    if not isinstance(window_days, int) or isinstance(window_days, bool) or window_days <= 0:
        raise ValueError("filing_window_days must be a positive integer")
    if counting not in _COUNTING:
        raise ValueError(f"unknown counting convention: {counting!r}")

    if counting == CALENDAR_INCLUSIVE:
        return event_date + timedelta(days=window_days - 1)
    if counting == CALENDAR_EXCLUSIVE:
        return event_date + timedelta(days=window_days)
    return _add_business_days(
        event_date, window_days, inclusive=(counting == BUSINESS_INCLUSIVE)
    )


def _note(window_days: int, counting: str, due: date, overdue: bool) -> str:
    human = {
        CALENDAR_INCLUSIVE: "calendar days, counting the triggering-event day as day 1",
        CALENDAR_EXCLUSIVE: "calendar days, clock starting the day after the triggering event",
        BUSINESS_INCLUSIVE: "business days (Mon–Fri), counting the event day if it is a business day",
        BUSINESS_EXCLUSIVE: "business days (Mon–Fri), clock starting the next business day",
    }[counting]
    parts = [
        f"Computed filing-due date {due.isoformat()} = {window_days} {human}.",
        "INFORMATIONAL date computation per ADR-2605312030 G5 — NOT a legal opinion, "
        "NOT advice, NOT 作成代理. 行政書士法 / UPL boundary: information + wayfinding + "
        "form-fill assist only; the member self-submits.",
    ]
    if overdue:
        parts.append(
            "The window appears to have closed as of the computed date — late filing "
            "rules / exceptions vary; route to chigiri + licensed counsel."
        )
    if counting in _BUSINESS:
        parts.append(
            "Business-day counting is Mon–Fri only and does NOT account for public "
            "holidays; treat the deadline as indicative."
        )
    parts.append(
        "起算日 assumptions and statutory exceptions vary by procedure — verify the "
        "filing window against the cited legal basis and route borderline / complex / "
        "time-critical cases to chigiri + licensed counsel. The member must confirm "
        "the input facts."
    )
    return " ".join(parts)


def compute_deadline_status(inp: FilingDeadlineInput) -> FilingDeadlineStatus:
    """Pure status. ``is_legal_opinion`` is hard-wired ``False`` (G5)."""
    due = compute_filing_due_date(inp.event_date, inp.filing_window_days, inp.counting)
    overdue = inp.as_of > due
    return FilingDeadlineStatus(
        procedure_id=inp.procedure_id,
        is_legal_opinion=False,  # G5 — no path may set this True
        filing_due_date=due,
        overdue=overdue,
        days_remaining=(due - inp.as_of).days,
        counting=inp.counting,
        member_confirmed=inp.member_confirmed,
        computation_note=_note(inp.filing_window_days, inp.counting, due, overdue),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_status_record(
    s: FilingDeadlineStatus,
    *,
    member_did: str,
    procedure_ref: str,
    created_at: datetime,
    session_ref: str | None = None,
    encrypted_result_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.toritsugi.statusTrack``-shaped record (filing-clock subset).

    ``isLegalOpinion`` is asserted ``False`` before return — a G5 schema invariant
    that this function structurally cannot violate.
    """
    rec: dict = {
        "memberDid": member_did,
        "procedureRef": procedure_ref,
        "isLegalOpinion": False,  # G5
        "filingDueDate": _iso_dt(
            datetime.combine(s.filing_due_date, datetime.min.time())
        ),
        "overdue": s.overdue,
        "computationNote": s.computation_note[:1000],
        "memberConfirmed": s.member_confirmed,
        "createdAt": _iso_dt(created_at),
    }
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    if encrypted_result_ref is not None:
        rec["encryptedResultRef"] = encrypted_result_ref
    assert rec["isLegalOpinion"] is False, "G5 invariant: isLegalOpinion must be False"
    return rec


__all__ = [
    "CALENDAR_INCLUSIVE",
    "CALENDAR_EXCLUSIVE",
    "BUSINESS_INCLUSIVE",
    "BUSINESS_EXCLUSIVE",
    "FilingDeadlineInput",
    "FilingDeadlineStatus",
    "compute_filing_due_date",
    "compute_deadline_status",
    "to_status_record",
]
