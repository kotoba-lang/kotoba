"""Tests for the kazaori disaster-agency DIRECTORY resolver pure core (ADR-2605263200).

Locks the constitutional invariants (issues no alerts, commands no response,
not an official emergency service, civilian-only G5), the registry-confidence-
then-title sort, jurisdiction filtering, optional free-text hazard filtering,
optional agency-kind filtering, the empty-result-on-unknown rule, and
integration against the worldwide disaster-agency seed registry. Pure stdlib,
deterministic, no network — runs in CI.

These do NOT import ``.cell`` (the deployable Pregel graph, which stays
non-deployable until Council ratification); the pure core lives in
``.agency_match`` precisely so it is testable without activating the cell.

Run (this machine has an entrypoint pytest plugin that pulls a broken pydantic):
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_agency_match.py -q
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .agency_match import (
    AGENCY_KINDS,
    CONFIDENCE_ORDER,
    AgencyQuery,
    DisasterAgency,
    load_registry,
    resolve_agencies,
    to_agency_routing_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/kazaori/registry/agencies.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(aid, *, jurisdiction="jpn", confidence="high", title="Agency",
           kind="disaster-management-agency", status="unverified-seed",
           hazards="", alert_channel="", organization="", notes=""):
    return {
        "agencyId": aid,
        "title": title,
        "jurisdiction": jurisdiction,
        "agencyKind": kind,
        "confidence": confidence,
        "verificationStatus": status,
        "organization": organization,
        "accessUrl": "https://example.test",
        "hazards": hazards,
        "alertChannel": alert_channel,
        "language": "ja",
        "provenance": "https://example.test",
        "lastVerified": "2026-06-02T00:00:00Z",
        "notes": notes,
    }


def _registry(*entries):
    return {"$schema": "com.etzhayyim.kazaori.disasterAgency", "agencies": list(entries)}


# ── invariants: issues no alerts / commands no response / not 119 ───────


@pytest.mark.parametrize("hazard", [None, "flood", "earthquake", "no-such-hazard"])
def test_result_never_issues_alerts(hazard):
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn", hazard=hazard), _registry(_entry("a")))
    assert res.issues_alerts is False
    assert res.commands_response is False
    assert res.is_official_emergency_service is False


@pytest.mark.parametrize("confidence", sorted(CONFIDENCE_ORDER))
def test_every_agency_pins_invariants_false(confidence):
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), _registry(_entry("a", confidence=confidence)))
    assert all(a.issues_alerts is False for a in res.agencies)
    assert all(a.commands_response is False for a in res.agencies)
    assert all(a.is_official_emergency_service is False for a in res.agencies)


def test_record_invariants_always_false():
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn", hazard="tsunami"), _registry(_entry("a")))
    rec = to_agency_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["issuesAlerts"] is False
    assert rec["commandsResponse"] is False
    assert rec["isOfficialEmergencyService"] is False
    assert rec["civilianOnly"] is True
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["hazardLabel"] == "tsunami"


def test_record_no_compensation_field_leaks():
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), _registry(_entry("a")))
    rec = to_agency_routing_record(
        res, member_did="did:web:m", created_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert not ({"fee", "price", "amount", "tithe", "cost"} & set(rec))


# ── civilian-only (G5): non-civilian kind is structurally unroutable ────


def test_non_civilian_agency_kind_raises():
    bad = _entry("mil", kind="armed-force-command")
    with pytest.raises(ValueError):
        resolve_agencies(AgencyQuery(jurisdiction="jpn"), _registry(bad))


def test_all_known_kinds_are_civilian_and_routable():
    reg = _registry(*[_entry(k, kind=k) for k in AGENCY_KINDS])
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), reg)
    assert {a.agency_kind for a in res.agencies} == AGENCY_KINDS


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_agencies(AgencyQuery(jurisdiction="zz-nowhere"), reg)
    assert res.agencies == ()
    assert res.issues_alerts is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), reg)
    assert {a.agency_id for a in res.agencies} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="intl-ocha"))
    res = resolve_agencies(AgencyQuery(jurisdiction="INTL-OCHA"), reg)
    assert [a.agency_id for a in res.agencies] == ["a"]
    assert res.jurisdiction == "intl-ocha"


# ── sort: confidence then title, registry's OWN signal only ─────────────


def test_sort_high_before_medium():
    reg = _registry(
        _entry("med", confidence="medium", title="AAA"),
        _entry("hi", confidence="high", title="ZZZ"),
    )
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), reg)
    assert [a.agency_id for a in res.agencies] == ["hi", "med"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", title="bravo agency"),
        _entry("a", title="Alpha Agency"),
        _entry("c", title="Charlie"),
    )
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), reg)
    assert [a.title for a in res.agencies] == ["Alpha Agency", "bravo agency", "Charlie"]


def test_full_confidence_ordering_high_medium_low():
    reg = _registry(
        _entry("lo", confidence="low", title="A"),
        _entry("hi", confidence="high", title="A"),
        _entry("med", confidence="medium", title="A"),
    )
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), reg)
    assert [a.confidence for a in res.agencies] == ["high", "medium", "low"]


# ── optional free-text hazard filter (wayfinding only) ──────────────────


def test_hazard_label_filters_by_substring():
    reg = _registry(
        _entry("flood", hazards="riverine and flash flood"),
        _entry("quake", hazards="earthquake and tsunami"),
    )
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn", hazard="flood"), reg)
    assert [a.agency_id for a in res.agencies] == ["flood"]


def test_hazard_label_case_insensitive():
    reg = _registry(_entry("a", alert_channel="Volcanic Eruption alert feed"))
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn", hazard="VOLCANIC"), reg)
    assert [a.agency_id for a in res.agencies] == ["a"]


def test_hazard_no_match_returns_empty():
    reg = _registry(_entry("a", hazards="typhoon"))
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn", hazard="meteor-strike"), reg)
    assert res.agencies == ()
    assert res.issues_alerts is False


def test_none_hazard_returns_all_in_jurisdiction():
    reg = _registry(_entry("a"), _entry("b"))
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn", hazard=None), reg)
    assert len(res.agencies) == 2


# ── optional agency-kind filter ─────────────────────────────────────────


def test_agency_kind_filter_narrows():
    reg = _registry(
        _entry("a", kind="disaster-management-agency"),
        _entry("b", kind="early-warning-system"),
    )
    res = resolve_agencies(
        AgencyQuery(jurisdiction="jpn", agency_kind="early-warning-system"), reg)
    assert [a.agency_id for a in res.agencies] == ["b"]
    assert res.agency_kind == "early-warning-system"


def test_unknown_agency_kind_filter_raises():
    with pytest.raises(ValueError):
        resolve_agencies(
            AgencyQuery(jurisdiction="jpn", agency_kind="bogus-kind"),
            _registry(_entry("a")),
        )


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn", allow_unverified=False), reg)
    assert [a.agency_id for a in res.agencies] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn", allow_unverified=True), reg)
    assert [a.agency_id for a in res.agencies] == ["seed"]


# ── validation (well-formed input only, no guessing) ────────────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_agencies(AgencyQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_hazard_raises(bad):
    with pytest.raises(ValueError):
        resolve_agencies(
            AgencyQuery(jurisdiction="jpn", hazard=bad), _registry(_entry("a")))


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_agencies(AgencyQuery(jurisdiction="jpn"), reg)


def test_registry_without_agencies_list_raises():
    with pytest.raises(ValueError):
        resolve_agencies(AgencyQuery(jurisdiction="jpn"), {"agencies": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"agencyId": "a", "jurisdiction": "jpn", "confidence": "high",
           "agencyKind": "disaster-management-agency"}  # no title
    with pytest.raises(ValueError):
        resolve_agencies(AgencyQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass invariant pin cannot be flipped ────────────────────


def test_agency_is_frozen_invariants_immutable():
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), _registry(_entry("a")))
    a = res.agencies[0]
    assert isinstance(a, DisasterAgency)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        a.issues_alerts = True  # type: ignore[misc]


# ── integration: drive the worldwide disaster-agency seed registry ──────


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {a["jurisdiction"] for a in data["agencies"]}
    assert len(data["agencies"]) >= 100  # worldwide, not JP-only
    assert len(juris) >= 20  # many distinct jurisdictions
    assert "jpn" in juris


def test_registry_every_seed_entry_is_civilian_and_projectable():
    """The whole seed must project without raising — i.e. every entry's kind is
    one of the known CIVILIAN kinds (no military entry slipped in)."""
    data = load_registry(_REGISTRY)
    juris = {a["jurisdiction"] for a in data["agencies"]}
    total = 0
    for j in juris:
        res = resolve_agencies(AgencyQuery(jurisdiction=j), data)
        total += len(res.agencies)
        assert all(a.agency_kind in AGENCY_KINDS for a in res.agencies)
    assert total == len(data["agencies"])  # nothing dropped, nothing raised


def test_registry_jpn_routes_sorted_high_first():
    data = load_registry(_REGISTRY)
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), data)
    assert len(res.agencies) == 4  # 4 real jpn entries in the seed
    ranks = [CONFIDENCE_ORDER[a.confidence] for a in res.agencies]
    assert ranks == sorted(ranks)  # non-decreasing confidence rank
    assert res.agencies[0].confidence == "high"
    ids = {a.agency_id for a in res.agencies}
    assert "jpn-jma-emergency-warning" in ids
    assert all(a.issues_alerts is False for a in res.agencies)


def test_registry_jpn_early_warning_kind_narrows_to_jma():
    data = load_registry(_REGISTRY)
    res = resolve_agencies(
        AgencyQuery(jurisdiction="jpn", agency_kind="early-warning-system"), data)
    ids = {a.agency_id for a in res.agencies}
    assert "jpn-jma-emergency-warning" in ids
    assert all(a.agency_kind == "early-warning-system" for a in res.agencies)


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_agencies(AgencyQuery(jurisdiction="zz-atlantis"), data)
    assert res.agencies == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_agencies(AgencyQuery(jurisdiction="jpn"), data)
    rec = to_agency_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["issuesAlerts"] is False
    assert rec["commandsResponse"] is False
    assert rec["isOfficialEmergencyService"] is False
    assert rec["agencyCount"] == len(res.agencies) == 4
    assert rec["sessionRef"] == "at://session/1"
    for view in rec["agencies"]:
        assert "accessUrl" in view and "provenance" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
