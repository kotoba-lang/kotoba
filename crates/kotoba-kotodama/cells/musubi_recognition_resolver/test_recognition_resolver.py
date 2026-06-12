"""Tests for the musubi ceremony CIVIL-RECOGNITION RESOLVER pure core (ADR-2605263400).

Locks the G-invariants (never a legal opinion, never confers civil status, never
an eligibility determination), the registry-confidence-then-title sort,
jurisdiction filtering, optional ceremony-type filtering, the empty-result-on-
unknown rule, and integration against the worldwide ceremony-recognition seed
registry. Pure stdlib, deterministic, no network — runs in CI.

These do NOT import ``.cell`` (the deployable Pregel graph, which stays
non-deployable until Council ratification); the pure core lives in
``.recognition_resolver`` precisely so it is testable without activating the cell.

BOUNDARY under test: musubi performs covenant ceremonies (Reformed 万人祭司, NO
clergy class) and does NOT confer civil status. The resolver is INFORMATIONAL
routing only — it surfaces where a separate civil step is required; it gives NO
legal advice and NEVER claims to register a civil marriage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .recognition_resolver import (
    CONFIDENCE_ORDER,
    Recognition,
    RecognitionQuery,
    resolve_recognitions,
    to_recognition_routing_record,
    load_registry,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/musubi/registry/ceremony-recognition.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(rid, *, jurisdiction="jpn", confidence="high", title="Rite",
           ceremony_type="marriage", status="unverified-seed", notes="",
           legal_basis="", authority="", channel=""):
    return {
        "recognitionId": rid,
        "title": title,
        "jurisdiction": jurisdiction,
        "ceremonyType": ceremony_type,
        "confidence": confidence,
        "verificationStatus": status,
        "authority": authority,
        "channel": channel,
        "legalBasis": legal_basis,
        "language": "ja",
        "notes": notes,
        "lastVerified": "2026-06-02T00:00:00Z",
        "provenance": "https://example.test",
    }


def _registry(*entries):
    return {
        "$schema": "com.etzhayyim.musubi.ceremonyRecognition",
        "recognitions": list(entries),
    }


# ── G-invariants: never legal opinion, never confers civil status ───────


@pytest.mark.parametrize("ceremony", [None, "marriage", "naming", "no-such-type"])
def test_g_invariant_result_never_legal_opinion_or_civil_status(ceremony):
    reg = _registry(_entry("a"))
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", ceremony_type=ceremony), reg)
    assert res.is_legal_opinion is False
    assert res.confers_civil_status is False


@pytest.mark.parametrize("confidence", sorted(CONFIDENCE_ORDER))
def test_g_invariant_every_recognition_pins_false(confidence):
    reg = _registry(_entry("a", confidence=confidence))
    res = resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), reg)
    assert all(r.is_legal_opinion is False for r in res.recognitions)
    assert all(r.confers_civil_status is False for r in res.recognitions)


def test_g_invariant_record_pins_always_false():
    reg = _registry(_entry("a", title="Kon'in-todoke"))
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", ceremony_type="marriage"), reg)
    rec = to_recognition_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isLegalOpinion"] is False
    assert rec["confersCivilStatus"] is False
    assert rec["isEligibilityDetermination"] is False
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["ceremonyTypeLabel"] == "marriage"


def test_g_invariant_no_civil_status_claim_field_leaks():
    reg = _registry(_entry("a"))
    res = resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), reg)
    rec = to_recognition_routing_record(
        res, member_did="did:web:m",
        created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )
    # no field implying musubi itself registered/granted a civil status
    assert not ({"registered", "married", "civilStatus", "granted"} & set(rec))


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_recognitions(RecognitionQuery(jurisdiction="zz-nowhere"), reg)
    assert res.recognitions == ()
    assert res.is_legal_opinion is False
    assert res.confers_civil_status is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), reg)
    assert {r.recognition_id for r in res.recognitions} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="eu-wide"))
    res = resolve_recognitions(RecognitionQuery(jurisdiction="EU-Wide"), reg)
    assert [r.recognition_id for r in res.recognitions] == ["a"]
    assert res.jurisdiction == "eu-wide"


# ── sort: confidence then title, registry's OWN signal only ─────────────


def test_sort_high_before_medium():
    reg = _registry(
        _entry("med", confidence="medium", title="AAA"),
        _entry("hi", confidence="high", title="ZZZ"),
    )
    res = resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), reg)
    assert [r.recognition_id for r in res.recognitions] == ["hi", "med"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", confidence="high", title="bravo rite"),
        _entry("a", confidence="high", title="Alpha Rite"),
        _entry("c", confidence="high", title="Charlie"),
    )
    res = resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), reg)
    assert [r.title for r in res.recognitions] == ["Alpha Rite", "bravo rite", "Charlie"]


def test_full_confidence_ordering_high_medium_low():
    reg = _registry(
        _entry("lo", confidence="low", title="A"),
        _entry("hi", confidence="high", title="A"),
        _entry("med", confidence="medium", title="A"),
    )
    res = resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), reg)
    assert [r.confidence for r in res.recognitions] == ["high", "medium", "low"]


# ── optional ceremony-type secondary filter ─────────────────────────────


def test_ceremony_type_filters_to_matching_only():
    reg = _registry(
        _entry("m", ceremony_type="marriage"),
        _entry("n", ceremony_type="naming"),
        _entry("f", ceremony_type="funeral"),
    )
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", ceremony_type="naming"), reg)
    assert [r.recognition_id for r in res.recognitions] == ["n"]


def test_ceremony_type_filter_is_case_insensitive():
    reg = _registry(_entry("a", ceremony_type="marriage"))
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", ceremony_type="MARRIAGE"), reg)
    assert [r.recognition_id for r in res.recognitions] == ["a"]


def test_ceremony_type_no_match_returns_empty():
    reg = _registry(_entry("a", ceremony_type="marriage"))
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", ceremony_type="coronation"), reg)
    assert res.recognitions == ()
    assert res.is_legal_opinion is False  # still never opinion, even when empty
    assert res.confers_civil_status is False


def test_none_ceremony_type_returns_all_in_jurisdiction():
    reg = _registry(
        _entry("a", ceremony_type="marriage"),
        _entry("b", ceremony_type="funeral"),
    )
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", ceremony_type=None), reg)
    assert len(res.recognitions) == 2


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", allow_unverified=False), reg)
    assert [r.recognition_id for r in res.recognitions] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", allow_unverified=True), reg)
    assert [r.recognition_id for r in res.recognitions] == ["seed"]


# ── validation (G8 — well-formed input only, no guessing) ───────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_recognitions(RecognitionQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_ceremony_type_raises(bad):
    with pytest.raises(ValueError):
        resolve_recognitions(
            RecognitionQuery(jurisdiction="jpn", ceremony_type=bad),
            _registry(_entry("a")),
        )


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), reg)


def test_registry_without_recognitions_list_raises():
    with pytest.raises(ValueError):
        resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), {"recognitions": "nope"})


def test_entry_missing_required_field_raises():
    # no title
    bad = {"recognitionId": "a", "jurisdiction": "jpn", "ceremonyType": "marriage",
           "confidence": "high"}
    with pytest.raises(ValueError):
        resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass G-invariant pin cannot be flipped ──────────────────


def test_recognition_is_frozen_pins_immutable():
    reg = _registry(_entry("a"))
    res = resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), reg)
    r = res.recognitions[0]
    assert isinstance(r, Recognition)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        r.confers_civil_status = True  # type: ignore[misc]
    with pytest.raises(Exception):
        r.is_legal_opinion = True  # type: ignore[misc]


# ── integration: drive the worldwide ceremony-recognition seed registry ──


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {r["jurisdiction"] for r in data["recognitions"]}
    assert len(data["recognitions"]) >= 30  # worldwide, not JP-only
    assert len(juris) >= 20  # many distinct jurisdictions
    assert "jpn" in juris


def test_registry_jpn_routes_sorted_high_first():
    data = load_registry(_REGISTRY)
    res = resolve_recognitions(RecognitionQuery(jurisdiction="jpn"), data)
    assert len(res.recognitions) == 6  # 6 real jpn entries in the seed
    ranks = [CONFIDENCE_ORDER[r.confidence] for r in res.recognitions]
    assert ranks == sorted(ranks)  # non-decreasing confidence rank
    assert res.recognitions[0].confidence == "high"  # all-high group leads
    # known anchor entry is present + routed (not opined / not granted)
    ids = {r.recognition_id for r in res.recognitions}
    assert "jp-marriage-notification-konin-todoke" in ids
    assert all(r.is_legal_opinion is False for r in res.recognitions)
    assert all(r.confers_civil_status is False for r in res.recognitions)


def test_registry_jpn_marriage_label_narrows_to_marriage_entries():
    data = load_registry(_REGISTRY)
    res = resolve_recognitions(
        RecognitionQuery(jurisdiction="jpn", ceremony_type="marriage"), data)
    ids = {r.recognition_id for r in res.recognitions}
    assert "jp-marriage-notification-konin-todoke" in ids  # 婚姻届
    assert all(r.ceremony_type == "marriage" for r in res.recognitions)
    assert all(r.jurisdiction == "jpn" for r in res.recognitions)


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_recognitions(RecognitionQuery(jurisdiction="zz-atlantis"), data)
    assert res.recognitions == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_recognitions(RecognitionQuery(jurisdiction="usa"), data)
    rec = to_recognition_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["isLegalOpinion"] is False
    assert rec["confersCivilStatus"] is False
    assert rec["isEligibilityDetermination"] is False
    assert rec["recognitionCount"] == len(res.recognitions) == 7
    assert rec["sessionRef"] == "at://session/1"
    # every surfaced entry is a routing view, not an advice / civil-grant payload
    for view in rec["recognitions"]:
        assert "channel" in view and "provenance" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
