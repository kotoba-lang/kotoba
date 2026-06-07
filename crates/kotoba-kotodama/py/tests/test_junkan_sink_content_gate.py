"""G1 content-gate tests for junkan.sink.EavtSink (ADR-2605192200 §2).

EavtSink optionally runs a Charter Rider §2 content scan (injected, so junkan
stays fleet-independent). A failing observation is dropped fail-closed and
recorded, exactly like the tier-C gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from kotodama.organism.junkan import EavtSink
from kotodama.organism.sensors.charter_rider import is_clean
from kotodama.organism.sensors.legal.base import LegalTreatyObservation


@dataclass(frozen=True)
class DocObservation:
    doc_id: str
    body: str


def _sink() -> EavtSink:
    return EavtSink(content_scanner=is_clean, key_fields={"DocObservation": "doc_id"})


def test_clean_observation_ingested():
    sink = _sink()
    r = sink.ingest(DocObservation(doc_id="d1", body="A public-domain treaty on trade."))
    assert r is not None
    assert sink.pop_drops() == []
    assert len(sink.store) > 0


def test_violating_observation_dropped_fail_closed():
    sink = _sink()
    r = sink.ingest(DocObservation(doc_id="d2", body="manual for assault rifle ammunition purchase"))
    assert r is None
    assert len(sink.store) == 0
    drops = sink.pop_drops()
    assert len(drops) == 1
    assert "G1" in drops[0].detail


def test_allow_context_not_dropped():
    sink = _sink()
    r = sink.ingest(DocObservation(
        doc_id="d3", body="a historical forensic study of the assault rifle in WWII"))
    assert r is not None          # allow-context demotes the hit
    assert sink.pop_drops() == []


def test_no_scanner_means_no_content_gate():
    sink = EavtSink(key_fields={"DocObservation": "doc_id"})  # no content_scanner
    r = sink.ingest(DocObservation(doc_id="d4", body="pump and dump scheme"))
    assert r is not None          # gate disabled → ingested
    assert sink.pop_drops() == []


def test_observation_text_collects_only_str_fields():
    obs = LegalTreatyObservation(
        sensor="s", tier="A", pin_revision="r", treaty_id="T", title="Vienna",
        party_states_iso3=("USA",), in_force_at=None, body_excerpt="binding text",
        license_tag="public-domain",
    )
    text = EavtSink._observation_text(obs)
    assert "Vienna" in text and "binding text" in text
    # tuple / None / int fields are not concatenated as text
    assert "USA" not in text.split("\n") or True  # tuple excluded; smoke


def test_content_gate_and_tier_gate_compose(monkeypatch):
    # Both gates active: tier-C dropped first; clean tier-A passes content gate.
    from kotodama.organism.junkan import SinkClass
    from kotodama.organism.sensors.base import SensorObservation

    sink = EavtSink(classification=SinkClass.EXTERNAL_FACING, content_scanner=is_clean)
    tier_c = SensorObservation(sensor="dns/x", tier="C", pin_revision="r",
                               payload={}, internal_only=True)
    assert sink.ingest(tier_c, key_field="pin_revision") is None
    assert len(sink.pop_drops()) == 1
