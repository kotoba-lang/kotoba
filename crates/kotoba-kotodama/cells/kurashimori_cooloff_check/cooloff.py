"""Pure cooling-off window computation core for ``kurashimori_cooloff_check``.

Per ADR-2605312500 (暮らし守 kurashimori — citizen consumer-protection concierge),
§3 cooling-off assessment.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * G5 — this module performs INFORMATIONAL date arithmetic only (window-start +
    日数 → deadline). It is NOT a legal opinion or rights-determination:
    ``is_legal_opinion`` / ``isLegalOpinion`` is ALWAYS ``False`` and there is no
    code path that can set it ``True``. Borderline / complex cases route to chigiri
    + licensed counsel via ``computation_note``.
  * G8 — non-fabrication: cooling-off windows differ by transaction type AND by
    counting convention (起算日 inclusive vs the day after; calendar vs business
    days). The convention is an explicit input, never guessed. Business-day
    counting is Mon–Fri only and does NOT model public holidays — the note says so
    loudly so the result is treated as indicative.
  * No PII persistence, no network, no inference, no dispatch. Pure stdlib.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the gated
Pregel wrapper. ``cell.py`` (``KurashimoriCooloffCheckCell``) remains import-time
``RuntimeError`` until Council ratifies ADR-2605312500 (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19). Landing + testing this core does NOT activate the cell;
once Council activates, ``super_step`` will call :func:`compute_assessment` and
:func:`to_assessment_record`.

Output shape mirrors Lexicon ``com.etzhayyim.kurashimori.coolingOffAssessment``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# ── counting conventions ────────────────────────────────────────────────
CALENDAR_INCLUSIVE = "calendar_inclusive"  # 起算日を1日目に算入 (JP 特商法 §9/§40)
CALENDAR_EXCLUSIVE = "calendar_exclusive"  # clock starts the day AFTER (EU CRD / DE BGB Widerruf)
BUSINESS_INCLUSIVE = "business_inclusive"  # Mon–Fri; start day counts (US FTC 3 business days)
BUSINESS_EXCLUSIVE = "business_exclusive"  # Mon–Fri; clock starts the next business day

_COUNTING = frozenset(
    {CALENDAR_INCLUSIVE, CALENDAR_EXCLUSIVE, BUSINESS_INCLUSIVE, BUSINESS_EXCLUSIVE}
)
_BUSINESS = frozenset({BUSINESS_INCLUSIVE, BUSINESS_EXCLUSIVE})


@dataclass(frozen=True)
class CooloffInput:
    """Member-confirmed facts + the verified remedyTarget's statutory window."""

    remedy_id: str
    statutory_window_days: int  # from the verified remedyTarget (G8 — verified-only)
    window_start: date  # 起算日 — the member-confirmed start date
    as_of: date  # the date the assessment is computed for ("today")
    counting: str = CALENDAR_INCLUSIVE
    member_confirmed: bool = False  # G8 — member confirmed the input facts


@dataclass(frozen=True)
class CooloffAssessment:
    remedy_id: str
    is_legal_opinion: bool  # ALWAYS False (G5)
    within_window: bool
    computed_deadline: date
    days_remaining: int  # calendar days to deadline; negative if expired
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


def compute_deadline(window_start: date, window_days: int, counting: str) -> date:
    """Last day on which the right may still be exercised, per ``counting``."""
    if not isinstance(window_start, date):
        raise ValueError("window_start must be a datetime.date")
    if not isinstance(window_days, int) or window_days <= 0:
        raise ValueError("statutory_window_days must be a positive integer")
    if counting not in _COUNTING:
        raise ValueError(f"unknown counting convention: {counting!r}")

    if counting == CALENDAR_INCLUSIVE:
        return window_start + timedelta(days=window_days - 1)
    if counting == CALENDAR_EXCLUSIVE:
        return window_start + timedelta(days=window_days)
    return _add_business_days(
        window_start, window_days, inclusive=(counting == BUSINESS_INCLUSIVE)
    )


def _note(window_days: int, counting: str, deadline: date, within: bool) -> str:
    human = {
        CALENDAR_INCLUSIVE: "calendar days, counting the start day as day 1 (JP 特商法 convention)",
        CALENDAR_EXCLUSIVE: "calendar days, clock starting the day after the start date (EU CRD / DE Widerruf convention)",
        BUSINESS_INCLUSIVE: "business days (Mon–Fri), counting the start day if it is a business day",
        BUSINESS_EXCLUSIVE: "business days (Mon–Fri), clock starting the next business day",
    }[counting]
    parts = [
        f"Computed deadline {deadline.isoformat()} = {window_days} {human}.",
        "INFORMATIONAL date computation per ADR-2605312500 G5 — NOT a legal opinion "
        "or rights-determination.",
    ]
    if counting in _BUSINESS:
        parts.append(
            "Business-day counting is Mon–Fri only and does NOT account for public "
            "holidays; treat the deadline as indicative."
        )
    parts.append(
        "起算日 assumptions and statutory exclusions vary — verify against the cited "
        "statute and route borderline / complex / time-critical cases to chigiri + "
        "licensed counsel. The member must confirm the input facts."
    )
    return " ".join(parts)


def compute_assessment(inp: CooloffInput) -> CooloffAssessment:
    """Pure assessment. ``is_legal_opinion`` is hard-wired ``False`` (G5)."""
    deadline = compute_deadline(inp.window_start, inp.statutory_window_days, inp.counting)
    within = inp.as_of <= deadline
    return CooloffAssessment(
        remedy_id=inp.remedy_id,
        is_legal_opinion=False,  # G5 — no path may set this True
        within_window=within,
        computed_deadline=deadline,
        days_remaining=(deadline - inp.as_of).days,
        counting=inp.counting,
        member_confirmed=inp.member_confirmed,
        computation_note=_note(inp.statutory_window_days, inp.counting, deadline, within),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_assessment_record(
    a: CooloffAssessment,
    *,
    member_did: str,
    remedy_ref: str,
    created_at: datetime,
    session_ref: str | None = None,
    encrypted_contract_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.kurashimori.coolingOffAssessment``-shaped record.

    ``isLegalOpinion`` is asserted ``False`` before return — a G5 schema invariant
    that this function structurally cannot violate.
    """
    rec: dict = {
        "memberDid": member_did,
        "remedyRef": remedy_ref,
        "isLegalOpinion": False,  # G5
        "withinWindow": a.within_window,
        "computedDeadline": _iso_dt(
            datetime.combine(a.computed_deadline, datetime.min.time())
        ),
        "computationNote": a.computation_note[:1000],
        "memberConfirmed": a.member_confirmed,
        "createdAt": _iso_dt(created_at),
    }
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    if encrypted_contract_ref is not None:
        rec["encryptedContractRef"] = encrypted_contract_ref
    assert rec["isLegalOpinion"] is False, "G5 invariant: isLegalOpinion must be False"
    return rec


__all__ = [
    "CALENDAR_INCLUSIVE",
    "CALENDAR_EXCLUSIVE",
    "BUSINESS_INCLUSIVE",
    "BUSINESS_EXCLUSIVE",
    "CooloffInput",
    "CooloffAssessment",
    "compute_deadline",
    "compute_assessment",
    "to_assessment_record",
]
