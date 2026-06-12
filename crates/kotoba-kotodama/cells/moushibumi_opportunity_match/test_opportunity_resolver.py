"""Tests for the moushibumi PARTICIPATION-OPPORTUNITY RESOLVER pure core (ADR-2605312400).

Locks the G3 political-neutrality ceiling (never renders advice, never a legal
opinion, never an eligibility/rights determination), the registry-confidence-then-
title-then-organization sort, jurisdiction filtering, the optional structured
``channelKind`` filter, the empty-result-on-unknown rule, and integration against
the worldwide participation-target seed registry. Pure stdlib, deterministic, no
network — runs in CI.

These do NOT import ``.cell`` (the deployable Pregel participation-match graph,
which stays import-time ``RuntimeError`` until Council ratification); the pure
core lives in ``.opportunity_resolver`` precisely so it is testable without
activating the cell.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .opportunity_resolver import (
    CONFIDENCE_ORDER,
    Opportunity,
    OpportunityQuery,
    resolve_opportunities,
    to_opportunity_routing_record,
    load_registry,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/moushibumi/registry/targets.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(tid, *, jurisdiction="jpn", channel_kind="petition", title="Channel",
           confidence=None, status="unverified-seed", organ="", notes="",
           legal_basis="", portal_url=""):
    e = {
        "targetId": tid,
        "title": title,
        "jurisdiction": jurisdiction,
        "channelKind": channel_kind,
        "organ": organ,
        "channelType": "web-portal",
        "submissionForm": "",
        "deadline": "",
        "legalBasis": legal_basis,
        "language": "ja",
        "portalUrl": portal_url,
        "notes": notes,
        "lastVerified": "2026-06-02T00:00:00Z",
        "verificationStatus": status,
        "provenance": "https://example.test",
    }
    if confidence is not None:
        e["confidence"] = confidence
    return e


def _registry(*entries):
    return {
        "$schema": "com.etzhayyim.moushibumi.participationTarget",
        "targets": list(entries),
    }


# ── G3: never advice, never legal opinion, never eligibility ─────────────


@pytest.mark.parametrize("kind", [None, "petition", "public-comment", "no-such-kind"])
def test_g3_result_never_renders_advice_or_opinion(kind):
    reg = _registry(_entry("a"))
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", channel_kind=kind), reg)
    assert res.renders_advice is False
    assert res.is_legal_opinion is False


@pytest.mark.parametrize("confidence", [None, *sorted(CONFIDENCE_ORDER)])
def test_g3_every_opportunity_invariants_false(confidence):
    reg = _registry(_entry("a", confidence=confidence))
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    assert all(o.renders_advice is False for o in res.opportunities)
    assert all(o.is_legal_opinion is False for o in res.opportunities)


def test_g3_record_invariants_always_false():
    reg = _registry(_entry("a", title="Egov Public Comment", channel_kind="public-comment"))
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", channel_kind="public-comment"), reg)
    rec = to_opportunity_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["rendersAdvice"] is False
    assert rec["isEligibilityDetermination"] is False  # no rights / means-test verdict
    assert rec["politicallyNeutral"] is True  # 公選法-equivalent
    assert rec["officialSourcesOnly"] is True
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["channelKind"] == "public-comment"


def test_g3_record_no_partisan_or_compensation_field_leaks():
    reg = _registry(_entry("a"))
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    rec = to_opportunity_routing_record(
        res, member_did="did:web:m",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )
    # no campaigning / endorsement / candidate / GOTV / fee fields ever leak
    banned = {"candidate", "party", "endorsement", "recommend", "vote",
              "gotv", "fee", "price", "amount", "tithe", "cost"}
    assert not (banned & set(rec))


def test_g3_can_never_be_true_no_code_path():
    # there is no public API, builder arg, or registry field that flips either
    # invariant True. Even an entry that *claims* to be advice is pinned False.
    reg = _registry(_entry("a"))
    reg["targets"][0]["isLegalOpinion"] = True  # hostile registry value
    reg["targets"][0]["rendersAdvice"] = True
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    assert res.is_legal_opinion is False
    assert res.renders_advice is False
    assert all(o.is_legal_opinion is False for o in res.opportunities)
    assert all(o.renders_advice is False for o in res.opportunities)


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_opportunities(OpportunityQuery(jurisdiction="zz-nowhere"), reg)
    assert res.opportunities == ()
    assert res.renders_advice is False
    assert res.is_legal_opinion is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    assert {o.target_id for o in res.opportunities} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="eu-wide"))
    res = resolve_opportunities(OpportunityQuery(jurisdiction="EU-Wide"), reg)
    assert [o.target_id for o in res.opportunities] == ["a"]
    assert res.jurisdiction == "eu-wide"


# ── sort: confidence then title then organization, registry's OWN signal ─


def test_sort_high_before_medium_when_confidence_present():
    reg = _registry(
        _entry("med", confidence="medium", title="AAA"),
        _entry("hi", confidence="high", title="ZZZ"),
    )
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    assert [o.target_id for o in res.opportunities] == ["hi", "med"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", title="bravo channel"),
        _entry("a", title="Alpha Channel"),
        _entry("c", title="Charlie"),
    )
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    assert [o.title for o in res.opportunities] == [
        "Alpha Channel", "bravo channel", "Charlie"]


def test_sort_full_confidence_ordering_high_medium_low_then_absent():
    reg = _registry(
        _entry("none", confidence=None, title="A"),
        _entry("lo", confidence="low", title="A"),
        _entry("hi", confidence="high", title="A"),
        _entry("med", confidence="medium", title="A"),
    )
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    assert [o.target_id for o in res.opportunities] == ["hi", "med", "lo", "none"]


def test_sort_organization_breaks_title_tie():
    reg = _registry(
        _entry("b", title="Same Title", organ="Zeta Office"),
        _entry("a", title="Same Title", organ="Alpha Office"),
    )
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    assert [o.target_id for o in res.opportunities] == ["a", "b"]


def test_sort_seed_with_no_confidence_is_pure_title_order():
    # the real seed ships NO confidence; absent-everywhere collapses to title sort
    reg = _registry(
        _entry("z", title="Zebra"),
        _entry("a", title="apple"),
        _entry("m", title="Mango"),
    )
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    assert [o.target_id for o in res.opportunities] == ["a", "m", "z"]


# ── optional structured channelKind filter (pure data routing) ──────────


def test_channel_kind_filters_exact_match():
    reg = _registry(
        _entry("pet", channel_kind="petition"),
        _entry("pc", channel_kind="public-comment"),
        _entry("init", channel_kind="citizen-initiative"),
    )
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", channel_kind="public-comment"), reg)
    assert [o.target_id for o in res.opportunities] == ["pc"]


def test_channel_kind_case_insensitive():
    reg = _registry(_entry("a", channel_kind="election-info"))
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", channel_kind="ELECTION-INFO"), reg)
    assert [o.target_id for o in res.opportunities] == ["a"]


def test_channel_kind_no_match_returns_empty():
    reg = _registry(_entry("a", channel_kind="petition"))
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", channel_kind="referendum-no-such"), reg)
    assert res.opportunities == ()
    assert res.renders_advice is False  # still never advice, even when empty


def test_none_channel_kind_returns_all_in_jurisdiction():
    reg = _registry(_entry("a", channel_kind="petition"), _entry("b", channel_kind="public-comment"))
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", channel_kind=None), reg)
    assert len(res.opportunities) == 2


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", allow_unverified=False), reg)
    assert [o.target_id for o in res.opportunities] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", allow_unverified=True), reg)
    assert [o.target_id for o in res.opportunities] == ["seed"]


# ── validation (G8 — well-formed input only, no guessing) ───────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_opportunities(OpportunityQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_channel_kind_raises(bad):
    with pytest.raises(ValueError):
        resolve_opportunities(
            OpportunityQuery(jurisdiction="jpn", channel_kind=bad),
            _registry(_entry("a")),
        )


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)


def test_registry_without_targets_list_raises():
    with pytest.raises(ValueError):
        resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), {"targets": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"targetId": "a", "jurisdiction": "jpn", "channelKind": "petition"}  # no title
    with pytest.raises(ValueError):
        resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass G3 pin cannot be flipped ───────────────────────────


def test_opportunity_is_frozen_invariants_immutable():
    reg = _registry(_entry("a"))
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), reg)
    o = res.opportunities[0]
    assert isinstance(o, Opportunity)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        o.renders_advice = True  # type: ignore[misc]
    with pytest.raises(Exception):
        o.is_legal_opinion = True  # type: ignore[misc]


# ── integration: drive the worldwide participation-target seed registry ──


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {t["jurisdiction"] for t in data["targets"]}
    assert len(data["targets"]) >= 50  # worldwide, not JP-only
    assert len(juris) >= 30  # many distinct jurisdictions
    assert "jpn" in juris and "usa" in juris


def test_registry_jpn_routes_sorted_and_neutral():
    data = load_registry(_REGISTRY)
    res = resolve_opportunities(OpportunityQuery(jurisdiction="jpn"), data)
    assert len(res.opportunities) == 5  # 5 real jpn entries in the seed
    # known anchor entries present + routed (not advised / endorsed)
    ids = {o.target_id for o in res.opportunities}
    assert "jp-kokkai-seigan" in ids
    assert "jp-egov-public-comment" in ids
    assert all(o.renders_advice is False for o in res.opportunities)
    assert all(o.is_legal_opinion is False for o in res.opportunities)
    # seed has no confidence → pure title order
    titles = [o.title.casefold() for o in res.opportunities]
    assert titles == sorted(titles)


def test_registry_jpn_petition_filter_narrows_to_seigan_chinjo():
    data = load_registry(_REGISTRY)
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", channel_kind="petition"), data)
    ids = {o.target_id for o in res.opportunities}
    assert ids == {"jp-kokkai-seigan", "jp-chihogikai-chinjo"}
    assert all(o.channel_kind == "petition" for o in res.opportunities)
    assert all(o.jurisdiction == "jpn" for o in res.opportunities)


def test_registry_election_info_points_to_official_only():
    data = load_registry(_REGISTRY)
    res = resolve_opportunities(
        OpportunityQuery(jurisdiction="jpn", channel_kind="election-info"), data)
    ids = {o.target_id for o in res.opportunities}
    assert "jp-election-info" in ids
    # an election-info entry is still pure info routing — never advice/endorsement
    assert all(o.renders_advice is False for o in res.opportunities)


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_opportunities(OpportunityQuery(jurisdiction="zz-atlantis"), data)
    assert res.opportunities == ()


def test_registry_real_record_is_pure_neutral_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_opportunities(OpportunityQuery(jurisdiction="usa"), data)
    rec = to_opportunity_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["isLegalOpinion"] is False
    assert rec["rendersAdvice"] is False
    assert rec["isEligibilityDetermination"] is False
    assert rec["politicallyNeutral"] is True
    assert rec["opportunityCount"] == len(res.opportunities) == 7
    assert rec["sessionRef"] == "at://session/1"
    # every surfaced opportunity is a routing view, not an advice/endorsement payload
    for view in rec["opportunities"]:
        assert "channelKind" in view and "provenance" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
