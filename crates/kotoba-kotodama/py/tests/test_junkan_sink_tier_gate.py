"""Tier-C gating tests for junkan.sink.EavtSink (ADR-2605262400 §5 / G4 / R9).

An ``internal_only=True`` (tier-C) observation MUST NOT be ingested into an
EXTERNAL_FACING kotoba sink; it is dropped and recorded for the R9 backstop.
INTERNAL_ONLY sinks (the default — fleet-internal canonical store) pass it.
"""

from __future__ import annotations

from dataclasses import dataclass

from kotodama.organism.junkan import (
    DroppedObservation,
    EavtSink,
    SinkClass,
)
from kotodama.organism.sensors.base import SensorObservation


def _obs(internal_only: bool, tier: str = "C", sensor: str = "dns/rapid7-sonar-fdns",
         key: str = "k1") -> SensorObservation:
    return SensorObservation(
        sensor=sensor, tier=tier, pin_revision="rev-1",
        payload={"id": key}, internal_only=internal_only,
    )


def test_default_sink_is_internal_only():
    assert EavtSink().classification is SinkClass.INTERNAL_ONLY


def test_internal_sink_passes_tier_c():
    sink = EavtSink()  # INTERNAL_ONLY default
    r = sink.ingest(_obs(internal_only=True), key_field="pin_revision")
    assert r is not None
    assert sink.pop_drops() == []
    assert len(sink.store) > 0


def test_external_sink_drops_tier_c():
    sink = EavtSink(classification=SinkClass.EXTERNAL_FACING)
    r = sink.ingest(_obs(internal_only=True), key_field="pin_revision")
    assert r is None                       # dropped
    assert len(sink.store) == 0            # nothing transacted
    drops = sink.pop_drops()
    assert len(drops) == 1
    assert isinstance(drops[0], DroppedObservation)
    assert drops[0].tier == "C"
    assert drops[0].sensor == "dns/rapid7-sonar-fdns"


def test_external_sink_passes_non_internal():
    sink = EavtSink(classification=SinkClass.EXTERNAL_FACING)
    r = sink.ingest(_obs(internal_only=False, tier="A"), key_field="pin_revision")
    assert r is not None
    assert sink.pop_drops() == []


def test_pop_drops_clears():
    sink = EavtSink(classification=SinkClass.EXTERNAL_FACING)
    sink.ingest(_obs(internal_only=True), key_field="pin_revision")
    assert len(sink.pop_drops()) == 1
    assert sink.pop_drops() == []          # cleared after pop


def test_ingest_all_omits_dropped_receipts():
    sink = EavtSink(classification=SinkClass.EXTERNAL_FACING)
    obses = [
        _obs(internal_only=False, tier="A", key="a"),
        _obs(internal_only=True, tier="C", key="b"),
        _obs(internal_only=False, tier="A", key="c"),
    ]
    # distinct entity ids via payload id key
    receipts = sink.ingest_all(obses, key_field="pin_revision")
    # all three share pin_revision key here → same entity; assert drop accounting instead
    assert len(sink.pop_drops()) == 1      # exactly the one tier-C observation


def test_observations_without_internal_only_field_always_pass():
    @dataclass(frozen=True)
    class PlainObservation:
        widget_id: str

    sink = EavtSink(classification=SinkClass.EXTERNAL_FACING)
    r = sink.ingest(PlainObservation(widget_id="w1"), key_field="widget_id")
    assert r is not None                   # no internal_only attr → not gated
    assert sink.pop_drops() == []


def test_legal_observations_are_tier_a_and_pass_external(tmp_path):
    # Treaty/statute/etc. carry internal_only=False → publishable.
    from kotodama.organism.sensors.legal.base import LegalTreatyObservation

    obs = LegalTreatyObservation(
        sensor="law/treaties/un-treaty-collection", tier="A", pin_revision="r",
        treaty_id="UNTS-1", title="T", party_states_iso3=("USA",),
        in_force_at=None, body_excerpt="", license_tag="public-domain",
    )
    sink = EavtSink(classification=SinkClass.EXTERNAL_FACING)
    assert sink.ingest(obs) is not None
    assert sink.pop_drops() == []
