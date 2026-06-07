"""Pure participation-window computation core for ``moushibumi_status_track``.

Per ADR-2605312400 (申文 moushibumi — citizen democratic-participation concierge),
participation-window status: given a consultation / petition / public-comment open
date + a window length (or an explicit close date), compute whether the window is
still open as-of a given date and how many calendar days remain.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * G9 / 公選法-equivalent political neutrality — this module computes INFORMATION
    only: it tells a member whether a participation window is open and how long is
    left. It performs NO campaigning, endorsement, candidate-preference, or
    get-out-the-vote (GOTV) action, and emits no such signal. ``renders_advice`` is
    ALWAYS ``False`` and there is no code path that can set it ``True``.
  * G5-equivalent — this is INFORMATIONAL date arithmetic, explicitly NOT legal
    advice or a rights-determination: ``is_legal_opinion`` / ``isLegalOpinion`` is
    ALWAYS ``False`` and there is no code path that can set it ``True``. Borderline /
    complex cases route to chigiri + licensed counsel via ``computation_note``.
  * G8 — non-fabrication: the window length / close date is NEVER invented. It is an
    explicit INPUT supplied from a verified registry entry or a member-confirmed
    fact. Many real participation windows (e.g. 国会会期中, 院ごとに異なる締切) are
    free-text and院-specific; this core refuses to guess and the note says so.
  * No PII persistence, no network, no inference, no dispatch. Pure stdlib.

R0/R2 BOUNDARY (CRITICAL): this pure core is importable independently of the gated
Pregel wrapper. ``cell.py`` (``MoushibumiStatusTrackCell``) remains import-time
``RuntimeError`` until Council ratifies ADR-2605312400 (Lv6+ ≥4 + public comment,
R2). Landing + testing this core does NOT activate the cell; once Council activates,
``super_step`` will call :func:`compute_window` and :func:`to_window_record`.

Output shape mirrors Lexicon ``com.etzhayyim.moushibumi.statusTrack``
(participation-window facet).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# ── counting conventions (close-date computed from open + window_days) ───
# Reused from the kurashimori cooloff calendar distinction: whether the open
# (起算) day is counted as day 1 (inclusive) or the clock starts the day after
# (exclusive). For participation windows the convention is an explicit input.
CALENDAR_INCLUSIVE = "calendar_inclusive"  # open day counts as day 1
CALENDAR_EXCLUSIVE = "calendar_exclusive"  # clock starts the day AFTER the open date

_COUNTING = frozenset({CALENDAR_INCLUSIVE, CALENDAR_EXCLUSIVE})


@dataclass(frozen=True)
class WindowInput:
    """Member-confirmed / verified-registry facts for ONE participation window.

    Exactly ONE of ``window_days`` or ``close_date`` must be supplied (both modes
    are first-class):
      * ``window_days`` (+ ``open_date`` + ``counting``) → close date is computed.
      * ``close_date``  (explicit) → ``window_days`` / ``counting`` ignored for the
        close-date computation.

    The window length / close date is ALWAYS verified-or-member-confirmed input
    (G8), never invented from the registry's free-text ``deadline``.
    """

    target_id: str
    open_date: date  # consultation / petition open date (起算)
    as_of: date  # the date the window status is computed for ("today")
    window_days: int | None = None  # window length in days (verified/confirmed)
    close_date: date | None = None  # explicit close date (verified/confirmed)
    counting: str = CALENDAR_INCLUSIVE
    member_confirmed: bool = False  # G8 — member confirmed the input facts


@dataclass(frozen=True)
class WindowStatus:
    target_id: str
    is_legal_opinion: bool  # ALWAYS False (G5-equivalent)
    renders_advice: bool  # ALWAYS False (G9 political neutrality)
    is_open: bool  # True ONLY when open_date <= as_of <= computed_close
    not_yet_open: bool  # True when as_of precedes open_date (window has not started)
    computed_close: date
    days_remaining: int  # calendar days to close; negative if the window has closed
    source: str  # "window_days" | "close_date" — which input mode produced the close
    member_confirmed: bool
    computation_note: str


def compute_close(
    open_date: date,
    window_days: int,
    counting: str,
) -> date:
    """Last day on which the window is still open, from ``open_date`` + ``window_days``."""
    if not isinstance(open_date, date):
        raise ValueError("open_date must be a datetime.date")
    if not isinstance(window_days, int) or isinstance(window_days, bool) or window_days <= 0:
        raise ValueError("window_days must be a positive integer")
    if counting not in _COUNTING:
        raise ValueError(f"unknown counting convention: {counting!r}")
    if counting == CALENDAR_INCLUSIVE:
        return open_date + timedelta(days=window_days - 1)
    return open_date + timedelta(days=window_days)


def _resolve_close(inp: WindowInput) -> tuple[date, str]:
    """Resolve the effective close date + which input mode produced it (G8).

    Exactly one of ``window_days`` / ``close_date`` must be supplied; raise
    ValueError rather than guessing if neither, both, or a malformed value is given.
    """
    if not isinstance(inp.open_date, date):
        raise ValueError("open_date must be a datetime.date")
    if not isinstance(inp.as_of, date):
        raise ValueError("as_of must be a datetime.date")

    has_days = inp.window_days is not None
    has_close = inp.close_date is not None
    if has_days and has_close:
        raise ValueError(
            "supply exactly one of window_days / close_date, not both (G8 — the "
            "window length is a single verified fact)"
        )
    if not has_days and not has_close:
        raise ValueError(
            "supply exactly one of window_days / close_date — the window length is "
            "an INPUT from a verified registry entry or member-confirmed fact, never "
            "guessed (G8)"
        )

    if has_close:
        if not isinstance(inp.close_date, date):
            raise ValueError("close_date must be a datetime.date")
        if inp.close_date < inp.open_date:
            raise ValueError("close_date must not precede open_date")
        return inp.close_date, "close_date"

    close = compute_close(inp.open_date, inp.window_days, inp.counting)  # type: ignore[arg-type]
    return close, "window_days"


def _note(source: str, close: date, counting: str, is_open: bool, not_yet_open: bool) -> str:
    if source == "close_date":
        head = f"Window closes {close.isoformat()} (explicit close date supplied)."
    else:
        human = {
            CALENDAR_INCLUSIVE: "counting the open date as day 1",
            CALENDAR_EXCLUSIVE: "clock starting the day after the open date",
        }[counting]
        head = (
            f"Window closes {close.isoformat()}, computed from the open date + a "
            f"supplied window length, {human}."
        )
    state = "not yet open" if not_yet_open else ("open" if is_open else "closed")
    parts = [
        head,
        f"As-of the queried date the window is {state}.",
        "INFORMATIONAL participation-window computation per ADR-2605312400 — NOT a "
        "legal opinion or rights-determination, and NOT campaigning, endorsement, or "
        "get-out-the-vote (G9 political-neutrality / 公選法-equivalent: info only).",
        "The window length / close date is verified-or-member-confirmed input, never "
        "inferred from free-text registry deadlines (国会会期中 / 院ごとに異なる締切 "
        "vary); confirm against the cited provenance and route borderline / "
        "time-critical cases to chigiri + licensed counsel.",
    ]
    return " ".join(parts)


def compute_window(inp: WindowInput) -> WindowStatus:
    """Pure window status. ``is_legal_opinion`` / ``renders_advice`` are hard-wired
    ``False`` (G5 / G9); no code path may set either ``True``."""
    close, source = _resolve_close(inp)
    not_yet_open = inp.as_of < inp.open_date
    # open ONLY within [open_date, close]; a pre-open query is NOT open (bug fix:
    # previously is_open was `as_of <= close`, wrongly reporting a not-yet-started
    # window as open).
    is_open = (not not_yet_open) and inp.as_of <= close
    return WindowStatus(
        target_id=inp.target_id,
        is_legal_opinion=False,  # G5 — no path may set this True
        renders_advice=False,  # G9 — no path may set this True
        is_open=is_open,
        not_yet_open=not_yet_open,
        computed_close=close,
        days_remaining=(close - inp.as_of).days,
        source=source,
        member_confirmed=inp.member_confirmed,
        computation_note=_note(source, close, inp.counting, is_open, not_yet_open),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_window_record(
    s: WindowStatus,
    *,
    member_did: str,
    target_ref: str,
    created_at: datetime,
    session_ref: str | None = None,
    encrypted_detail_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.moushibumi.statusTrack``-shaped (window facet) record.

    ``isLegalOpinion`` and ``rendersAdvice`` are asserted ``False`` before return —
    G5 / G9 schema invariants this function structurally cannot violate.
    """
    rec: dict = {
        "memberDid": member_did,
        "targetRef": target_ref,
        "isLegalOpinion": False,  # G5
        "rendersAdvice": False,  # G9 — political neutrality
        "isOpen": s.is_open,
        "notYetOpen": s.not_yet_open,
        "computedClose": _iso_dt(
            datetime.combine(s.computed_close, datetime.min.time())
        ),
        "daysRemaining": s.days_remaining,
        "source": s.source,
        "computationNote": s.computation_note[:1000],
        "memberConfirmed": s.member_confirmed,
        "createdAt": _iso_dt(created_at),
    }
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    if encrypted_detail_ref is not None:
        rec["encryptedDetailRef"] = encrypted_detail_ref
    assert rec["isLegalOpinion"] is False, "G5 invariant: isLegalOpinion must be False"
    assert rec["rendersAdvice"] is False, "G9 invariant: rendersAdvice must be False"
    return rec


__all__ = [
    "CALENDAR_INCLUSIVE",
    "CALENDAR_EXCLUSIVE",
    "WindowInput",
    "WindowStatus",
    "compute_close",
    "compute_window",
    "to_window_record",
]
