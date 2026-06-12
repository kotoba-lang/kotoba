"""Tests for the kokoro support-line DIRECTORY resolver pure core (ADR-2605263700).

Locks the constitutional invariants (renders no clinical opinion, not a
diagnosis, not a treatment), the registry-confidence-then-title sort,
jurisdiction filtering, optional free-text topic filtering, optional
support-kind filtering, the empty-result-on-unknown rule, and integration
against the worldwide support-line seed registry. Pure stdlib, deterministic,
no network — runs in CI.

These do NOT import ``.cell`` (the deployable Pregel graph, which stays
non-deployable until Council ratification); the pure core lives in
``.support_match`` precisely so it is testable without activating the cell.

Run (this machine has an entrypoint pytest plugin that pulls a broken pydantic):
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_support_match.py -q
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .support_match import (
    CONFIDENCE_ORDER,
    SUPPORT_KINDS,
    SupportLine,
    SupportQuery,
    load_registry,
    resolve_support_lines,
    to_support_routing_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/kokoro/registry/support-lines.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(lid, *, jurisdiction="jpn", confidence="high", title="Line",
           kind="crisis-hotline", status="unverified-seed", organization="",
           notes="", languages="ja"):
    return {
        "lineId": lid,
        "title": title,
        "jurisdiction": jurisdiction,
        "supportKind": kind,
        "confidence": confidence,
        "verificationStatus": status,
        "organization": organization,
        "contact": "0120-000-000",
        "hours": "24/7",
        "languages": languages,
        "cost": "free",
        "provenance": "https://example.test",
        "lastVerified": "2026-06-02T00:00:00Z",
        "notes": notes,
    }


def _registry(*entries):
    return {"$schema": "com.etzhayyim.kokoro.supportLine", "lines": list(entries)}


# ── invariants: no clinical opinion / not diagnosis / not treatment ─────


@pytest.mark.parametrize("topic", [None, "youth", "text", "no-such-topic"])
def test_result_never_renders_clinical_opinion(topic):
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn", topic=topic), _registry(_entry("a")))
    assert res.renders_clinical_opinion is False
    assert res.is_diagnosis is False
    assert res.is_treatment is False


@pytest.mark.parametrize("confidence", sorted(CONFIDENCE_ORDER))
def test_every_line_pins_invariants_false(confidence):
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), _registry(_entry("a", confidence=confidence)))
    assert all(ln.renders_clinical_opinion is False for ln in res.lines)
    assert all(ln.is_diagnosis is False for ln in res.lines)
    assert all(ln.is_treatment is False for ln in res.lines)


def test_record_invariants_always_false():
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn", topic="crisis"), _registry(_entry("a")))
    rec = to_support_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["rendersClinicalOpinion"] is False
    assert rec["isDiagnosis"] is False
    assert rec["isTreatment"] is False
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["topicLabel"] == "crisis"


def test_record_no_compensation_field_leaks():
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), _registry(_entry("a")))
    rec = to_support_routing_record(
        res, member_did="did:web:m", created_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert not ({"fee", "price", "amount", "tithe"} & set(rec))


# ── unknown supportKind is structurally unroutable ──────────────────────


def test_unknown_support_kind_in_registry_raises():
    bad = _entry("x", kind="ai-therapist")
    with pytest.raises(ValueError):
        resolve_support_lines(SupportQuery(jurisdiction="jpn"), _registry(bad))


def test_all_known_kinds_are_routable():
    reg = _registry(*[_entry(k, kind=k) for k in SUPPORT_KINDS])
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), reg)
    assert {ln.support_kind for ln in res.lines} == SUPPORT_KINDS


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_support_lines(SupportQuery(jurisdiction="zz-nowhere"), reg)
    assert res.lines == ()
    assert res.renders_clinical_opinion is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), reg)
    assert {ln.line_id for ln in res.lines} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="intl-iasp"))
    res = resolve_support_lines(SupportQuery(jurisdiction="INTL-IASP"), reg)
    assert [ln.line_id for ln in res.lines] == ["a"]
    assert res.jurisdiction == "intl-iasp"


# ── sort: confidence then title, registry's OWN signal only ─────────────


def test_sort_high_before_medium():
    reg = _registry(
        _entry("med", confidence="medium", title="AAA"),
        _entry("hi", confidence="high", title="ZZZ"),
    )
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), reg)
    assert [ln.line_id for ln in res.lines] == ["hi", "med"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", title="bravo line"),
        _entry("a", title="Alpha Line"),
        _entry("c", title="Charlie"),
    )
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), reg)
    assert [ln.title for ln in res.lines] == ["Alpha Line", "bravo line", "Charlie"]


def test_full_confidence_ordering_high_medium_low():
    reg = _registry(
        _entry("lo", confidence="low", title="A"),
        _entry("hi", confidence="high", title="A"),
        _entry("med", confidence="medium", title="A"),
    )
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), reg)
    assert [ln.confidence for ln in res.lines] == ["high", "medium", "low"]


# ── optional free-text topic filter (wayfinding only) ───────────────────


def test_topic_label_filters_by_substring():
    reg = _registry(
        _entry("youth", notes="for children and youth under 18"),
        _entry("adult", notes="general adult support"),
    )
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn", topic="youth"), reg)
    assert [ln.line_id for ln in res.lines] == ["youth"]


def test_topic_label_case_insensitive():
    reg = _registry(_entry("a", organization="Text Crisis Line"))
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn", topic="TEXT"), reg)
    assert [ln.line_id for ln in res.lines] == ["a"]


def test_topic_no_match_returns_empty():
    reg = _registry(_entry("a", notes="suicide prevention"))
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn", topic="quantum-physics"), reg)
    assert res.lines == ()
    assert res.renders_clinical_opinion is False


def test_none_topic_returns_all_in_jurisdiction():
    reg = _registry(_entry("a"), _entry("b"))
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn", topic=None), reg)
    assert len(res.lines) == 2


# ── optional support-kind filter ────────────────────────────────────────


def test_support_kind_filter_narrows():
    reg = _registry(
        _entry("a", kind="crisis-hotline"),
        _entry("b", kind="text-or-chat-line"),
    )
    res = resolve_support_lines(
        SupportQuery(jurisdiction="jpn", support_kind="text-or-chat-line"), reg)
    assert [ln.line_id for ln in res.lines] == ["b"]
    assert res.support_kind == "text-or-chat-line"


def test_unknown_support_kind_filter_raises():
    with pytest.raises(ValueError):
        resolve_support_lines(
            SupportQuery(jurisdiction="jpn", support_kind="bogus-kind"),
            _registry(_entry("a")),
        )


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn", allow_unverified=False), reg)
    assert [ln.line_id for ln in res.lines] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn", allow_unverified=True), reg)
    assert [ln.line_id for ln in res.lines] == ["seed"]


# ── validation (well-formed input only, no guessing) ────────────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_support_lines(SupportQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_topic_raises(bad):
    with pytest.raises(ValueError):
        resolve_support_lines(
            SupportQuery(jurisdiction="jpn", topic=bad), _registry(_entry("a")))


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_support_lines(SupportQuery(jurisdiction="jpn"), reg)


def test_registry_without_lines_list_raises():
    with pytest.raises(ValueError):
        resolve_support_lines(SupportQuery(jurisdiction="jpn"), {"lines": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"lineId": "a", "jurisdiction": "jpn", "confidence": "high",
           "supportKind": "crisis-hotline"}  # no title
    with pytest.raises(ValueError):
        resolve_support_lines(SupportQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass invariant pin cannot be flipped ────────────────────


def test_line_is_frozen_invariants_immutable():
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), _registry(_entry("a")))
    ln = res.lines[0]
    assert isinstance(ln, SupportLine)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        ln.renders_clinical_opinion = True  # type: ignore[misc]


# ── integration: drive the worldwide support-line seed registry ─────────


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {ln["jurisdiction"] for ln in data["lines"]}
    assert len(data["lines"]) >= 100  # worldwide, not JP-only
    assert len(juris) >= 20  # many distinct jurisdictions
    assert "jpn" in juris


def test_registry_every_seed_entry_projects_known_kind():
    """The whole seed must project without raising — every entry's supportKind
    is one of the known kinds (no unknown service slipped in)."""
    data = load_registry(_REGISTRY)
    juris = {ln["jurisdiction"] for ln in data["lines"]}
    total = 0
    for j in juris:
        res = resolve_support_lines(SupportQuery(jurisdiction=j), data)
        total += len(res.lines)
        assert all(ln.support_kind in SUPPORT_KINDS for ln in res.lines)
    assert total == len(data["lines"])  # nothing dropped, nothing raised


def test_registry_jpn_routes_sorted_high_first_with_emergency_anchor():
    data = load_registry(_REGISTRY)
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), data)
    assert len(res.lines) == 5  # 5 real jpn entries in the seed
    ranks = [CONFIDENCE_ORDER[ln.confidence] for ln in res.lines]
    assert ranks == sorted(ranks)  # non-decreasing confidence rank
    ids = {ln.line_id for ln in res.lines}
    assert "jpn-emergency-110-119" in ids
    assert all(ln.renders_clinical_opinion is False for ln in res.lines)


def test_registry_jpn_emergency_kind_narrows_to_110_119():
    data = load_registry(_REGISTRY)
    res = resolve_support_lines(
        SupportQuery(jurisdiction="jpn", support_kind="emergency-number"), data)
    ids = {ln.line_id for ln in res.lines}
    assert "jpn-emergency-110-119" in ids
    assert all(ln.support_kind == "emergency-number" for ln in res.lines)


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_support_lines(SupportQuery(jurisdiction="zz-atlantis"), data)
    assert res.lines == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_support_lines(SupportQuery(jurisdiction="jpn"), data)
    rec = to_support_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["rendersClinicalOpinion"] is False
    assert rec["isDiagnosis"] is False
    assert rec["isTreatment"] is False
    assert rec["lineCount"] == len(res.lines) == 5
    assert rec["sessionRef"] == "at://session/1"
    for view in rec["lines"]:
        assert "contact" in view and "provenance" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
