"""Pure DSAR / FOIA response-deadline computation core for ``himotoki_deadline_check``.

Per ADR-2605302130 (繙き himotoki — ACTIVE disclosure-request filer; consent-bound
DSAR (APPI/GDPR/CCPA) + FOIA; own-data-only).

Given the date a disclosure request was *sent* + the *target's regime*, compute the
controller/agency response-due date, whether it is now overdue, and any lawful
statutory extension. INFORMATIONAL date arithmetic only.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * G5 — this module performs INFORMATIONAL date arithmetic only (request-sent date
    + statutory response window → response-due date). It is NOT a legal opinion or
    rights-determination: ``is_legal_opinion`` / ``isLegalOpinion`` is ALWAYS
    ``False`` and there is NO code path that can set it ``True``. Borderline /
    complex / contested cases route to chigiri + licensed counsel via
    ``computation_note``.
  * G14 / G8 — non-fabrication: response windows are WELL-ESTABLISHED statutory
    figures keyed by regime, each cited in :data:`REGIMES`. Where a regime's
    deadline is genuinely indeterminate in statute (e.g. JP APPI §33 "without undue
    delay" / 遅滞なく), it is modelled as ``None`` (indeterminate) — a number is
    NEVER invented. Business-day counting is Mon–Fri only and does NOT model public
    holidays — the note says so loudly so the result is treated as indicative.
  * Consent-gated, own-data-only (DSAR) / public-records (FOIA). Identity-bound,
    transparent, non-pretextual, lawful-channel-only.
  * No PII persistence, no network, no inference, no dispatch. Pure stdlib.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the gated
Pregel wrapper. ``cell.py`` (``HimotokiDeadlineCheckCell``) remains import-time
``RuntimeError`` until Council ratifies ADR-2605302130 (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19). Landing + testing this core does NOT activate the cell;
once Council activates, ``super_step`` will call :func:`compute_deadline_result`
and :func:`to_deadline_record`.

Output shape mirrors Lexicon ``com.etzhayyim.himotoki.responseDeadline``.

WELL-ESTABLISHED STATUTORY RESPONSE WINDOWS (each cited):
  * GDPR / UK GDPR Art.12(3): 1 month, extendable by +2 months for complex /
    numerous requests.
  * CCPA / CPRA: 45 days, extendable +45 days.
  * LGPD Art.19 (Brazil), simplified form: 15 days. (No general statutory extension
    modelled.)
  * PIPEDA (Canada, federal private sector): 30 days.
  * US FOIA, 5 U.S.C. §552(a)(6)(A)(i): 20 business days.
  * JP APPI §33: "without undue delay" (遅滞なく) — indeterminate; modelled as
    ``None``; NO number invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# ── window units ─────────────────────────────────────────────────────────
UNIT_CALENDAR_DAYS = "calendar_days"  # +N calendar days from request-sent date
UNIT_CALENDAR_MONTHS = "calendar_months"  # +N calendar months (GDPR Art.12(3) "one month")
UNIT_BUSINESS_DAYS = "business_days"  # +N business days (Mon–Fri; US FOIA "20 working days")

_UNITS = frozenset({UNIT_CALENDAR_DAYS, UNIT_CALENDAR_MONTHS, UNIT_BUSINESS_DAYS})


@dataclass(frozen=True)
class Regime:
    """A well-established statutory response window for one disclosure regime.

    ``base_amount`` / ``base_unit`` describe the primary response window. A regime
    with an indeterminate statutory window (``base_amount is None``) models a
    "without undue delay"-style rule — no number is invented. ``extension_amount``
    is the lawful, statutorily-named extension (same ``base_unit``); ``None`` means
    the regime has no modelled lawful extension.
    """

    code: str
    label: str
    citation: str
    base_amount: int | None
    base_unit: str
    extension_amount: int | None = None
    kind: str = "dsar"  # "dsar" (own-data-only) | "foia" (public-records)


# Well-established statutory response windows ONLY. Each carries its citation.
REGIMES: dict[str, Regime] = {
    # EU GDPR Art.12(3): one month, extendable by +2 months for complex/numerous.
    "gdpr-15": Regime(
        code="gdpr-15",
        label="EU GDPR right of access (Art.15)",
        citation="Regulation (EU) 2016/679 (GDPR) Art.12(3): respond within one month; "
        "extendable by two further months where requests are complex or numerous",
        base_amount=1,
        base_unit=UNIT_CALENDAR_MONTHS,
        extension_amount=2,
        kind="dsar",
    ),
    # UK GDPR Art.12(3): identical one-month + 2-month extension.
    "uk-gdpr-15": Regime(
        code="uk-gdpr-15",
        label="UK GDPR right of access (Art.15)",
        citation="UK GDPR (as retained) Art.12(3): respond within one month; "
        "extendable by two further months for complex or numerous requests",
        base_amount=1,
        base_unit=UNIT_CALENDAR_MONTHS,
        extension_amount=2,
        kind="dsar",
    ),
    # CCPA/CPRA: 45 days, extendable +45.
    "ccpa-110": Regime(
        code="ccpa-110",
        label="California CCPA/CPRA consumer request",
        citation="Cal. Civ. Code §1798.130(a)(2): respond within 45 days; "
        "extendable once by a further 45 days when reasonably necessary",
        base_amount=45,
        base_unit=UNIT_CALENDAR_DAYS,
        extension_amount=45,
        kind="dsar",
    ),
    # LGPD Art.19 (simplified form): 15 days. No general statutory extension modelled.
    "lgpd-18": Regime(
        code="lgpd-18",
        label="Brazil LGPD confirmation/access (simplified form)",
        citation="Lei nº 13.709/2018 (LGPD) Art.19(II): provide a full declaration "
        "within 15 days of the request (simplified-format response is immediate)",
        base_amount=15,
        base_unit=UNIT_CALENDAR_DAYS,
        extension_amount=None,
        kind="dsar",
    ),
    # PIPEDA (Canada, federal private sector): 30 days.
    "privacy-act-ca": Regime(
        code="privacy-act-ca",
        label="Canada PIPEDA access to personal information",
        citation="PIPEDA S.C. 2000, c.5, Sch.1 cl.4.9.4 / s.8(3): respond not later "
        "than 30 days after receipt of the request",
        base_amount=30,
        base_unit=UNIT_CALENDAR_DAYS,
        extension_amount=None,
        kind="dsar",
    ),
    # US FOIA: 20 business days.
    "foia-us-5usc552": Regime(
        code="foia-us-5usc552",
        label="US federal FOIA records request",
        citation="Freedom of Information Act, 5 U.S.C. §552(a)(6)(A)(i): determine "
        "within 20 working (business) days whether to comply with the request",
        base_amount=20,
        base_unit=UNIT_BUSINESS_DAYS,
        extension_amount=None,
        kind="foia",
    ),
    # JP APPI §33: "without undue delay" (遅滞なく) — indeterminate, no number invented.
    "appi-33": Regime(
        code="appi-33",
        label="Japan APPI §33 開示等の請求",
        citation="個人情報の保護に関する法律 §33: the controller must respond "
        "'without undue delay' (遅滞なく) — no fixed numeric statutory window",
        base_amount=None,
        base_unit=UNIT_CALENDAR_DAYS,
        extension_amount=None,
        kind="dsar",
    ),
}


@dataclass(frozen=True)
class DeadlineInput:
    """Member-confirmed facts about a sent disclosure request."""

    regime_code: str  # must be a key of REGIMES (G14 — well-established only)
    request_sent: date  # the date the disclosure request was sent
    as_of: date  # the date the deadline is computed for ("today")
    extended: bool = False  # the controller/agency invoked the regime's lawful extension
    member_confirmed: bool = False  # G8 — the member confirmed these facts


@dataclass(frozen=True)
class DeadlineResult:
    regime_code: str
    is_legal_opinion: bool  # ALWAYS False (G5)
    response_due: date | None  # None when the regime window is indeterminate
    indeterminate: bool  # True for "without undue delay"-style regimes
    overdue: bool  # past the due date (False when indeterminate)
    days_remaining: int | None  # calendar days to due date; negative if overdue; None if indeterminate
    extension_applied: bool  # the lawful extension was applied to this computation
    member_confirmed: bool
    computation_note: str


def _add_calendar_months(start: date, months: int) -> date:
    """Add ``months`` calendar months, clamping the day to the target month's length.

    Mirrors the common GDPR convention: one month after the 31st of a 30-day month
    is the last day of the following month (day clamped, never rolled over).
    """
    if months < 0:
        raise ValueError("months must be non-negative")
    total = (start.year * 12 + (start.month - 1)) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    # last valid day of the target month
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    return date(year, month, min(start.day, last_day))


def _add_business_days(start: date, n: int) -> date:
    """Date ``n`` business days (Mon–Fri) after ``start``. Holidays NOT modeled.

    The clock starts the day AFTER ``start`` (the request-sent date is day 0), so
    n=1 is the next business day. This matches the FOIA "within 20 working days"
    counting where the day of receipt is excluded.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    count = 0
    d = start
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d


def _apply_window(start: date, amount: int, unit: str) -> date:
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("window amount must be a positive integer")
    if unit == UNIT_CALENDAR_DAYS:
        return start + timedelta(days=amount)
    if unit == UNIT_CALENDAR_MONTHS:
        return _add_calendar_months(start, amount)
    if unit == UNIT_BUSINESS_DAYS:
        return _add_business_days(start, amount)
    raise ValueError(f"unknown window unit: {unit!r}")


def compute_response_due(
    request_sent: date, regime: Regime, *, extended: bool = False
) -> date | None:
    """Response-due date for ``regime`` given ``request_sent``.

    Returns ``None`` when the regime's statutory window is indeterminate (e.g. JP
    APPI "without undue delay"). Raises ``ValueError`` if ``extended`` is requested
    for a regime that has no lawful extension (G14 — never invent an extension).
    """
    if not isinstance(request_sent, date):
        raise ValueError("request_sent must be a datetime.date")
    if regime.base_amount is None:
        if extended:
            raise ValueError(
                f"regime {regime.code!r} has an indeterminate window; "
                "no lawful extension can be applied"
            )
        return None
    if regime.base_unit not in _UNITS:
        raise ValueError(f"unknown window unit: {regime.base_unit!r}")

    total = regime.base_amount
    if extended:
        if regime.extension_amount is None:
            raise ValueError(
                f"regime {regime.code!r} has no lawful statutory extension; "
                "'extended' cannot be applied"
            )
        total += regime.extension_amount
    return _apply_window(request_sent, total, regime.base_unit)


def _unit_human(unit: str) -> str:
    return {
        UNIT_CALENDAR_DAYS: "calendar days",
        UNIT_CALENDAR_MONTHS: "calendar month(s)",
        UNIT_BUSINESS_DAYS: "business days (Mon–Fri)",
    }[unit]


def _note(regime: Regime, due: date | None, extension_applied: bool) -> str:
    parts: list[str] = []
    if due is None:
        parts.append(
            f"Regime {regime.code} ({regime.label}) has no fixed numeric statutory "
            f"response window — {regime.citation}. The response date is INDETERMINATE; "
            "no deadline number is invented (G14)."
        )
    else:
        base = f"{regime.base_amount} {_unit_human(regime.base_unit)}"
        applied = base
        if extension_applied and regime.extension_amount is not None:
            applied = (
                f"{regime.base_amount}+{regime.extension_amount} "
                f"{_unit_human(regime.base_unit)} (lawful extension applied)"
            )
        parts.append(
            f"Computed response-due {due.isoformat()} = {applied} from the "
            f"request-sent date, per {regime.citation}."
        )
        if regime.base_unit == UNIT_BUSINESS_DAYS:
            parts.append(
                "Business-day counting is Mon–Fri only and does NOT account for "
                "public holidays; treat the deadline as indicative."
            )
    parts.append(
        "INFORMATIONAL date computation per ADR-2605302130 G5 — NOT a legal opinion "
        "or rights-determination."
    )
    parts.append(
        f"{'Public-records (FOIA)' if regime.kind == 'foia' else 'Consent-gated, own-data-only (DSAR)'}; "
        "statutory tolling / receipt-date assumptions / per-agency rules vary — verify "
        "against the cited statute and route borderline / complex / time-critical cases "
        "to chigiri + licensed counsel. The member must confirm the input facts."
    )
    return " ".join(parts)


def compute_deadline_result(inp: DeadlineInput) -> DeadlineResult:
    """Pure deadline assessment. ``is_legal_opinion`` is hard-wired ``False`` (G5)."""
    regime = REGIMES.get(inp.regime_code)
    if regime is None:
        raise ValueError(
            f"unknown / unsupported regime code: {inp.regime_code!r} — "
            "himotoki computes only well-established statutory windows (G14)"
        )
    if not isinstance(inp.as_of, date):
        raise ValueError("as_of must be a datetime.date")

    due = compute_response_due(inp.request_sent, regime, extended=inp.extended)
    extension_applied = inp.extended and regime.extension_amount is not None
    if due is None:
        return DeadlineResult(
            regime_code=regime.code,
            is_legal_opinion=False,  # G5 — no path may set this True
            response_due=None,
            indeterminate=True,
            overdue=False,
            days_remaining=None,
            extension_applied=False,
            member_confirmed=inp.member_confirmed,
            computation_note=_note(regime, None, False),
        )
    return DeadlineResult(
        regime_code=regime.code,
        is_legal_opinion=False,  # G5 — no path may set this True
        response_due=due,
        indeterminate=False,
        overdue=inp.as_of > due,
        days_remaining=(due - inp.as_of).days,
        extension_applied=extension_applied,
        member_confirmed=inp.member_confirmed,
        computation_note=_note(regime, due, extension_applied),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_deadline_record(
    r: DeadlineResult,
    *,
    member_did: str,
    target_ref: str,
    created_at: datetime,
    session_ref: str | None = None,
    encrypted_request_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.himotoki.responseDeadline``-shaped record.

    ``isLegalOpinion`` is asserted ``False`` before return — a G5 schema invariant
    that this function structurally cannot violate.
    """
    rec: dict = {
        "memberDid": member_did,
        "targetRef": target_ref,
        "regimeCode": r.regime_code,
        "isLegalOpinion": False,  # G5
        "indeterminate": r.indeterminate,
        "overdue": r.overdue,
        "extensionApplied": r.extension_applied,
        "memberConfirmed": r.member_confirmed,
        "computationNote": r.computation_note[:1000],
        "createdAt": _iso_dt(created_at),
    }
    if r.response_due is not None:
        rec["responseDue"] = _iso_dt(
            datetime.combine(r.response_due, datetime.min.time())
        )
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    if encrypted_request_ref is not None:
        rec["encryptedRequestRef"] = encrypted_request_ref
    assert rec["isLegalOpinion"] is False, "G5 invariant: isLegalOpinion must be False"
    return rec


__all__ = [
    "UNIT_CALENDAR_DAYS",
    "UNIT_CALENDAR_MONTHS",
    "UNIT_BUSINESS_DAYS",
    "Regime",
    "REGIMES",
    "DeadlineInput",
    "DeadlineResult",
    "compute_response_due",
    "compute_deadline_result",
    "to_deadline_record",
]
