"""Tests for the junkan.edn reader — round-trip of the EDN wire format.

ADR-2605262130. The writer (to_edn / datoms_to_tx_edn) had no inverse, so
there was no way to verify that what we serialize for kotoba is parseable.
This adds read_edn / read_all_edn / parse_tx_edn and proves the round-trip:
  - scalars, strings (with escapes), keywords, vectors, maps, sets, #inst;
  - commas are whitespace (EDN semantics);
  - to_edn → read_edn identity for supported types (tuples → list);
  - parse_tx_edn inverts datoms_to_tx_edn;
  - :db/retract is rejected (G9 append-only);
  - malformed input raises EdnError;
  - END-TO-END: observation → datoms → EDN → parse_tx_edn → DatomStore.
"""

from __future__ import annotations

import datetime as dt

import pytest

from kotodama.organism.junkan import (
    DatomStore,
    EdnError,
    datoms_from_dataclass,
    datoms_to_tx_edn,
    kw,
    parse_tx_edn,
    read_all_edn,
    read_edn,
    to_edn,
)
from kotodama.organism.sensors.legal.base import LegalTreatyObservation


# ── scalar / collection reading ───────────────────────────────────────────
def test_read_scalars():
    assert read_edn("nil") is None
    assert read_edn("true") is True
    assert read_edn("false") is False
    assert read_edn("42") == 42
    assert read_edn("-7") == -7
    assert read_edn("1.5") == 1.5
    assert read_edn('"hello"') == "hello"


def test_read_keyword():
    k = read_edn(":legal.treaty/title")
    assert k == ":legal.treaty/title"
    assert isinstance(k, type(kw("x")))


def test_read_string_escapes():
    assert read_edn(r'"a\"b"') == 'a"b'
    assert read_edn(r'"a\\b"') == "a\\b"
    assert read_edn(r'"l1\nl2"') == "l1\nl2"
    assert read_edn(r'"t\tab"') == "t\tab"


def test_read_vector_map_set():
    assert read_edn("[1 2 3]") == [1, 2, 3]
    assert read_edn('{:a 1 :b "x"}') == {kw("a"): 1, kw("b"): "x"}
    assert read_edn("#{1 2 3}") == {1, 2, 3}
    assert read_edn("[]") == []


def test_read_nested():
    assert read_edn('[[:db/add "e" :a [1 2]]]') == [[":db/add", "e", ":a", [1, 2]]]


def test_commas_are_whitespace():
    assert read_edn("[1, 2, 3]") == [1, 2, 3]


def test_read_inst():
    assert read_edn('#inst "2026-06-01T12:00:00"') == dt.datetime(2026, 6, 1, 12, 0, 0)


def test_read_all_multiple_forms():
    assert read_all_edn("1 2 3") == [1, 2, 3]
    assert read_all_edn("") == []


# ── error handling ────────────────────────────────────────────────────────
def test_trailing_data_raises():
    with pytest.raises(EdnError):
        read_edn("1 2")


def test_unterminated_string_raises():
    with pytest.raises(EdnError):
        read_edn('"abc')


def test_unterminated_vector_raises():
    with pytest.raises(EdnError):
        read_edn("[1 2")


def test_bare_symbol_rejected():
    with pytest.raises(EdnError):
        read_edn("foo")


def test_unsupported_dispatch_rejected():
    with pytest.raises(EdnError):
        read_edn("#uuid \"x\"")


# ── round-trip property: to_edn → read_edn ────────────────────────────────
@pytest.mark.parametrize("value", [
    None, True, False, 0, 42, -3, 3.14, "", "hi",
    "needs \"escape\"\nand\ttabs",
    [1, 2, 3], [], [["a", "b"], ["c"]],
    {kw("a"): 1, kw("b"): [1, 2]},
    {1, 2, 3},
    dt.datetime(2026, 6, 1, 0, 0, 0),
])
def test_roundtrip_to_edn_read_edn(value):
    assert read_edn(to_edn(value)) == value


def test_tuple_roundtrips_as_list():
    # EDN has no tuple; a tuple serializes to a vector and reads back as list.
    assert read_edn(to_edn(("USA", "JPN"))) == ["USA", "JPN"]


# ── parse_tx_edn inverts datoms_to_tx_edn ─────────────────────────────────
def test_parse_tx_edn_inverts_writer():
    facts = [
        ("treaty:1", ":legal.treaty/title", "T1"),
        ("treaty:1", ":legal.treaty/party-states-iso3", ["USA", "JPN"]),
    ]
    edn = datoms_to_tx_edn(facts)
    parsed = parse_tx_edn(edn)
    # attr comes back as Keyword, value vectors as list; compare structurally
    assert [(e, str(a), v) for (e, a, v) in parsed] == [
        ("treaty:1", ":legal.treaty/title", "T1"),
        ("treaty:1", ":legal.treaty/party-states-iso3", ["USA", "JPN"]),
    ]


def test_parse_tx_edn_rejects_retract():
    with pytest.raises(EdnError):
        parse_tx_edn('[[:db/retract "e" :a "v"]]')


def test_parse_tx_edn_rejects_bad_arity():
    with pytest.raises(EdnError):
        parse_tx_edn('[[:db/add "e" :a]]')


# ── END-TO-END: observation → EDN → parse → DatomStore ────────────────────
def test_full_roundtrip_observation_through_edn_into_store():
    obs = LegalTreatyObservation(
        sensor="law/treaties/un-treaty-collection", tier="A", pin_revision="rev-1",
        treaty_id="UNTS-12345", title="Vienna Convention",
        party_states_iso3=("AUT", "USA"), in_force_at="1980-01-27",
        body_excerpt="...", license_tag="public-domain",
    )
    facts = datoms_from_dataclass(obs, entity_id="treaty:UNTS-12345",
                                  skip=("captured_at_ms", "internal_only"))
    edn = datoms_to_tx_edn(facts)

    # Parse the wire format back and load it into a fresh store — simulating
    # the receiving (kotoba-kqe) side ingesting our EDN tx-data.
    parsed = parse_tx_edn(edn)
    store = DatomStore()
    store.transact([(e, str(a), v) for (e, a, v) in parsed])

    ent = store.entity("treaty:UNTS-12345")
    assert ent[":legal.treaty/title"] == "Vienna Convention"
    assert ent[":legal.treaty/party-states-iso3"] == ["AUT", "USA"]  # tuple→vector→list
    assert ent[":legal.treaty/tier"] == "A"
