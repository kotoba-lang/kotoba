"""Tests for the kataribe publication-channel DIRECTORY resolver core (ADR-2605263600).

Locks the constitutional invariants (not the original publisher, asserts no
content accuracy), the registry-confidence-then-title sort, jurisdiction
filtering, optional free-text topic filtering, optional channel-kind filtering,
the empty-result-on-unknown rule, and integration against the worldwide
publication-channel seed registry. Pure stdlib, deterministic, no network.

These do NOT import ``.cell`` (the deployable Pregel graph, which stays
non-deployable until Council ratification); the pure core lives in
``.channel_match`` precisely so it is testable without activating the cell.

Run (this machine has an entrypoint pytest plugin that pulls a broken pydantic):
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest test_channel_match.py -q
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from .channel_match import (
    CHANNEL_KINDS,
    CONFIDENCE_ORDER,
    ChannelQuery,
    PublicationChannel,
    load_registry,
    resolve_channels,
    to_channel_routing_record,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "20-actors/kataribe/registry/channels.seed.json"


# ── small in-memory registry fixtures (deterministic, no I/O) ───────────


def _entry(cid, *, jurisdiction="jpn", confidence="high", title="Channel",
           kind="official-gazette", status="unverified-seed", publisher="",
           content_type="", notes=""):
    return {
        "channelId": cid,
        "title": title,
        "jurisdiction": jurisdiction,
        "channelKind": kind,
        "confidence": confidence,
        "verificationStatus": status,
        "publisher": publisher,
        "accessUrl": "https://example.test",
        "contentType": content_type,
        "access": "open",
        "language": "ja",
        "provenance": "https://example.test",
        "lastVerified": "2026-06-02T00:00:00Z",
        "notes": notes,
    }


def _registry(*entries):
    return {"$schema": "com.etzhayyim.kataribe.publicationChannel", "channels": list(entries)}


# ── invariants: not original publisher / asserts no accuracy ────────────


@pytest.mark.parametrize("topic", [None, "laws", "gazette", "no-such-topic"])
def test_result_pins_invariants_false(topic):
    res = resolve_channels(ChannelQuery(jurisdiction="jpn", topic=topic), _registry(_entry("a")))
    assert res.is_original_publication is False
    assert res.asserts_content_accuracy is False


@pytest.mark.parametrize("confidence", sorted(CONFIDENCE_ORDER))
def test_every_channel_pins_invariants_false(confidence):
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), _registry(_entry("a", confidence=confidence)))
    assert all(c.is_original_publication is False for c in res.channels)
    assert all(c.asserts_content_accuracy is False for c in res.channels)


def test_record_invariants_always_false():
    res = resolve_channels(ChannelQuery(jurisdiction="jpn", topic="laws"), _registry(_entry("a")))
    rec = to_channel_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
    )
    assert rec["isOriginalPublication"] is False
    assert rec["assertsContentAccuracy"] is False
    assert rec["createdAt"] == "2026-06-03T12:00:00Z"
    assert rec["topicLabel"] == "laws"


def test_record_no_compensation_field_leaks():
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), _registry(_entry("a")))
    rec = to_channel_routing_record(
        res, member_did="did:web:m", created_at=datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert not ({"fee", "price", "amount", "tithe", "cost"} & set(rec))


# ── unknown channelKind is structurally unroutable ──────────────────────


def test_unknown_channel_kind_in_registry_raises():
    bad = _entry("x", kind="paywalled-tabloid")
    with pytest.raises(ValueError):
        resolve_channels(ChannelQuery(jurisdiction="jpn"), _registry(bad))


def test_all_known_kinds_are_routable():
    reg = _registry(*[_entry(k, kind=k) for k in CHANNEL_KINDS])
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), reg)
    assert {c.channel_kind for c in res.channels} == CHANNEL_KINDS


# ── jurisdiction filtering + empty-on-unknown ───────────────────────────


def test_unknown_jurisdiction_returns_empty_not_a_guess():
    reg = _registry(_entry("a", jurisdiction="jpn"), _entry("b", jurisdiction="usa"))
    res = resolve_channels(ChannelQuery(jurisdiction="zz-nowhere"), reg)
    assert res.channels == ()
    assert res.is_original_publication is False


def test_jurisdiction_filters_to_matching_only():
    reg = _registry(
        _entry("a", jurisdiction="jpn"),
        _entry("b", jurisdiction="usa"),
        _entry("c", jurisdiction="jpn"),
    )
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), reg)
    assert {c.channel_id for c in res.channels} == {"a", "c"}


def test_jurisdiction_match_is_case_insensitive():
    reg = _registry(_entry("a", jurisdiction="intl-rsf"))
    res = resolve_channels(ChannelQuery(jurisdiction="INTL-RSF"), reg)
    assert [c.channel_id for c in res.channels] == ["a"]
    assert res.jurisdiction == "intl-rsf"


# ── sort: confidence then title, registry's OWN signal only ─────────────


def test_sort_high_before_medium():
    reg = _registry(
        _entry("med", confidence="medium", title="AAA"),
        _entry("hi", confidence="high", title="ZZZ"),
    )
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), reg)
    assert [c.channel_id for c in res.channels] == ["hi", "med"]


def test_sort_ties_broken_by_title_case_insensitive():
    reg = _registry(
        _entry("b", title="bravo gazette"),
        _entry("a", title="Alpha Gazette"),
        _entry("c", title="Charlie"),
    )
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), reg)
    assert [c.title for c in res.channels] == ["Alpha Gazette", "bravo gazette", "Charlie"]


def test_full_confidence_ordering_high_medium_low():
    reg = _registry(
        _entry("lo", confidence="low", title="A"),
        _entry("hi", confidence="high", title="A"),
        _entry("med", confidence="medium", title="A"),
    )
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), reg)
    assert [c.confidence for c in res.channels] == ["high", "medium", "low"]


# ── optional free-text topic filter (wayfinding only) ───────────────────


def test_topic_label_filters_by_substring():
    reg = _registry(
        _entry("law", content_type="laws/case-law"),
        _entry("gaz", content_type="official-notices"),
    )
    res = resolve_channels(ChannelQuery(jurisdiction="jpn", topic="case-law"), reg)
    assert [c.channel_id for c in res.channels] == ["law"]


def test_topic_label_case_insensitive():
    reg = _registry(_entry("a", publisher="National Printing Bureau"))
    res = resolve_channels(ChannelQuery(jurisdiction="jpn", topic="PRINTING"), reg)
    assert [c.channel_id for c in res.channels] == ["a"]


def test_topic_no_match_returns_empty():
    reg = _registry(_entry("a", content_type="laws"))
    res = resolve_channels(ChannelQuery(jurisdiction="jpn", topic="sports-scores"), reg)
    assert res.channels == ()
    assert res.is_original_publication is False


def test_none_topic_returns_all_in_jurisdiction():
    reg = _registry(_entry("a"), _entry("b"))
    res = resolve_channels(ChannelQuery(jurisdiction="jpn", topic=None), reg)
    assert len(res.channels) == 2


# ── optional channel-kind filter ────────────────────────────────────────


def test_channel_kind_filter_narrows():
    reg = _registry(
        _entry("a", kind="official-gazette"),
        _entry("b", kind="translation-resource"),
    )
    res = resolve_channels(
        ChannelQuery(jurisdiction="jpn", channel_kind="translation-resource"), reg)
    assert [c.channel_id for c in res.channels] == ["b"]
    assert res.channel_kind == "translation-resource"


def test_unknown_channel_kind_filter_raises():
    with pytest.raises(ValueError):
        resolve_channels(
            ChannelQuery(jurisdiction="jpn", channel_kind="bogus-kind"),
            _registry(_entry("a")),
        )


# ── allow_unverified gate (caller policy, boundary edge) ────────────────


def test_allow_unverified_false_drops_seed_entries():
    reg = _registry(
        _entry("seed", status="unverified-seed"),
        _entry("ok", status="council-verified"),
    )
    res = resolve_channels(ChannelQuery(jurisdiction="jpn", allow_unverified=False), reg)
    assert [c.channel_id for c in res.channels] == ["ok"]


def test_allow_unverified_true_keeps_seed_entries():
    reg = _registry(_entry("seed", status="unverified-seed"))
    res = resolve_channels(ChannelQuery(jurisdiction="jpn", allow_unverified=True), reg)
    assert [c.channel_id for c in res.channels] == ["seed"]


# ── validation (well-formed input only, no guessing) ────────────────────


@pytest.mark.parametrize("bad", ["", "   ", None, 7])
def test_blank_or_nonstring_jurisdiction_raises(bad):
    with pytest.raises(ValueError):
        resolve_channels(ChannelQuery(jurisdiction=bad), _registry(_entry("a")))


@pytest.mark.parametrize("bad", ["", "   ", 7])
def test_blank_or_nonstring_topic_raises(bad):
    with pytest.raises(ValueError):
        resolve_channels(
            ChannelQuery(jurisdiction="jpn", topic=bad), _registry(_entry("a")))


def test_unknown_confidence_in_registry_raises():
    reg = _registry(_entry("a", confidence="cosmic"))
    with pytest.raises(ValueError):
        resolve_channels(ChannelQuery(jurisdiction="jpn"), reg)


def test_registry_without_channels_list_raises():
    with pytest.raises(ValueError):
        resolve_channels(ChannelQuery(jurisdiction="jpn"), {"channels": "nope"})


def test_entry_missing_required_field_raises():
    bad = {"channelId": "a", "jurisdiction": "jpn", "confidence": "high",
           "channelKind": "official-gazette"}  # no title
    with pytest.raises(ValueError):
        resolve_channels(ChannelQuery(jurisdiction="jpn"), _registry(bad))


# ── frozen-dataclass invariant pin cannot be flipped ────────────────────


def test_channel_is_frozen_invariants_immutable():
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), _registry(_entry("a")))
    c = res.channels[0]
    assert isinstance(c, PublicationChannel)
    with pytest.raises(Exception):  # FrozenInstanceError (a dataclasses subtype)
        c.is_original_publication = True  # type: ignore[misc]


# ── integration: drive the worldwide publication-channel seed registry ──


def test_registry_loads_and_has_worldwide_coverage():
    data = load_registry(_REGISTRY)
    juris = {c["jurisdiction"] for c in data["channels"]}
    assert len(data["channels"]) >= 100  # worldwide, not JP-only
    assert len(juris) >= 20  # many distinct jurisdictions
    assert "jpn" in juris


def test_registry_every_seed_entry_projects_known_kind():
    """The whole seed must project without raising — every entry's channelKind
    is one of the known kinds (no unknown channel slipped in)."""
    data = load_registry(_REGISTRY)
    juris = {c["jurisdiction"] for c in data["channels"]}
    total = 0
    for j in juris:
        res = resolve_channels(ChannelQuery(jurisdiction=j), data)
        total += len(res.channels)
        assert all(c.channel_kind in CHANNEL_KINDS for c in res.channels)
    assert total == len(data["channels"])  # nothing dropped, nothing raised


def test_registry_jpn_routes_sorted_high_first_with_kanpo_anchor():
    data = load_registry(_REGISTRY)
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), data)
    assert len(res.channels) == 6  # 6 real jpn entries in the seed
    ranks = [CONFIDENCE_ORDER[c.confidence] for c in res.channels]
    assert ranks == sorted(ranks)  # non-decreasing confidence rank
    ids = {c.channel_id for c in res.channels}
    assert "jpn-kanpo-official-gazette" in ids
    assert all(c.is_original_publication is False for c in res.channels)


def test_registry_jpn_translation_kind_narrows_to_law_translation():
    data = load_registry(_REGISTRY)
    res = resolve_channels(
        ChannelQuery(jurisdiction="jpn", channel_kind="translation-resource"), data)
    ids = {c.channel_id for c in res.channels}
    assert "jpn-japanese-law-translation" in ids
    assert all(c.channel_kind == "translation-resource" for c in res.channels)


def test_registry_unknown_jurisdiction_empty_against_real_seed():
    data = load_registry(_REGISTRY)
    res = resolve_channels(ChannelQuery(jurisdiction="zz-atlantis"), data)
    assert res.channels == ()


def test_registry_real_record_is_pure_routing_view():
    data = load_registry(_REGISTRY)
    res = resolve_channels(ChannelQuery(jurisdiction="jpn"), data)
    rec = to_channel_routing_record(
        res, member_did="did:web:member.example",
        created_at=datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc),
        session_ref="at://session/1",
    )
    assert rec["isOriginalPublication"] is False
    assert rec["assertsContentAccuracy"] is False
    assert rec["channelCount"] == len(res.channels) == 6
    assert rec["sessionRef"] == "at://session/1"
    for view in rec["channels"]:
        assert "accessUrl" in view and "provenance" in view


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
