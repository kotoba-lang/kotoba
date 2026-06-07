"""Tests for the kurashimori ESCALATION-FORUM RESOLVER pure core (ADR-2605312500).

Locks the G5 / UPL ROUTE-NOT-REPRESENT invariant (never a legal opinion, never
eligibility, never representation, never date math), the escalation-only remedy
filter, the registry-confidence-then-title sort, jurisdiction filtering, the
optional secondary forum-kind filter, the empty-result-on-unknown rule, and
integration against the worldwide consumer-remedy seed registry. Pure stdlib,
deterministic, no network — runs in CI.

These do NOT import ``.cell`` (the deployable Pregel cell, which stays import-time
RuntimeError until Council ratification); the pure core lives in
``.escalation_resolver`` precisely so it is testable without activating the cell.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .escalation_resolver import (
    CONFIDENCE_ORDER,
    ESCALATION_KINDS,
    EscalationQuery,
    EscalationTarget,
    resolve_escalation_targets,
    to_escalation_routing_record,
    load_registry,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/kurashimori/registry/targets.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(rid, *, jurisdiction="jpn", remedy_kind="escalation-public",
           title="Forum", status="unverified-seed", forum="", channel="",
           legal_basis=""):
    return {
        "remedyId": rid,
        "title": title,
        "jurisdiction": jurisdiction,
        "remedyKind": remedy_kind,
        "statutoryWindowDays": 0,
        "windowStart": "(随時)",
        "formRef": "chigiri:consumer:x:v0",
        "deliveryChannel": channel,
        "escalationForum": forum,
        "legalBasis": legal_basis,
        "language": "ja",
        "provenance": "https://example.test",
        "lastVerified": "2026-06-02T00:00:00Z",
        "verificationStatus": status,
        "notes": "",
    }


def _registry(*entries):
    return {"$schema": "com.etzhayyim.kurashimori.remedyTarget", "targets": list(entries)}


# ── G5 / UPL: never legal opinion, never eligibility, never representation ─


@pytest.mark.parametrize("forum_kind", [None, "escalation-public", "escalation-adr"])
def test_g5_result_never_legal_opinion(forum_kind):
    reg = _registry(_entry("a", remedy_kind="escalation-public"),
                    _entry("b", remedy_kind="escalation-adr"))
    res = resolve_escalation_targets(
        EscalationQuery(jurisdiction="jpn", forum_kind=forum_kind), reg)
    assert res.is_legal_opinion is False


@pytest.mark.parametrize("status", sorted(CONFIDENCE_ORDER))
def test_g5_every_target_is_legal_opinion_false(status):
    reg = _registry(_entry("a", status=status))
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    assert all(t.is_legal_opinion is False for t in res.targets)


def test_g5_record_isLegalOpinion_always_false():
    reg = _registry(_entry("a", title="消費生活センター 188"))
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    rec = to_escalation_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["isEligibilityDetermination"] is False  # no rights/means-test verdict
    assert rec["isRepresentation"] is False  # ROUTE-NOT-REPRESENT
    assert rec["zeroCompensation"] is True
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"


def test_g5_record_no_compensation_or_datemath_field_leaks():
    reg = _registry(_entry("a"))
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    rec = to_escalation_routing_record(
        res, member_did="did:web:m",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )
    # no fee/compensation field, and no statutory-window/date-math field leaks
    leaked = {"fee", "price", "amount", "tithe", "cost",
              "statutoryWindowDays", "deadline", "windowStart"} & set(rec)
    assert not leaked


# ── escalation-only remedy filter (the core purpose) ────────────────────


def test_only_escalation_kinds_surface_self_help_dropped():
    reg = _registry(
        _entry("cool", remedy_kind="cooling-off"),
        _entry("ret", remedy_kind="return-policy"),
        _entry("warr", remedy_kind="warranty"),
        _entry("cb", remedy_kind="chargeback"),
        _entry("pub", remedy_kind="escalation-public"),
        _entry("adr", remedy_kind="escalation-adr"),
    )
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    assert {t.remedy_id for t in res.targets} == {"pub", "adr"}
    assert all(t.remedy_kind in ESCALATION_KINDS for t in res.targets)


def test_jurisdiction_with_only_self_help_returns_empty():
    reg = _registry(
        _entry("cool", remedy_kind="cooling-off"),
        _entry("ret", remedy_kind="return-policy"),
    )
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    assert res.targets == ()
    assert res.is_legal_opinion is False


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="zz-nowhere"), reg)
    assert res.targets == ()
    assert res.is_legal_opinion is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    assert {t.remedy_id for t in res.targets} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="eu-wide"))
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="EU-Wide"), reg)
    assert [t.remedy_id for t in res.targets] == ["a"]
    assert res.jurisdiction == "eu-wide"


# ── sort: confidence (verificationStatus) then title, registry signal only ─


def test_sort_council_verified_before_unverified_seed():
    reg = _registry(
        _entry("seed", status="unverified-seed", title="AAA"),
        _entry("cv", status="council-verified", title="ZZZ"),
    )
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    assert [t.remedy_id for t in res.targets] == ["cv", "seed"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", status="unverified-seed", title="bravo forum"),
        _entry("a", status="unverified-seed", title="Alpha Forum"),
        _entry("c", status="unverified-seed", title="Charlie"),
    )
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    assert [t.title for t in res.targets] == ["Alpha Forum", "bravo forum", "Charlie"]


def test_full_confidence_ordering_council_verified_unverified():
    reg = _registry(
        _entry("seed", status="unverified-seed", title="A"),
        _entry("cv", status="council-verified", title="A"),
        _entry("v", status="verified", title="A"),
    )
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    assert [t.confidence for t in res.targets] == [
        "council-verified", "verified", "unverified-seed"]


# ── optional secondary forum-kind filter ────────────────────────────────


def test_forum_kind_public_narrows():
    reg = _registry(
        _entry("pub", remedy_kind="escalation-public"),
        _entry("adr", remedy_kind="escalation-adr"),
    )
    res = resolve_escalation_targets(
        EscalationQuery(jurisdiction="jpn", forum_kind="escalation-public"), reg)
    assert [t.remedy_id for t in res.targets] == ["pub"]


def test_forum_kind_adr_narrows():
    reg = _registry(
        _entry("pub", remedy_kind="escalation-public"),
        _entry("adr", remedy_kind="escalation-adr"),
    )
    res = resolve_escalation_targets(
        EscalationQuery(jurisdiction="jpn", forum_kind="escalation-adr"), reg)
    assert [t.remedy_id for t in res.targets] == ["adr"]


def test_forum_kind_case_insensitive():
    reg = _registry(_entry("adr", remedy_kind="escalation-adr"))
    res = resolve_escalation_targets(
        EscalationQuery(jurisdiction="jpn", forum_kind="ESCALATION-ADR"), reg)
    assert [t.remedy_id for t in res.targets] == ["adr"]


def test_none_forum_kind_returns_both_kinds():
    reg = _registry(
        _entry("pub", remedy_kind="escalation-public"),
        _entry("adr", remedy_kind="escalation-adr"),
    )
    res = resolve_escalation_targets(
        EscalationQuery(jurisdiction="jpn", forum_kind=None), reg)
    assert len(res.targets) == 2


def test_non_escalation_forum_kind_rejected():
    # a self-help remedy kind is NOT a valid escalation forum_kind filter
    with pytest.raises(ValueError):
        resolve_escalation_targets(
            EscalationQuery(jurisdiction="jpn", forum_kind="cooling-off"),
            _registry(_entry("a")),
        )


# ── validation (G8 — well-formed input only, no guessing) ───────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_escalation_targets(EscalationQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_forum_kind_raises(bad):
    with pytest.raises(ValueError):
        resolve_escalation_targets(
            EscalationQuery(jurisdiction="jpn", forum_kind=bad),
            _registry(_entry("a")),
        )


def test_unknown_verification_status_in_registry_raises():
    reg = _registry(_entry("a", status="cosmic-grade"))
    with pytest.raises(ValueError):
        resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)


def test_registry_without_targets_list_raises():
    with pytest.raises(ValueError):
        resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), {"targets": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"remedyId": "a", "jurisdiction": "jpn", "remedyKind": "escalation-public"}  # no title
    with pytest.raises(ValueError):
        resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass G5 pin cannot be flipped (can-never-be-True) ───────


def test_target_is_frozen_is_legal_opinion_immutable():
    reg = _registry(_entry("a"))
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), reg)
    t = res.targets[0]
    assert isinstance(t, EscalationTarget)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        t.is_legal_opinion = True  # type: ignore[misc]


def test_g5_invariant_holds_across_all_kinds_and_statuses():
    # exhaustive cross-product: no remedy kind / verification status produces a True
    entries = []
    for i, kind in enumerate(sorted(ESCALATION_KINDS)):
        for j, status in enumerate(sorted(CONFIDENCE_ORDER)):
            entries.append(_entry(f"e{i}{j}", remedy_kind=kind, status=status,
                                  title=f"Forum {i}{j}"))
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), _registry(*entries))
    assert len(res.targets) == len(entries)
    assert all(t.is_legal_opinion is False for t in res.targets)
    assert res.is_legal_opinion is False


# ── integration: drive the worldwide consumer-remedy seed registry ──────


def test_registry_loads_and_has_worldwide_escalation_coverage():
    data = load_registry(_REGISTRY)
    esc = [t for t in data["targets"] if t["remedyKind"] in ESCALATION_KINDS]
    juris = {t["jurisdiction"] for t in esc}
    assert len(esc) >= 20  # worldwide escalation forums, not JP-only
    assert len(juris) >= 15  # many distinct jurisdictions
    assert "jpn" in juris


def test_registry_jpn_escalation_routes_both_kinds():
    data = load_registry(_REGISTRY)
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), data)
    ids = {t.remedy_id for t in res.targets}
    assert ids == {"jp-shohi-center-188", "jp-tekikaku-adr"}  # exactly the 2 jpn escalation forums
    kinds = {t.remedy_kind for t in res.targets}
    assert kinds == {"escalation-public", "escalation-adr"}
    assert all(t.is_legal_opinion is False for t in res.targets)


def test_registry_jpn_drops_cooling_off_and_return_policy():
    # jpn has cooling-off + return-policy entries that must NOT surface here
    data = load_registry(_REGISTRY)
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), data)
    assert all(t.remedy_kind in ESCALATION_KINDS for t in res.targets)


def test_registry_eu_wide_forum_kind_filter():
    data = load_registry(_REGISTRY)
    pub = resolve_escalation_targets(
        EscalationQuery(jurisdiction="eu-wide", forum_kind="escalation-public"), data)
    adr = resolve_escalation_targets(
        EscalationQuery(jurisdiction="eu-wide", forum_kind="escalation-adr"), data)
    assert all(t.remedy_kind == "escalation-public" for t in pub.targets)
    assert all(t.remedy_kind == "escalation-adr" for t in adr.targets)
    adr_ids = {t.remedy_id for t in adr.targets}
    assert "eu-adr-consumer-dispute-resolution" in adr_ids


def test_registry_sort_is_non_decreasing_confidence_rank():
    data = load_registry(_REGISTRY)
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="eu-wide"), data)
    ranks = [CONFIDENCE_ORDER[t.verification_status] for t in res.targets]
    assert ranks == sorted(ranks)  # non-decreasing confidence rank


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="zz-atlantis"), data)
    assert res.targets == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_escalation_targets(EscalationQuery(jurisdiction="jpn"), data)
    rec = to_escalation_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["isLegalOpinion"] is False
    assert rec["isEligibilityDetermination"] is False
    assert rec["isRepresentation"] is False
    assert rec["targetCount"] == len(res.targets) == 2
    assert rec["sessionRef"] == "at://session/1"
    # every surfaced target is a routing view, not an advice / date-math payload
    for view in rec["targets"]:
        assert "escalationForum" in view and "provenance" in view
        assert "statutoryWindowDays" not in view  # no date math leaks into routing


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
