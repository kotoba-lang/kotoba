"""Tests for the himotoki DISCLOSURE-TARGET RESOLVER pure core (ADR-2605302130).

Locks the constitutional invariant (never a legal opinion, never an eligibility
determination, never a deadline computation — routing only), the
registry-confidence-then-organization sort, jurisdiction filtering, the optional
regime secondary filter (regime OR altRegimes), the empty-result-on-unknown rule,
and integration against the worldwide disclosure-target seed registry. Pure
stdlib, deterministic, no network — runs in CI.

These do NOT import ``.cell`` (the deployable Pregel graph, which stays
non-deployable / import-time RuntimeError until Council ratification); the pure
core lives in ``.target_resolver`` precisely so it is testable without
activating the cell.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .target_resolver import (
    CONFIDENCE_ORDER,
    DisclosureTarget,
    TargetQuery,
    resolve_targets,
    to_target_routing_record,
    load_registry,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/himotoki/registry/targets.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(org, *, jurisdiction="usa", regime="gdpr-15", confidence="high",
           alt_regimes=None, status="unverified-seed", deadline=30,
           channel="web-portal", portal="https://example.test/dsar"):
    e = {
        "organization": org,
        "jurisdiction": jurisdiction,
        "regime": regime,
        "altRegimes": list(alt_regimes) if alt_regimes is not None else None,
        "verificationStatus": status,
        "channelType": channel,
        "portalUrl": portal,
        "contactEmail": "privacy@example.test",
        "formRef": "chigiri:dsar:v0",
        "statutoryDeadlineDays": deadline,
        "language": "en",
        "bloc": "test-bloc",
        "notes": "seed scaffold",
        "provenance": "https://example.test/privacy",
        "lastVerified": "2026-05-30T00:00:00Z",
    }
    if confidence is not None:
        e["confidence"] = confidence
    return e


def _registry(*entries):
    return {"$schema": "com.etzhayyim.himotoki.disclosureTarget",
            "targets": list(entries)}


# ── constitutional invariant: never opinion / eligibility / deadline ────


@pytest.mark.parametrize("regime", [None, "gdpr-15", "ccpa-110", "no-such-regime"])
def test_result_never_is_legal_opinion(regime):
    reg = _registry(_entry("a"))
    res = resolve_targets(TargetQuery(jurisdiction="usa", regime=regime), reg)
    assert res.is_legal_opinion is False


@pytest.mark.parametrize("confidence", [*sorted(CONFIDENCE_ORDER), None])
def test_every_target_is_legal_opinion_false(confidence):
    reg = _registry(_entry("a", confidence=confidence))
    res = resolve_targets(TargetQuery(jurisdiction="usa"), reg)
    assert all(t.is_legal_opinion is False for t in res.targets)


def test_record_is_legal_opinion_always_false():
    reg = _registry(_entry("Acme Corp"))
    res = resolve_targets(TargetQuery(jurisdiction="usa", regime="gdpr-15"), reg)
    rec = to_target_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["isEligibilityDetermination"] is False  # no means/standing verdict
    assert rec["isDeadlineComputation"] is False  # routing only, not date math
    assert rec["routingOnly"] is True
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["regime"] == "gdpr-15"


def test_record_no_eligibility_or_rights_field_leaks():
    reg = _registry(_entry("a"))
    res = resolve_targets(TargetQuery(jurisdiction="usa"), reg)
    rec = to_target_routing_record(
        res, member_did="did:web:m",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )
    leak = {"eligible", "qualifies", "rights", "verdict", "advice", "deadline"}
    assert not (leak & set(rec))


# ── the invariant can NEVER be flipped to True (no code path) ────────────


def test_target_is_frozen_is_legal_opinion_immutable():
    reg = _registry(_entry("a"))
    res = resolve_targets(TargetQuery(jurisdiction="usa"), reg)
    t = res.targets[0]
    assert isinstance(t, DisclosureTarget)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        t.is_legal_opinion = True  # type: ignore[misc]


def test_no_confidence_path_can_force_is_legal_opinion_true():
    # Even a maliciously-crafted entry that carries isLegalOpinion=True is
    # ignored: the projection hard-wires False regardless of input.
    bad = _entry("a")
    bad["isLegalOpinion"] = True
    bad["is_legal_opinion"] = True
    res = resolve_targets(TargetQuery(jurisdiction="usa"), _registry(bad))
    assert res.targets[0].is_legal_opinion is False
    assert res.is_legal_opinion is False


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="usa"), _entry("b", jurisdiction="jpn"))
    res = resolve_targets(TargetQuery(jurisdiction="zz-nowhere"), reg)
    assert res.targets == ()
    assert res.is_legal_opinion is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="usa"),
        _entry("b", jurisdiction="jpn"),
        _entry("c", jurisdiction="usa"),
    )
    res = resolve_targets(TargetQuery(jurisdiction="usa"), reg)
    assert {t.organization for t in res.targets} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="eu-wide"))
    res = resolve_targets(TargetQuery(jurisdiction="EU-Wide"), reg)
    assert [t.organization for t in res.targets] == ["a"]
    assert res.jurisdiction == "eu-wide"


# ── sort: confidence then organization, registry's OWN signal only ──────


def test_sort_high_before_medium():
    reg = _registry(
        _entry("med-org", confidence="medium"),
        _entry("hi-org", confidence="high"),
    )
    res = resolve_targets(TargetQuery(jurisdiction="usa"), reg)
    # hi-org leads despite alphabetically following med-org
    assert [t.organization for t in res.targets] == ["hi-org", "med-org"]


def test_sort_ties_broken_by_organization_case_insensitive():
    reg = _registry(
        _entry("bravo corp", confidence="high"),
        _entry("Alpha Corp", confidence="high"),
        _entry("Charlie", confidence="high"),
    )
    res = resolve_targets(TargetQuery(jurisdiction="usa"), reg)
    assert [t.organization for t in res.targets] == ["Alpha Corp", "bravo corp", "Charlie"]


def test_full_confidence_ordering_high_medium_low():
    reg = _registry(
        _entry("lo", confidence="low"),
        _entry("hi", confidence="high"),
        _entry("med", confidence="medium"),
    )
    res = resolve_targets(TargetQuery(jurisdiction="usa"), reg)
    assert [t.confidence for t in res.targets] == ["high", "medium", "low"]


def test_ungraded_entries_sort_after_all_graded_but_are_kept():
    reg = _registry(
        _entry("ungraded", confidence=None),  # no confidence field
        _entry("graded-low", confidence="low"),
        _entry("graded-high", confidence="high"),
    )
    res = resolve_targets(TargetQuery(jurisdiction="usa"), reg)
    assert [t.organization for t in res.targets] == [
        "graded-high", "graded-low", "ungraded"]
    assert res.targets[-1].confidence == ""  # ungraded surfaced, not dropped


# ── optional regime secondary filter (regime OR altRegimes) ─────────────


def test_regime_filter_matches_primary_regime():
    reg = _registry(
        _entry("gdpr-org", regime="gdpr-15"),
        _entry("ccpa-org", regime="ccpa-110"),
    )
    res = resolve_targets(TargetQuery(jurisdiction="usa", regime="ccpa-110"), reg)
    assert [t.organization for t in res.targets] == ["ccpa-org"]


def test_regime_filter_matches_alt_regimes():
    reg = _registry(
        _entry("primary-ccpa", regime="ccpa-110", alt_regimes=["gdpr-15", "appi-33"]),
        _entry("primary-other", regime="lgpd-18", alt_regimes=None),
    )
    res = resolve_targets(TargetQuery(jurisdiction="usa", regime="gdpr-15"), reg)
    assert [t.organization for t in res.targets] == ["primary-ccpa"]


def test_regime_filter_case_insensitive():
    reg = _registry(_entry("a", regime="GDPR-15"))
    res = resolve_targets(TargetQuery(jurisdiction="usa", regime="gdpr-15"), reg)
    assert [t.organization for t in res.targets] == ["a"]


def test_regime_no_match_returns_empty():
    reg = _registry(_entry("a", regime="gdpr-15", alt_regimes=None))
    res = resolve_targets(
        TargetQuery(jurisdiction="usa", regime="maritime-prize-disclosure"), reg)
    assert res.targets == ()
    assert res.is_legal_opinion is False  # still never an opinion, even when empty


def test_none_regime_returns_all_in_jurisdiction():
    reg = _registry(_entry("a", regime="gdpr-15"), _entry("b", regime="ccpa-110"))
    res = resolve_targets(TargetQuery(jurisdiction="usa", regime=None), reg)
    assert len(res.targets) == 2


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_targets(
        TargetQuery(jurisdiction="usa", allow_unverified=False), reg)
    assert [t.organization for t in res.targets] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_targets(
        TargetQuery(jurisdiction="usa", allow_unverified=True), reg)
    assert [t.organization for t in res.targets] == ["seed"]


# ── validation (G8 — well-formed input only, no guessing) ───────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_targets(TargetQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_regime_raises(bad):
    with pytest.raises(ValueError):
        resolve_targets(
            TargetQuery(jurisdiction="usa", regime=bad), _registry(_entry("a")))


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_targets(TargetQuery(jurisdiction="usa"), reg)


def test_registry_without_targets_list_raises():
    with pytest.raises(ValueError):
        resolve_targets(TargetQuery(jurisdiction="usa"), {"targets": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"organization": "a", "jurisdiction": "usa"}  # no regime
    with pytest.raises(ValueError):
        resolve_targets(TargetQuery(jurisdiction="usa"), _registry(bad))


def test_bool_deadline_rejected():
    bad = _entry("a")
    bad["statutoryDeadlineDays"] = True
    with pytest.raises(ValueError):
        resolve_targets(TargetQuery(jurisdiction="usa"), _registry(bad))


# ── integration: drive the worldwide disclosure-target seed registry ────


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {t["jurisdiction"] for t in data["targets"]}
    assert len(data["targets"]) >= 50  # worldwide, not single-jurisdiction
    assert len(juris) >= 30  # many distinct jurisdictions
    assert "usa" in juris and "jpn" in juris and "eu-wide" in juris


def test_registry_usa_routes_sorted_and_routing_only():
    data = load_registry(_REGISTRY)
    res = resolve_targets(TargetQuery(jurisdiction="usa"), data)
    assert len(res.targets) == 9  # 9 usa entries in the seed
    ranks = [
        (t.confidence if t.confidence else "zzz") for t in res.targets
    ]
    # confidence-rank non-decreasing (graded first, ungraded last)
    from .target_resolver import _confidence_rank
    rkeys = [_confidence_rank(t.confidence) for t in res.targets]
    assert rkeys == sorted(rkeys)
    assert all(t.is_legal_opinion is False for t in res.targets)


def test_registry_twn_high_before_medium_real_seed():
    # twn carries two graded entries: medium pdpa-tw-3 + high foia-tw-fgil.
    data = load_registry(_REGISTRY)
    res = resolve_targets(TargetQuery(jurisdiction="twn"), data)
    assert len(res.targets) == 2
    assert res.targets[0].confidence == "high"  # high leads
    assert res.targets[1].confidence == "medium"


def test_registry_usa_regime_narrows_to_ccpa():
    data = load_registry(_REGISTRY)
    res = resolve_targets(TargetQuery(jurisdiction="usa", regime="ccpa-110"), data)
    orgs = {t.organization for t in res.targets}
    # Discord/Google/Meta carry ccpa-110 primary; CA CCPA business entry too
    assert any("Discord" in o for o in orgs)
    assert all(t.jurisdiction == "usa" for t in res.targets)
    # every result actually carries the requested regime (primary or alt)
    for t in res.targets:
        assert t.regime == "ccpa-110" or "ccpa-110" in t.alt_regimes


def test_registry_gdpr_alt_regime_routing_real_seed():
    # jpn LY Corporation (LINE) is regime appi-33 with gdpr-15 in altRegimes.
    data = load_registry(_REGISTRY)
    res = resolve_targets(TargetQuery(jurisdiction="jpn", regime="gdpr-15"), data)
    orgs = {t.organization for t in res.targets}
    assert any("LY Corporation" in o for o in orgs)
    for t in res.targets:
        assert t.regime == "gdpr-15" or "gdpr-15" in t.alt_regimes


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_targets(TargetQuery(jurisdiction="zz-atlantis"), data)
    assert res.targets == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_targets(TargetQuery(jurisdiction="usa"), data)
    rec = to_target_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["isLegalOpinion"] is False
    assert rec["isEligibilityDetermination"] is False
    assert rec["isDeadlineComputation"] is False
    assert rec["targetCount"] == len(res.targets) == 9
    assert rec["sessionRef"] == "at://session/1"
    # every surfaced target is a routing view (channel + provenance), not advice
    for view in rec["targets"]:
        assert "portalUrl" in view and "provenance" in view and "channelType" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
