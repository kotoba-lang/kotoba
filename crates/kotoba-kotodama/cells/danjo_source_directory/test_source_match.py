"""Tests for the danjo fiscal-source DIRECTORY resolver pure core (ADR-2605301600).

Locks the constitutional invariants (non-adjudicating — censor's eye no sword,
asserts no wrongdoing), the registry-confidence-then-title sort, jurisdiction
filtering, optional free-text topic filtering, optional source-kind filtering,
the empty-result-on-unknown rule, and integration against the worldwide
fiscal-source seed registry. Pure stdlib, deterministic, no network.

These do NOT import ``.cell`` (the deployable Pregel graph, which stays
non-deployable until Council ratification); the pure core lives in
``.source_match`` precisely so it is testable without activating the cell.

Run (this machine has an entrypoint pytest plugin that pulls a broken pydantic):
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_source_match.py -q
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .source_match import (
    CONFIDENCE_ORDER,
    SOURCE_KINDS,
    FiscalSource,
    SourceQuery,
    load_registry,
    resolve_sources,
    to_source_routing_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/danjo/registry/sources.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(sid, *, jurisdiction="jpn", confidence="high", title="Source",
           kind="budget-portal", status="unverified-seed", authority="",
           fmt="CSV", legal_basis="", notes=""):
    return {
        "sourceId": sid,
        "title": title,
        "jurisdiction": jurisdiction,
        "sourceKind": kind,
        "confidence": confidence,
        "verificationStatus": status,
        "authority": authority,
        "datasetUrl": "https://example.test",
        "format": fmt,
        "legalBasis": legal_basis,
        "language": "ja",
        "provenance": "https://example.test",
        "lastVerified": "2026-06-02T00:00:00Z",
        "notes": notes,
    }


def _registry(*entries):
    return {"$schema": "com.etzhayyim.danjo.fiscalSource", "sources": list(entries)}


# ── invariants: non-adjudicating / asserts no wrongdoing ────────────────


@pytest.mark.parametrize("topic", [None, "budget", "audit", "no-such-topic"])
def test_result_pins_invariants_false(topic):
    res = resolve_sources(SourceQuery(jurisdiction="jpn", topic=topic), _registry(_entry("a")))
    assert res.is_adjudication is False
    assert res.asserts_wrongdoing is False


@pytest.mark.parametrize("confidence", sorted(CONFIDENCE_ORDER))
def test_every_source_pins_invariants_false(confidence):
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), _registry(_entry("a", confidence=confidence)))
    assert all(s.is_adjudication is False for s in res.sources)
    assert all(s.asserts_wrongdoing is False for s in res.sources)


def test_record_invariants_always_false():
    res = resolve_sources(SourceQuery(jurisdiction="jpn", topic="audit"), _registry(_entry("a")))
    rec = to_source_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isAdjudication"] is False
    assert rec["assertsWrongdoing"] is False
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["topicLabel"] == "audit"


def test_record_no_compensation_field_leaks():
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), _registry(_entry("a")))
    rec = to_source_routing_record(
        res, member_did="did:web:m", created_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert not ({"fee", "price", "amount", "tithe", "cost"} & set(rec))


# ── unknown sourceKind is structurally unroutable ───────────────────────


def test_unknown_source_kind_in_registry_raises():
    bad = _entry("x", kind="anonymous-tip-line")
    with pytest.raises(ValueError):
        resolve_sources(SourceQuery(jurisdiction="jpn"), _registry(bad))


def test_all_known_kinds_are_routable():
    reg = _registry(*[_entry(k, kind=k) for k in SOURCE_KINDS])
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), reg)
    assert {s.source_kind for s in res.sources} == SOURCE_KINDS


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_sources(SourceQuery(jurisdiction="zz-nowhere"), reg)
    assert res.sources == ()
    assert res.is_adjudication is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), reg)
    assert {s.source_id for s in res.sources} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="intl-oecd"))
    res = resolve_sources(SourceQuery(jurisdiction="INTL-OECD"), reg)
    assert [s.source_id for s in res.sources] == ["a"]
    assert res.jurisdiction == "intl-oecd"


# ── sort: confidence then title, registry's OWN signal only ─────────────


def test_sort_high_before_medium():
    reg = _registry(
        _entry("med", confidence="medium", title="AAA"),
        _entry("hi", confidence="high", title="ZZZ"),
    )
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), reg)
    assert [s.source_id for s in res.sources] == ["hi", "med"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", title="bravo portal"),
        _entry("a", title="Alpha Portal"),
        _entry("c", title="Charlie"),
    )
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), reg)
    assert [s.title for s in res.sources] == ["Alpha Portal", "bravo portal", "Charlie"]


def test_full_confidence_ordering_high_medium_low():
    reg = _registry(
        _entry("lo", confidence="low", title="A"),
        _entry("hi", confidence="high", title="A"),
        _entry("med", confidence="medium", title="A"),
    )
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), reg)
    assert [s.confidence for s in res.sources] == ["high", "medium", "low"]


# ── optional free-text topic filter (wayfinding only) ───────────────────


def test_topic_label_filters_by_substring():
    reg = _registry(
        _entry("proc", legal_basis="public procurement act"),
        _entry("aud", authority="Board of Audit"),
    )
    res = resolve_sources(SourceQuery(jurisdiction="jpn", topic="procurement"), reg)
    assert [s.source_id for s in res.sources] == ["proc"]


def test_topic_label_case_insensitive():
    reg = _registry(_entry("a", authority="Ministry of Finance"))
    res = resolve_sources(SourceQuery(jurisdiction="jpn", topic="FINANCE"), reg)
    assert [s.source_id for s in res.sources] == ["a"]


def test_topic_no_match_returns_empty():
    reg = _registry(_entry("a", authority="Board of Audit"))
    res = resolve_sources(SourceQuery(jurisdiction="jpn", topic="weather-data"), reg)
    assert res.sources == ()
    assert res.is_adjudication is False


def test_none_topic_returns_all_in_jurisdiction():
    reg = _registry(_entry("a"), _entry("b"))
    res = resolve_sources(SourceQuery(jurisdiction="jpn", topic=None), reg)
    assert len(res.sources) == 2


# ── optional source-kind filter ─────────────────────────────────────────


def test_source_kind_filter_narrows():
    reg = _registry(
        _entry("a", kind="budget-portal"),
        _entry("b", kind="audit-institution"),
    )
    res = resolve_sources(
        SourceQuery(jurisdiction="jpn", source_kind="audit-institution"), reg)
    assert [s.source_id for s in res.sources] == ["b"]
    assert res.source_kind == "audit-institution"


def test_unknown_source_kind_filter_raises():
    with pytest.raises(ValueError):
        resolve_sources(
            SourceQuery(jurisdiction="jpn", source_kind="bogus-kind"),
            _registry(_entry("a")),
        )


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_sources(SourceQuery(jurisdiction="jpn", allow_unverified=False), reg)
    assert [s.source_id for s in res.sources] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_sources(SourceQuery(jurisdiction="jpn", allow_unverified=True), reg)
    assert [s.source_id for s in res.sources] == ["seed"]


# ── validation (well-formed input only, no guessing) ────────────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_sources(SourceQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_topic_raises(bad):
    with pytest.raises(ValueError):
        resolve_sources(
            SourceQuery(jurisdiction="jpn", topic=bad), _registry(_entry("a")))


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_sources(SourceQuery(jurisdiction="jpn"), reg)


def test_registry_without_sources_list_raises():
    with pytest.raises(ValueError):
        resolve_sources(SourceQuery(jurisdiction="jpn"), {"sources": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"sourceId": "a", "jurisdiction": "jpn", "confidence": "high",
           "sourceKind": "budget-portal"}  # no title
    with pytest.raises(ValueError):
        resolve_sources(SourceQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass invariant pin cannot be flipped ────────────────────


def test_source_is_frozen_invariants_immutable():
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), _registry(_entry("a")))
    s = res.sources[0]
    assert isinstance(s, FiscalSource)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        s.is_adjudication = True  # type: ignore[misc]


# ── integration: drive the worldwide fiscal-source seed registry ────────


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {s["jurisdiction"] for s in data["sources"]}
    assert len(data["sources"]) >= 100  # worldwide, not JP-only
    assert len(juris) >= 20  # many distinct jurisdictions
    assert "jpn" in juris


def test_registry_every_seed_entry_projects_known_kind():
    """The whole seed must project without raising — every entry's sourceKind
    is one of the known kinds (no unknown source slipped in)."""
    data = load_registry(_REGISTRY)
    juris = {s["jurisdiction"] for s in data["sources"]}
    total = 0
    for j in juris:
        res = resolve_sources(SourceQuery(jurisdiction=j), data)
        total += len(res.sources)
        assert all(s.source_kind in SOURCE_KINDS for s in res.sources)
    assert total == len(data["sources"])  # nothing dropped, nothing raised


def test_registry_jpn_routes_sorted_high_first_with_mof_anchor():
    data = load_registry(_REGISTRY)
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), data)
    assert len(res.sources) == 6  # 6 real jpn entries in the seed
    ranks = [CONFIDENCE_ORDER[s.confidence] for s in res.sources]
    assert ranks == sorted(ranks)  # non-decreasing confidence rank
    ids = {s.source_id for s in res.sources}
    assert "jpn-budget-mof-bb" in ids
    assert all(s.is_adjudication is False for s in res.sources)


def test_registry_jpn_audit_kind_narrows_to_board_of_audit():
    data = load_registry(_REGISTRY)
    res = resolve_sources(
        SourceQuery(jurisdiction="jpn", source_kind="audit-institution"), data)
    ids = {s.source_id for s in res.sources}
    assert "jpn-audit-jbaudit" in ids
    assert all(s.source_kind == "audit-institution" for s in res.sources)


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_sources(SourceQuery(jurisdiction="zz-atlantis"), data)
    assert res.sources == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_sources(SourceQuery(jurisdiction="jpn"), data)
    rec = to_source_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["isAdjudication"] is False
    assert rec["assertsWrongdoing"] is False
    assert rec["sourceCount"] == len(res.sources) == 6
    assert rec["sessionRef"] == "at://session/1"
    for view in rec["sources"]:
        assert "datasetUrl" in view and "provenance" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
