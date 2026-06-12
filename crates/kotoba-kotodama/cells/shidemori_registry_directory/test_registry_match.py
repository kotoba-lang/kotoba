"""Tests for the shidemori death-registration DIRECTORY resolver core (ADR-2605263800).

Locks the constitutional invariants (renders no advice — UPL boundary, not an
eligibility/obligation determination), the registry-confidence-then-title sort,
jurisdiction filtering, optional free-text topic filtering, optional
record-kind filtering, the empty-result-on-unknown rule, and integration
against the worldwide death-registration seed registry. Pure stdlib,
deterministic, no network — runs in CI.

These do NOT import ``.cell`` (the deployable Pregel graph, which stays
non-deployable until Council ratification); the pure core lives in
``.registry_match`` precisely so it is testable without activating the cell.

Run (this machine has an entrypoint pytest plugin that pulls a broken pydantic):
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_registry_match.py -q
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .registry_match import (
    CONFIDENCE_ORDER,
    RECORD_KINDS,
    RegistryQuery,
    RegistryRecord,
    load_registry,
    resolve_registries,
    to_registry_routing_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/shidemori/registry/registries.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(rid, *, jurisdiction="jpn", confidence="high", title="Office",
           kind="death-registration-authority", status="unverified-seed",
           authority="", procedure="", legal_basis="", notes=""):
    return {
        "registryId": rid,
        "title": title,
        "jurisdiction": jurisdiction,
        "recordKind": kind,
        "confidence": confidence,
        "verificationStatus": status,
        "authority": authority,
        "accessUrl": "https://example.test",
        "procedure": procedure,
        "deadline": "7 days",
        "legalBasis": legal_basis,
        "language": "ja",
        "provenance": "https://example.test",
        "lastVerified": "2026-06-02T00:00:00Z",
        "notes": notes,
    }


def _registry(*entries):
    return {"$schema": "com.etzhayyim.shidemori.deathRegistration", "registries": list(entries)}


# ── invariants: no advice / no eligibility determination ────────────────


@pytest.mark.parametrize("topic", [None, "cremation", "certificate", "no-such-topic"])
def test_result_never_renders_advice(topic):
    res = resolve_registries(RegistryQuery(jurisdiction="jpn", topic=topic), _registry(_entry("a")))
    assert res.renders_advice is False
    assert res.is_eligibility_determination is False


@pytest.mark.parametrize("confidence", sorted(CONFIDENCE_ORDER))
def test_every_record_pins_invariants_false(confidence):
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), _registry(_entry("a", confidence=confidence)))
    assert all(r.renders_advice is False for r in res.records)
    assert all(r.is_eligibility_determination is False for r in res.records)


def test_record_invariants_always_false():
    res = resolve_registries(RegistryQuery(jurisdiction="jpn", topic="permit"), _registry(_entry("a")))
    rec = to_registry_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["rendersAdvice"] is False
    assert rec["isEligibilityDetermination"] is False
    assert rec["zeroCompensation"] is True
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["topicLabel"] == "permit"


def test_record_no_compensation_field_leaks():
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), _registry(_entry("a")))
    rec = to_registry_routing_record(
        res, member_did="did:web:m", created_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert not ({"fee", "price", "amount", "tithe", "cost"} & set(rec))


# ── unknown recordKind is structurally unroutable ───────────────────────


def test_unknown_record_kind_in_registry_raises():
    bad = _entry("x", kind="astral-projection-permit")
    with pytest.raises(ValueError):
        resolve_registries(RegistryQuery(jurisdiction="jpn"), _registry(bad))


def test_all_known_kinds_are_routable():
    reg = _registry(*[_entry(k, kind=k) for k in RECORD_KINDS])
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), reg)
    assert {r.record_kind for r in res.records} == RECORD_KINDS


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_registries(RegistryQuery(jurisdiction="zz-nowhere"), reg)
    assert res.records == ()
    assert res.renders_advice is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), reg)
    assert {r.registry_id for r in res.records} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="intl-guidance"))
    res = resolve_registries(RegistryQuery(jurisdiction="INTL-Guidance"), reg)
    assert [r.registry_id for r in res.records] == ["a"]
    assert res.jurisdiction == "intl-guidance"


# ── sort: confidence then title, registry's OWN signal only ─────────────


def test_sort_high_before_medium():
    reg = _registry(
        _entry("med", confidence="medium", title="AAA"),
        _entry("hi", confidence="high", title="ZZZ"),
    )
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), reg)
    assert [r.registry_id for r in res.records] == ["hi", "med"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", title="bravo office"),
        _entry("a", title="Alpha Office"),
        _entry("c", title="Charlie"),
    )
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), reg)
    assert [r.title for r in res.records] == ["Alpha Office", "bravo office", "Charlie"]


def test_full_confidence_ordering_high_medium_low():
    reg = _registry(
        _entry("lo", confidence="low", title="A"),
        _entry("hi", confidence="high", title="A"),
        _entry("med", confidence="medium", title="A"),
    )
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), reg)
    assert [r.confidence for r in res.records] == ["high", "medium", "low"]


# ── optional free-text topic filter (wayfinding only) ───────────────────


def test_topic_label_filters_by_substring():
    reg = _registry(
        _entry("crem", procedure="apply for the cremation permit at the ward office"),
        _entry("cert", legal_basis="death certificate issuance act"),
    )
    res = resolve_registries(RegistryQuery(jurisdiction="jpn", topic="cremation"), reg)
    assert [r.registry_id for r in res.records] == ["crem"]


def test_topic_label_case_insensitive():
    reg = _registry(_entry("a", authority="Family Register Section"))
    res = resolve_registries(RegistryQuery(jurisdiction="jpn", topic="REGISTER"), reg)
    assert [r.registry_id for r in res.records] == ["a"]


def test_topic_no_match_returns_empty():
    reg = _registry(_entry("a", notes="burial permit"))
    res = resolve_registries(RegistryQuery(jurisdiction="jpn", topic="spaceflight"), reg)
    assert res.records == ()
    assert res.renders_advice is False


def test_none_topic_returns_all_in_jurisdiction():
    reg = _registry(_entry("a"), _entry("b"))
    res = resolve_registries(RegistryQuery(jurisdiction="jpn", topic=None), reg)
    assert len(res.records) == 2


# ── optional record-kind filter ─────────────────────────────────────────


def test_record_kind_filter_narrows():
    reg = _registry(
        _entry("a", kind="death-registration-authority"),
        _entry("b", kind="burial-cremation-permit"),
    )
    res = resolve_registries(
        RegistryQuery(jurisdiction="jpn", record_kind="burial-cremation-permit"), reg)
    assert [r.registry_id for r in res.records] == ["b"]
    assert res.record_kind == "burial-cremation-permit"


def test_unknown_record_kind_filter_raises():
    with pytest.raises(ValueError):
        resolve_registries(
            RegistryQuery(jurisdiction="jpn", record_kind="bogus-kind"),
            _registry(_entry("a")),
        )


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_registries(RegistryQuery(jurisdiction="jpn", allow_unverified=False), reg)
    assert [r.registry_id for r in res.records] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_registries(RegistryQuery(jurisdiction="jpn", allow_unverified=True), reg)
    assert [r.registry_id for r in res.records] == ["seed"]


# ── validation (well-formed input only, no guessing) ────────────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_registries(RegistryQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_topic_raises(bad):
    with pytest.raises(ValueError):
        resolve_registries(
            RegistryQuery(jurisdiction="jpn", topic=bad), _registry(_entry("a")))


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_registries(RegistryQuery(jurisdiction="jpn"), reg)


def test_registry_without_registries_list_raises():
    with pytest.raises(ValueError):
        resolve_registries(RegistryQuery(jurisdiction="jpn"), {"registries": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"registryId": "a", "jurisdiction": "jpn", "confidence": "high",
           "recordKind": "death-registration-authority"}  # no title
    with pytest.raises(ValueError):
        resolve_registries(RegistryQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass invariant pin cannot be flipped ────────────────────


def test_record_is_frozen_invariants_immutable():
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), _registry(_entry("a")))
    r = res.records[0]
    assert isinstance(r, RegistryRecord)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        r.renders_advice = True  # type: ignore[misc]


# ── integration: drive the worldwide death-registration seed registry ───


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {r["jurisdiction"] for r in data["registries"]}
    assert len(data["registries"]) >= 100  # worldwide, not JP-only
    assert len(juris) >= 20  # many distinct jurisdictions
    assert "jpn" in juris


def test_registry_every_seed_entry_projects_known_kind():
    """The whole seed must project without raising — every entry's recordKind
    is one of the known kinds (no unknown record type slipped in)."""
    data = load_registry(_REGISTRY)
    juris = {r["jurisdiction"] for r in data["registries"]}
    total = 0
    for j in juris:
        res = resolve_registries(RegistryQuery(jurisdiction=j), data)
        total += len(res.records)
        assert all(r.record_kind in RECORD_KINDS for r in res.records)
    assert total == len(data["registries"])  # nothing dropped, nothing raised


def test_registry_jpn_routes_sorted_high_first_with_koseki_anchor():
    data = load_registry(_REGISTRY)
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), data)
    assert len(res.records) == 4  # 4 real jpn entries in the seed
    ranks = [CONFIDENCE_ORDER[r.confidence] for r in res.records]
    assert ranks == sorted(ranks)  # non-decreasing confidence rank
    ids = {r.registry_id for r in res.records}
    assert "jpn-koseki-death-notification" in ids
    assert all(r.renders_advice is False for r in res.records)


def test_registry_jpn_permit_kind_narrows_to_cremation_permit():
    data = load_registry(_REGISTRY)
    res = resolve_registries(
        RegistryQuery(jurisdiction="jpn", record_kind="burial-cremation-permit"), data)
    ids = {r.registry_id for r in res.records}
    assert "jpn-kasou-kyokasho-permit" in ids
    assert all(r.record_kind == "burial-cremation-permit" for r in res.records)


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_registries(RegistryQuery(jurisdiction="zz-atlantis"), data)
    assert res.records == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_registries(RegistryQuery(jurisdiction="jpn"), data)
    rec = to_registry_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["rendersAdvice"] is False
    assert rec["isEligibilityDetermination"] is False
    assert rec["recordCount"] == len(res.records) == 4
    assert rec["sessionRef"] == "at://session/1"
    for view in rec["records"]:
        assert "authority" in view and "provenance" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
