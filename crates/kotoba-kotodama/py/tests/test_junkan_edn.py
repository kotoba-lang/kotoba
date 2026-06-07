"""Tests for junkan.edn — EDN wire-format + Observation→datom→EDN bridge.

ADR-2605262130 + ADR-2605312345. This is the missing path that lets a
passive sensor observation be transacted into kotoba as Datomic-isomorphic
EDN tx-data. Covers:
  - to_edn primitive + collection serialization (nil/bool/kw/str/num/
    vector/map/set/inst), with bool-before-int and Keyword-before-str;
  - string escaping;
  - datom_to_eavt_edn raw [e a v t];
  - datoms_to_tx_edn [[:db/add e a v] …] (the kotoba ingest form);
  - entity_to_edn {:db/id … :a v};
  - store_to_tx_edn full-store dump preserving order;
  - ns_for namespace derivation from Observation class names;
  - datoms_from_dataclass field→attr mapping + skip_none + skip;
  - END-TO-END: a real LegalTreatyObservation → datoms → EDN.
"""

from __future__ import annotations

import datetime as dt

import pytest

from kotodama.organism.junkan import (
    Datom,
    DatomStore,
    Keyword,
    datom_to_eavt_edn,
    datoms_from_dataclass,
    datoms_to_tx_edn,
    entity_to_edn,
    kw,
    ns_for,
    store_to_tx_edn,
    to_edn,
)
from kotodama.organism.sensors.legal.base import LegalTreatyObservation


# ── to_edn primitives ─────────────────────────────────────────────────────
def test_to_edn_scalars():
    assert to_edn(None) == "nil"
    assert to_edn(True) == "true"
    assert to_edn(False) == "false"
    assert to_edn(42) == "42"
    assert to_edn(-3) == "-3"
    assert to_edn(1.5) == "1.5"
    assert to_edn("hello") == '"hello"'


def test_bool_not_serialized_as_int():
    # bool is an int subclass — must be checked first.
    assert to_edn(True) == "true"
    assert to_edn(1) == "1"


def test_keyword_vs_string():
    assert to_edn(kw("db/add")) == ":db/add"
    assert to_edn(kw(":already")) == ":already"
    assert to_edn("db/add") == '"db/add"'          # plain str → quoted
    assert isinstance(kw("x"), Keyword)


def test_string_escaping():
    assert to_edn('a"b') == '"a\\"b"'
    assert to_edn("a\\b") == '"a\\\\b"'
    assert to_edn("line1\nline2") == '"line1\\nline2"'
    assert to_edn("t\tab") == '"t\\tab"'


def test_to_edn_vector_and_tuple():
    assert to_edn([1, 2, 3]) == "[1 2 3]"
    assert to_edn(("USA", "JPN")) == '["USA" "JPN"]'
    assert to_edn([]) == "[]"


def test_to_edn_map():
    assert to_edn({kw("a"): 1, kw("b"): "x"}) == '{:a 1 :b "x"}'


def test_to_edn_set():
    out = to_edn({1})
    assert out == "#{1}"


def test_to_edn_inst():
    d = dt.datetime(2026, 6, 1, 12, 0, 0)
    assert to_edn(d) == '#inst "2026-06-01T12:00:00"'


def test_to_edn_unsupported_raises():
    with pytest.raises(TypeError):
        to_edn(object())


# ── datom / tx serialization ──────────────────────────────────────────────
def test_datom_to_eavt_edn():
    d = Datom(e="treaty:UNTS-1", a=":legal.treaty/title", v="Vienna Convention", t=3)
    assert datom_to_eavt_edn(d) == '["treaty:UNTS-1" :legal.treaty/title "Vienna Convention" 3]'


def test_datom_eavt_edn_normalizes_attr_keyword():
    # attribute stored without leading ':' still emits as a keyword.
    d = Datom(e="e1", a="legal.treaty/title", v="X", t=1)
    assert ":legal.treaty/title" in datom_to_eavt_edn(d)


def test_datoms_to_tx_edn():
    facts = [
        ("treaty:1", ":legal.treaty/title", "T1"),
        ("treaty:1", ":legal.treaty/in-force-at", "1980-01-27"),
    ]
    edn = datoms_to_tx_edn(facts)
    assert edn == (
        '[[:db/add "treaty:1" :legal.treaty/title "T1"] '
        '[:db/add "treaty:1" :legal.treaty/in-force-at "1980-01-27"]]'
    )


def test_entity_to_edn():
    edn = entity_to_edn("treaty:1", {"legal.treaty/title": "T1", "legal.treaty/tier": "A"})
    assert edn == '{:db/id "treaty:1" :legal.treaty/title "T1" :legal.treaty/tier "A"}'


def test_store_to_tx_edn_preserves_order():
    s = DatomStore()
    s.transact([("gini", ":junkan.stock/level", 30)])
    s.transact([("gini", ":junkan.stock/level", 34)])
    edn = store_to_tx_edn(s)
    assert edn == (
        '[[:db/add "gini" :junkan.stock/level 30] '
        '[:db/add "gini" :junkan.stock/level 34]]'
    )


# ── ns_for + dataclass bridge ─────────────────────────────────────────────
def test_ns_for_camelcase_to_dotted():
    assert ns_for(LegalTreatyObservation(
        sensor="s", tier="A", pin_revision="r", treaty_id="t", title="",
        party_states_iso3=(), in_force_at=None, body_excerpt="", license_tag="x",
    )) == "legal.treaty"


def test_datoms_from_dataclass_maps_fields():
    obs = LegalTreatyObservation(
        sensor="law/treaties/un-treaty-collection", tier="A", pin_revision="rev-1",
        treaty_id="UNTS-12345", title="Vienna Convention",
        party_states_iso3=("AUT", "USA", "JPN"), in_force_at="1980-01-27",
        body_excerpt="Every treaty in force ...", license_tag="public-domain",
    )
    facts = datoms_from_dataclass(obs, entity_id="treaty:UNTS-12345")
    by_attr = {a: v for (_e, a, v) in facts}
    assert all(e == "treaty:UNTS-12345" for (e, _a, _v) in facts)
    assert by_attr[":legal.treaty/treaty-id"] == "UNTS-12345"
    assert by_attr[":legal.treaty/party-states-iso3"] == ("AUT", "USA", "JPN")
    assert by_attr[":legal.treaty/tier"] == "A"
    # captured_at_ms == 0 default still present (not None); internal_only False present.
    assert ":legal.treaty/captured-at-ms" in by_attr


def test_datoms_from_dataclass_skips_none_and_named():
    obs = LegalTreatyObservation(
        sensor="s", tier="A", pin_revision="r", treaty_id="T", title="t",
        party_states_iso3=(), in_force_at=None, body_excerpt="b", license_tag="x",
    )
    facts = datoms_from_dataclass(obs, entity_id="t:T", skip=("sensor", "pin_revision"))
    attrs = {a for (_e, a, _v) in facts}
    assert ":legal.treaty/in-force-at" not in attrs   # None dropped
    assert ":legal.treaty/sensor" not in attrs        # skip
    assert ":legal.treaty/pin-revision" not in attrs  # skip
    assert ":legal.treaty/treaty-id" in attrs


def test_datoms_from_dataclass_keep_none_when_disabled():
    obs = LegalTreatyObservation(
        sensor="s", tier="A", pin_revision="r", treaty_id="T", title="t",
        party_states_iso3=(), in_force_at=None, body_excerpt="b", license_tag="x",
    )
    facts = datoms_from_dataclass(obs, entity_id="t:T", skip_none=False)
    by_attr = {a: val for (_e, a, val) in facts}
    assert by_attr[":legal.treaty/in-force-at"] is None


def test_datoms_from_dataclass_rejects_non_dataclass():
    with pytest.raises(TypeError):
        datoms_from_dataclass({"a": 1}, entity_id="x")


# ── END-TO-END: world-info observation → kotoba EDN tx-data ────────────────
def test_observation_to_kotoba_edn_roundtrip():
    obs = LegalTreatyObservation(
        sensor="law/treaties/un-treaty-collection", tier="A", pin_revision="rev-1",
        treaty_id="UNTS-12345", title="Vienna Convention on the Law of Treaties",
        party_states_iso3=("AUT", "USA"), in_force_at="1980-01-27",
        body_excerpt="Every treaty in force is binding ...", license_tag="public-domain",
    )
    facts = datoms_from_dataclass(obs, entity_id="treaty:UNTS-12345",
                                  skip=("captured_at_ms", "internal_only"))
    edn = datoms_to_tx_edn(facts)
    # The serialized tx-data is the form kotoba-kqe ingests.
    assert edn.startswith("[[:db/add ")
    assert ':legal.treaty/title "Vienna Convention on the Law of Treaties"' in edn
    assert ':legal.treaty/party-states-iso3 ["AUT" "USA"]' in edn
    assert edn.endswith("]]")

    # And the same facts load into the reference DatomStore (EAVT model).
    store = DatomStore()
    store.transact(facts)
    entity = store.entity("treaty:UNTS-12345")
    assert entity[":legal.treaty/treaty-id"] == "UNTS-12345"
    assert entity[":legal.treaty/party-states-iso3"] == ("AUT", "USA")
