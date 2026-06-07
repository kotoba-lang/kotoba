"""Tests for the himotoki DSAR/FOIA response-deadline pure core (ADR-2605302130).

Locks the G5 invariant (never a legal opinion), the per-regime well-established
statutory response windows (GDPR 1mo+2mo / CCPA 45+45 / LGPD 15 / PIPEDA 30 / FOIA
20 business days / APPI indeterminate), window boundaries, overdue detection, lawful
extension handling, and integration against the worldwide disclosure-target registry.
Pure stdlib, deterministic, no network — runs in CI.

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
    REGIMES,
    UNIT_BUSINESS_DAYS,
    UNIT_CALENDAR_DAYS,
    UNIT_CALENDAR_MONTHS,
    DeadlineInput,
    _add_business_days,
    compute_deadline_result,
    compute_response_due,
    to_deadline_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/himotoki/registry/targets.seed.json"


# ── G5: never a legal opinion (can-never-be-True) ───────────────────────


@pytest.mark.parametrize("regime_code", sorted(REGIMES))
@pytest.mark.parametrize("extended", [False, True])
def test_g5_is_never_a_legal_opinion(regime_code, extended):
    regime = REGIMES[regime_code]
    # 'extended' is only lawful where the regime has an extension; otherwise skip
    if extended and regime.extension_amount is None:
        pytest.skip("regime has no lawful extension")
    r = compute_deadline_result(DeadlineInput(
        regime_code=regime_code,
        request_sent=date(2026, 6, 1), as_of=date(2026, 6, 3),
        extended=extended,
    ))
    assert r.is_legal_opinion is False


def test_g5_record_isLegalOpinion_always_false():
    r = compute_deadline_result(DeadlineInput(
        regime_code="gdpr-15",
        request_sent=date(2026, 6, 1), as_of=date(2026, 6, 3),
    ))
    rec = to_deadline_record(
        r, member_did="did:web:member.example", target_ref="at://x/y/z",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["regimeCode"] == "gdpr-15"
    assert rec["responseDue"] == "2026-07-01T00:00:00Z"
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["overdue"] is False
    assert rec["indeterminate"] is False


# ── GDPR Art.12(3): 1 month, +2 months extension ────────────────────────


def test_gdpr_one_month():
    # sent 2026-06-01 → one month → 2026-07-01
    r = compute_deadline_result(DeadlineInput(
        regime_code="gdpr-15", request_sent=date(2026, 6, 1), as_of=date(2026, 6, 15),
    ))
    assert r.response_due == date(2026, 7, 1)
    assert r.overdue is False
    assert r.days_remaining == 16
    assert r.extension_applied is False


def test_gdpr_month_end_clamp():
    # sent 2026-01-31 → one month → Feb has 28 days (2026) → clamp to 2026-02-28
    assert compute_response_due(date(2026, 1, 31), REGIMES["gdpr-15"]) == date(2026, 2, 28)


def test_gdpr_extension_plus_two_months():
    # extended: 1 + 2 = 3 months → 2026-06-01 → 2026-09-01
    r = compute_deadline_result(DeadlineInput(
        regime_code="gdpr-15", request_sent=date(2026, 6, 1), as_of=date(2026, 6, 1),
        extended=True,
    ))
    assert r.response_due == date(2026, 9, 1)
    assert r.extension_applied is True


def test_uk_gdpr_matches_gdpr():
    assert (
        compute_response_due(date(2026, 6, 1), REGIMES["uk-gdpr-15"])
        == compute_response_due(date(2026, 6, 1), REGIMES["gdpr-15"])
    )


# ── CCPA/CPRA: 45 days, +45 extension ───────────────────────────────────


def test_ccpa_45_days():
    r = compute_deadline_result(DeadlineInput(
        regime_code="ccpa-110", request_sent=date(2026, 6, 1), as_of=date(2026, 6, 1),
    ))
    assert r.response_due == date(2026, 7, 16)  # 06-01 + 45 days
    assert r.days_remaining == 45


def test_ccpa_extension_90_days():
    r = compute_deadline_result(DeadlineInput(
        regime_code="ccpa-110", request_sent=date(2026, 6, 1), as_of=date(2026, 6, 1),
        extended=True,
    ))
    assert r.response_due == date(2026, 8, 30)  # 06-01 + 90 days
    assert r.extension_applied is True


# ── boundary: exactly-on-deadline vs day-after (overdue) ────────────────


def test_boundary_exactly_on_due_is_not_overdue():
    r = compute_deadline_result(DeadlineInput(
        regime_code="ccpa-110", request_sent=date(2026, 6, 1), as_of=date(2026, 7, 16),
    ))
    assert r.response_due == date(2026, 7, 16)
    assert r.overdue is False
    assert r.days_remaining == 0


def test_boundary_day_after_due_is_overdue():
    r = compute_deadline_result(DeadlineInput(
        regime_code="ccpa-110", request_sent=date(2026, 6, 1), as_of=date(2026, 7, 17),
    ))
    assert r.overdue is True
    assert r.days_remaining == -1


# ── LGPD Art.19: 15 days, no extension ──────────────────────────────────


def test_lgpd_15_days():
    assert compute_response_due(date(2026, 6, 1), REGIMES["lgpd-18"]) == date(2026, 6, 16)


def test_lgpd_no_extension_raises():
    with pytest.raises(ValueError):
        compute_response_due(date(2026, 6, 1), REGIMES["lgpd-18"], extended=True)


# ── PIPEDA: 30 days ─────────────────────────────────────────────────────


def test_pipeda_30_days():
    assert compute_response_due(date(2026, 6, 1), REGIMES["privacy-act-ca"]) == date(2026, 7, 1)


# ── US FOIA: 20 business days (Mon–Fri), holidays not modeled ────────────


def test_foia_20_business_days():
    # Mon 2026-06-01 sent (day 0); 20 business days later. 06-01 is a Monday.
    # weeks of 5 business days → 20 = 4 full weeks = 28 calendar days → Mon 2026-06-29
    r = compute_deadline_result(DeadlineInput(
        regime_code="foia-us-5usc552", request_sent=date(2026, 6, 1), as_of=date(2026, 6, 1),
    ))
    assert r.response_due == date(2026, 6, 29)


def test_foia_business_day_skips_weekend():
    # business-day arithmetic skips Sat/Sun: Fri 2026-06-05 + 1 business day → Mon 2026-06-08
    assert _add_business_days(date(2026, 6, 5), 1) == date(2026, 6, 8)
    # and the next two land on Tue/Wed, never the weekend
    assert _add_business_days(date(2026, 6, 5), 2) == date(2026, 6, 9)
    assert _add_business_days(date(2026, 6, 5), 3) == date(2026, 6, 10)


def test_foia_note_flags_holidays_not_modeled():
    r = compute_deadline_result(DeadlineInput(
        regime_code="foia-us-5usc552", request_sent=date(2026, 6, 1), as_of=date(2026, 6, 2),
    ))
    assert "holidays" in r.computation_note.lower()
    assert "not a legal opinion" in r.computation_note.lower()


def test_foia_no_extension_raises():
    with pytest.raises(ValueError):
        compute_response_due(date(2026, 6, 1), REGIMES["foia-us-5usc552"], extended=True)


# ── JP APPI §33: indeterminate ("without undue delay"), no number invented


def test_appi_indeterminate():
    r = compute_deadline_result(DeadlineInput(
        regime_code="appi-33", request_sent=date(2026, 6, 1), as_of=date(2026, 6, 30),
    ))
    assert r.indeterminate is True
    assert r.response_due is None
    assert r.days_remaining is None
    assert r.overdue is False
    assert "indeterminate" in r.computation_note.lower()


def test_appi_record_omits_responseDue():
    r = compute_deadline_result(DeadlineInput(
        regime_code="appi-33", request_sent=date(2026, 6, 1), as_of=date(2026, 6, 30),
    ))
    rec = to_deadline_record(
        r, member_did="did:web:m", target_ref="at://x",
        created_at=datetime(2026, 6, 30, 9, 0, tzinfo=timezone.utc),
    )
    assert "responseDue" not in rec
    assert rec["indeterminate"] is True
    assert rec["isLegalOpinion"] is False


def test_appi_extended_raises():
    with pytest.raises(ValueError):
        compute_response_due(date(2026, 6, 1), REGIMES["appi-33"], extended=True)


# ── validation (G8/G14 — well-formed, supported input only) ─────────────


def test_unknown_regime_raises():
    with pytest.raises(ValueError):
        compute_deadline_result(DeadlineInput(
            regime_code="made-up-regime-99", request_sent=date(2026, 6, 1),
            as_of=date(2026, 6, 1),
        ))


def test_request_sent_must_be_date():
    with pytest.raises(ValueError):
        compute_response_due("2026-06-01", REGIMES["gdpr-15"])  # type: ignore[arg-type]


def test_as_of_must_be_date():
    with pytest.raises(ValueError):
        compute_deadline_result(DeadlineInput(
            regime_code="gdpr-15", request_sent=date(2026, 6, 1),
            as_of="2026-06-01",  # type: ignore[arg-type]
        ))


# ── integration: drive the worldwide registry's regimes through the core ─


def test_registry_supported_regimes_feed_the_core():
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    targets = data["targets"]
    assert len(targets) >= 5
    supported = [t for t in targets if t.get("regime") in REGIMES]
    # the registry must contain at least the core well-established regimes
    assert len(supported) >= 5, "registry should exercise multiple supported regimes"
    seen_codes = set()
    for t in supported:
        code = t["regime"]
        seen_codes.add(code)
        r = compute_deadline_result(DeadlineInput(
            regime_code=code,
            request_sent=date(2026, 6, 1), as_of=date(2026, 6, 1),
        ))
        assert r.is_legal_opinion is False
        regime = REGIMES[code]
        if regime.base_amount is None:
            assert r.indeterminate is True and r.response_due is None
        else:
            # day-of-send is never already overdue for any positive window
            assert r.indeterminate is False
            assert r.response_due is not None
            assert r.overdue is False
    # ensure the core regimes are genuinely represented in the registry
    assert {"gdpr-15", "ccpa-110", "appi-33"} <= seen_codes


def test_registry_appi_target_is_indeterminate_in_core():
    data = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    appi = next(t for t in data["targets"] if t.get("regime") == "appi-33")
    r = compute_deadline_result(DeadlineInput(
        regime_code=appi["regime"], request_sent=date(2026, 6, 1), as_of=date(2026, 7, 1),
    ))
    assert r.indeterminate is True


def test_core_units_are_distinct():
    assert len({UNIT_CALENDAR_DAYS, UNIT_CALENDAR_MONTHS, UNIT_BUSINESS_DAYS}) == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
