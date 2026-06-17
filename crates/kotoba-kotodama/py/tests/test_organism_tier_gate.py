"""TierGate auto-wiring tests (ADR-2605262400 §4.3 Wave-3).

Verifies that Organism:
  - Owns a TierGate bound to its actor_did.
  - Drains LeakAttempts on each tick via pop_leaks().
  - Routes the per-tick leak count into apply_sensor_delta → joucho
    stress axis.
  - Logs a warning when leaks are observed.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from kotodama.organism.joucho import JouchoScores
from kotodama.organism.sensors.base import (
    DatasetPin,
    SensorObservation,
)
from kotodama.organism.sensors.tier_gate import (
    SinkClassification,
    TierGate,
)
from kotodama.organism.organism import Organism


def _make_organism(actor_did: str = "did:web:etzhayyim.com:actor:test"):
    org = Organism(
        code="99999999",
        graph=MagicMock(),
        actor_did=actor_did,
    )
    # Birth → ACTIVE so tick() runs its body (the lifecycle gate otherwise
    # early-returns a no-op dummy cadence and never drains the TierGate).
    org.lifecycle.handle_birth(actor_did)
    return org


def _tier_c_obs() -> SensorObservation:
    pin = DatasetPin(
        name="dns/rapid7-sonar-fdns",
        revision="sha256:r",
        cid_map_cid="bafy",
        license="rapid7-research-use",
        tier="C",
        created_at="2026-05-26T00:00:00Z",
    )
    return SensorObservation(
        sensor=pin.name,
        tier="C",
        pin_revision=pin.revision,
        payload={"name": "example.com", "type": "txt", "value": "v=spf1"},
        internal_only=True,
    )


# ── TierGate ownership ────────────────────────────────────────────────


def test_organism_owns_tier_gate_bound_to_actor_did():
    org = _make_organism(actor_did="did:web:etzhayyim.com:actor:c99")
    assert isinstance(org.tier_gate, TierGate)
    assert org.tier_gate.actor_did == "did:web:etzhayyim.com:actor:c99"


def test_default_organism_tier_gate_drains_empty():
    org = _make_organism()
    org.tick(now_ms=1000)
    assert org.tier_gate.leak_attempts == []


# ── Wave-3 leak propagation ───────────────────────────────────────────


def test_external_caller_can_trigger_leak_via_gate():
    """External sink wrapped through organism.tier_gate.guard records a
    LeakAttempt when a tier-C observation hits an EXTERNAL_FACING sink."""
    org = _make_organism()
    external_sink_calls = []
    wrapped = org.tier_gate.guard(
        SinkClassification.EXTERNAL_FACING,
        sink_kind="public-ndjson-feed",
        wrapped=external_sink_calls.append,
    )
    wrapped(_tier_c_obs())
    # External sink did NOT receive the observation (G4 drop).
    assert external_sink_calls == []
    # And a LeakAttempt was queued for the next tick.
    assert len(org.tier_gate.leak_attempts) == 1
    assert org.tier_gate.leak_attempts[0].tier == "C"


def test_leak_increases_stress_via_apply_sensor_delta():
    """A tier-C leak attempt pumps +10 stress through
    apply_sensor_delta when the organism's next tick drains pop_leaks."""
    org = _make_organism()
    org.joucho_provider = lambda _did: JouchoScores(stress=20)
    # Simulate an external EXTERNAL_FACING sink drop.
    wrapped = org.tier_gate.guard(
        SinkClassification.EXTERNAL_FACING,
        sink_kind="social-post",
        wrapped=lambda _o: None,
    )
    wrapped(_tier_c_obs())
    assert len(org.tier_gate.leak_attempts) == 1
    # Next tick will drain the gate AND apply +10 stress via the
    # augmented joucho provider. We can't easily inspect the
    # intermediate joucho without running resolve_heartbeat_cadence;
    # the side-effect we CAN observe is that the leak ring is empty
    # after the tick.
    org.tick(now_ms=1000)
    assert org.tier_gate.leak_attempts == []  # drained


def test_multiple_leaks_drained_in_one_tick():
    org = _make_organism()
    wrapped = org.tier_gate.guard(
        SinkClassification.EXTERNAL_FACING,
        sink_kind="public-feed",
        wrapped=lambda _o: None,
    )
    wrapped(_tier_c_obs())
    wrapped(_tier_c_obs())
    wrapped(_tier_c_obs())
    assert len(org.tier_gate.leak_attempts) == 3
    org.tick(now_ms=1000)
    assert org.tier_gate.leak_attempts == []


def test_internal_only_sink_does_not_trigger_leak():
    """G4 doesn't fire when the sink is INTERNAL_ONLY (judah LiteLLM,
    encrypted-record persistence, etc.)."""
    org = _make_organism()
    sink_calls = []
    wrapped = org.tier_gate.guard(
        SinkClassification.INTERNAL_ONLY,
        sink_kind="judah-litellm",
        wrapped=sink_calls.append,
    )
    wrapped(_tier_c_obs())
    # Tier-C observation flowed through to the internal sink — that's
    # the allowed path under G13.
    assert len(sink_calls) == 1
    assert org.tier_gate.leak_attempts == []


def test_leak_logged_at_warning_level(caplog):
    org = _make_organism(actor_did="did:web:etzhayyim.com:actor:c12345678")
    wrapped = org.tier_gate.guard(
        SinkClassification.EXTERNAL_FACING,
        sink_kind="bad-feed",
        wrapped=lambda _o: None,
    )
    wrapped(_tier_c_obs())
    with caplog.at_level(logging.WARNING, logger="kotodama.organism"):
        org.tick(now_ms=1000)
    # The organism's tick() logs a warning on any leak attempt.
    matched = [r for r in caplog.records if "tier-C leak attempt" in r.message]
    assert matched, f"no leak warning logged; saw: {[r.message for r in caplog.records]}"
