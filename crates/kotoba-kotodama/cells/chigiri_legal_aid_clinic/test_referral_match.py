"""Tests for the chigiri legal-aid REFERRAL RESOLVER pure core (ADR-2605262700).

Locks the G14 / UPL invariant (never renders advice, never determines
eligibility), the registry-confidence-then-title sort, jurisdiction filtering,
optional free-text practice-area filtering, the empty-result-on-unknown rule,
and integration against the worldwide legal-aid seed registry. Pure stdlib,
deterministic, no network — runs in CI.

These do NOT import ``.cell`` (the deployable Pregel intake graph, which stays
non-deployable until Council ratification); the pure core lives in
``.referral_match`` precisely so it is testable without activating the cell.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .referral_match import (
    CONFIDENCE_ORDER,
    Referral,
    ReferralQuery,
    resolve_referrals,
    to_referral_routing_record,
    load_registry,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/chigiri/registry/legal-aid.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(rid, *, jurisdiction="jpn", confidence="high", title="Org",
           status="unverified-seed", notes="", legal_basis="", authority="",
           channel=""):
    return {
        "referralId": rid,
        "title": title,
        "jurisdiction": jurisdiction,
        "confidence": confidence,
        "verificationStatus": status,
        "authority": authority,
        "channel": channel,
        "legalBasis": legal_basis,
        "language": "ja",
        "bloc": "jpn-national",
        "notes": notes,
        "lastVerified": "2026-06-02T00:00:00Z",
        "provenance": "https://example.test",
    }


def _registry(*entries):
    return {"$schema": "com.etzhayyim.chigiri.legalAidReferral", "referrals": list(entries)}


# ── G14 / UPL: never advice, never eligibility ──────────────────────────


@pytest.mark.parametrize("area", [None, "housing", "labor", "no-such-area"])
def test_g14_result_never_renders_advice(area):
    reg = _registry(_entry("a"))
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn", practice_area=area), reg)
    assert res.renders_advice is False


@pytest.mark.parametrize("confidence", sorted(CONFIDENCE_ORDER))
def test_g14_every_referral_renders_advice_false(confidence):
    reg = _registry(_entry("a", confidence=confidence))
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn"), reg)
    assert all(r.renders_advice is False for r in res.referrals)


def test_g14_record_rendersAdvice_always_false():
    reg = _registry(_entry("a", title="Houterasu"))
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn", practice_area="housing"), reg)
    rec = to_referral_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["rendersAdvice"] is False
    assert rec["isEligibilityDetermination"] is False  # no means-test verdict
    assert rec["zeroCompensation"] is True
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["practiceAreaLabel"] == "housing"


def test_g14_record_no_compensation_field_leaks():
    reg = _registry(_entry("a"))
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn"), reg)
    rec = to_referral_routing_record(
        res, member_did="did:web:m",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )
    assert not ({"fee", "price", "amount", "tithe", "cost"} & set(rec))


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_referrals(ReferralQuery(jurisdiction="zz-nowhere"), reg)
    assert res.referrals == ()
    assert res.renders_advice is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn"), reg)
    assert {r.referral_id for r in res.referrals} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="eu-wide"))
    res = resolve_referrals(ReferralQuery(jurisdiction="EU-Wide"), reg)
    assert [r.referral_id for r in res.referrals] == ["a"]
    assert res.jurisdiction == "eu-wide"


# ── sort: confidence then title, registry's OWN signal only ─────────────


def test_sort_high_before_medium():
    reg = _registry(
        _entry("med", confidence="medium", title="AAA"),
        _entry("hi", confidence="high", title="ZZZ"),
    )
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn"), reg)
    assert [r.referral_id for r in res.referrals] == ["hi", "med"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", confidence="high", title="bravo org"),
        _entry("a", confidence="high", title="Alpha Org"),
        _entry("c", confidence="high", title="Charlie"),
    )
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn"), reg)
    assert [r.title for r in res.referrals] == ["Alpha Org", "bravo org", "Charlie"]


def test_full_confidence_ordering_high_medium_low():
    reg = _registry(
        _entry("lo", confidence="low", title="A"),
        _entry("hi", confidence="high", title="A"),
        _entry("med", confidence="medium", title="A"),
    )
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn"), reg)
    assert [r.confidence for r in res.referrals] == ["high", "medium", "low"]


# ── optional free-text practice-area filter (wayfinding only) ───────────


def test_practice_area_label_filters_by_substring():
    reg = _registry(
        _entry("housing", notes="tenant and housing disputes"),
        _entry("labor", legal_basis="labour standards act"),
    )
    res = resolve_referrals(
        ReferralQuery(jurisdiction="jpn", practice_area="housing"), reg)
    assert [r.referral_id for r in res.referrals] == ["housing"]


def test_practice_area_label_case_insensitive():
    reg = _registry(_entry("a", title="Consumer Affairs Center"))
    res = resolve_referrals(
        ReferralQuery(jurisdiction="jpn", practice_area="CONSUMER"), reg)
    assert [r.referral_id for r in res.referrals] == ["a"]


def test_practice_area_no_match_returns_empty():
    reg = _registry(_entry("a", title="Housing Aid"))
    res = resolve_referrals(
        ReferralQuery(jurisdiction="jpn", practice_area="maritime-prize-law"), reg)
    assert res.referrals == ()
    assert res.renders_advice is False  # still never advice, even when empty


def test_none_practice_area_returns_all_in_jurisdiction():
    reg = _registry(_entry("a"), _entry("b"))
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn", practice_area=None), reg)
    assert len(res.referrals) == 2


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_referrals(
        ReferralQuery(jurisdiction="jpn", allow_unverified=False), reg)
    assert [r.referral_id for r in res.referrals] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_referrals(
        ReferralQuery(jurisdiction="jpn", allow_unverified=True), reg)
    assert [r.referral_id for r in res.referrals] == ["seed"]


# ── validation (G8 — well-formed input only, no guessing) ───────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_referrals(ReferralQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_practice_area_raises(bad):
    with pytest.raises(ValueError):
        resolve_referrals(
            ReferralQuery(jurisdiction="jpn", practice_area=bad),
            _registry(_entry("a")),
        )


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_referrals(ReferralQuery(jurisdiction="jpn"), reg)


def test_registry_without_referrals_list_raises():
    with pytest.raises(ValueError):
        resolve_referrals(ReferralQuery(jurisdiction="jpn"), {"referrals": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"referralId": "a", "jurisdiction": "jpn", "confidence": "high"}  # no title
    with pytest.raises(ValueError):
        resolve_referrals(ReferralQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass G14 pin cannot be flipped ──────────────────────────


def test_referral_is_frozen_renders_advice_immutable():
    reg = _registry(_entry("a"))
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn"), reg)
    r = res.referrals[0]
    assert isinstance(r, Referral)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        r.renders_advice = True  # type: ignore[misc]


# ── integration: drive the worldwide legal-aid seed registry ────────────


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {r["jurisdiction"] for r in data["referrals"]}
    assert len(data["referrals"]) >= 30  # worldwide, not JP-only
    assert len(juris) >= 20  # many distinct jurisdictions
    assert "jpn" in juris


def test_registry_jpn_routes_sorted_high_first():
    data = load_registry(_REGISTRY)
    res = resolve_referrals(ReferralQuery(jurisdiction="jpn"), data)
    assert len(res.referrals) == 7  # 7 real jpn entries in the seed
    ranks = [CONFIDENCE_ORDER[r.confidence] for r in res.referrals]
    assert ranks == sorted(ranks)  # non-decreasing confidence rank
    assert res.referrals[0].confidence == "high"  # all-high group leads
    # known anchor entry is present + routed (not advised)
    ids = {r.referral_id for r in res.referrals}
    assert "jp-houterasu-legal-aid" in ids
    assert all(r.renders_advice is False for r in res.referrals)


def test_registry_jpn_labor_label_narrows_to_roudou_corner():
    data = load_registry(_REGISTRY)
    res = resolve_referrals(
        ReferralQuery(jurisdiction="jpn", practice_area="labor"), data)
    ids = {r.referral_id for r in res.referrals}
    assert "jp-mhlw-sougou-roudou-soudan" in ids  # 総合労働相談コーナー
    assert all(r.jurisdiction == "jpn" for r in res.referrals)


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_referrals(ReferralQuery(jurisdiction="zz-atlantis"), data)
    assert res.referrals == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_referrals(ReferralQuery(jurisdiction="usa"), data)
    rec = to_referral_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["rendersAdvice"] is False
    assert rec["isEligibilityDetermination"] is False
    assert rec["referralCount"] == len(res.referrals) == 7
    assert rec["sessionRef"] == "at://session/1"
    # every surfaced referral is a routing view, not an advice payload
    for view in rec["referrals"]:
        assert "channel" in view and "provenance" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
