"""Tests for junkan.sink — EAVT ingest sink (sensor Observation → kotoba datoms).

ADR-2605262130 + ADR-2605312345. Verifies the assembled ingest pipeline:
  - entity-id derivation from per-family natural key (treaty_id / citation
    / procedure_id / template_id);
  - ingest() returns an IngestReceipt (entity, tx, n_facts);
  - ingest_all() over a list, one tx each;
  - SAME entity re-ingested → history accretes, latest wins (EAVT time
    travel — the property that makes re-pins update, not duplicate);
  - to_tx_edn() emits kotoba-ingestable EDN for the whole store;
  - END-TO-END: a real TreatyCorpusSensor reads an NDJSON snapshot and the
    sink ingests its stream into the DatomStore;
  - unknown observation type without a key field raises KeyError;
  - explicit entity_id / key_field overrides.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from kotodama.organism.junkan import DatomStore, EavtSink, IngestReceipt
from kotodama.organism.sensors.base import DatasetPin
from kotodama.organism.sensors.legal.base import LegalTreatyObservation
from kotodama.organism.sensors.legal.treaty_corpus_sensor import TreatyCorpusSensor


def _treaty(treaty_id: str, title: str, in_force_at: str | None = None) -> LegalTreatyObservation:
    return LegalTreatyObservation(
        sensor="law/treaties/un-treaty-collection", tier="A", pin_revision="rev-1",
        treaty_id=treaty_id, title=title, party_states_iso3=("USA", "JPN"),
        in_force_at=in_force_at, body_excerpt="...", license_tag="public-domain",
    )


def test_entity_id_from_natural_key():
    sink = EavtSink()
    eid = sink.entity_id_for(_treaty("UNTS-1", "T"))
    assert eid == "legal.treaty:UNTS-1"


def test_ingest_returns_receipt():
    sink = EavtSink()
    r = sink.ingest(_treaty("UNTS-1", "Vienna Convention"))
    assert isinstance(r, IngestReceipt)
    assert r.entity_id == "legal.treaty:UNTS-1"
    assert r.tx == 1
    assert r.n_facts > 0
    # the facts are readable back out of the store via EAVT
    ent = sink.store.entity("legal.treaty:UNTS-1")
    assert ent[":legal.treaty/title"] == "Vienna Convention"


def test_ingest_all_one_tx_each():
    sink = EavtSink()
    receipts = sink.ingest_all([_treaty(f"UNTS-{i}", f"T{i}") for i in range(3)])
    assert [r.tx for r in receipts] == [1, 2, 3]
    assert {r.entity_id for r in receipts} == {
        "legal.treaty:UNTS-0", "legal.treaty:UNTS-1", "legal.treaty:UNTS-2",
    }


def test_re_ingest_same_entity_accretes_history():
    # A re-pin of the same treaty with an updated in_force_at must UPDATE the
    # same entity (EAVT time travel), not create a duplicate.
    sink = EavtSink()
    sink.ingest(_treaty("UNTS-1", "Draft", in_force_at=None))
    sink.ingest(_treaty("UNTS-1", "Vienna Convention", in_force_at="1980-01-27"))
    eid = "legal.treaty:UNTS-1"
    # latest wins
    assert sink.store.entity(eid)[":legal.treaty/title"] == "Vienna Convention"
    assert sink.store.entity(eid)[":legal.treaty/in-force-at"] == "1980-01-27"
    # history retained
    titles = [v for (_t, v) in sink.store.history(eid, ":legal.treaty/title")]
    assert titles == ["Draft", "Vienna Convention"]
    # one entity, not two
    assert set(sink.store.find(":legal.treaty/treaty-id", "UNTS-1")) == {eid}


def test_as_of_time_travel():
    sink = EavtSink()
    sink.ingest(_treaty("UNTS-1", "Draft"))
    t2 = sink.ingest(_treaty("UNTS-1", "Final")).tx
    eid = "legal.treaty:UNTS-1"
    assert sink.store.entity(eid, as_of=1)[":legal.treaty/title"] == "Draft"
    assert sink.store.entity(eid, as_of=t2)[":legal.treaty/title"] == "Final"


def test_to_tx_edn_round_trips_into_kotoba_form():
    sink = EavtSink()
    sink.ingest(_treaty("UNTS-1", "T1"), skip=("captured_at_ms", "internal_only"))
    edn = sink.to_tx_edn()
    assert edn.startswith("[[:db/add ")
    assert ':legal.treaty/title "T1"' in edn
    assert ':legal.treaty/party-states-iso3 ["USA" "JPN"]' in edn


def test_explicit_entity_id_override():
    sink = EavtSink()
    r = sink.ingest(_treaty("UNTS-1", "T"), entity_id="custom:id")
    assert r.entity_id == "custom:id"


def test_key_field_override():
    sink = EavtSink()
    # use title as the key instead of treaty_id
    eid = sink.entity_id_for(_treaty("UNTS-1", "Vienna"), key_field="title")
    assert eid == "legal.treaty:Vienna"


def test_unknown_observation_without_key_raises():
    @dataclass(frozen=True)
    class WidgetObservation:
        gizmo: str

    sink = EavtSink()
    with pytest.raises(KeyError):
        sink.ingest(WidgetObservation(gizmo="g"))
    # but an explicit key_field works
    r = sink.ingest(WidgetObservation(gizmo="g"), key_field="gizmo")
    assert r.entity_id == "widget:g"


def test_custom_key_fields_registry():
    @dataclass(frozen=True)
    class WidgetObservation:
        gizmo: str

    sink = EavtSink(key_fields={"WidgetObservation": "gizmo"})
    r = sink.ingest(WidgetObservation(gizmo="abc"))
    assert r.entity_id == "widget:abc"


# ── END-TO-END: real sensor → snapshot → sink → EAVT store ─────────────────
def test_end_to_end_sensor_stream_into_sink(tmp_path: Path):
    name = "law/treaties/un-treaty-collection"
    snap = tmp_path / name / "snap-20260601T000000Z"
    snap.mkdir(parents=True)
    rows = [
        {"treaty_id": "UNTS-100", "title": "Treaty A",
         "party_states": ["USA", "JPN"], "in_force_at": "1990-01-01", "body": "..."},
        {"treaty_id": "UNTS-200", "title": "Treaty B",
         "party_states": ["DEU"], "in_force_at": "2001-05-05", "body": "..."},
    ]
    with (snap / "treaties.ndjson").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    sensor = TreatyCorpusSensor(treaty_corpus="un-treaty")
    sensor.annex_root = tmp_path
    pin = DatasetPin(name=name, revision="rev-1", cid_map_cid="bafy",
                     license="public-domain", tier="A", created_at="2026-06-01T00:00:00Z")

    sink = EavtSink()
    receipts = sink.ingest_all(sensor.stream(pin), skip=("captured_at_ms", "internal_only"))

    assert len(receipts) == 2
    assert sink.store.entity("legal.treaty:UNTS-100")[":legal.treaty/title"] == "Treaty A"
    assert sink.store.entity("legal.treaty:UNTS-200")[":legal.treaty/party-states-iso3"] == ("DEU",)
    # one EDN tx-data blob ready for kotoba-kqe
    assert sink.to_tx_edn().count("[:db/add") >= 2 * len(receipts) // 2
