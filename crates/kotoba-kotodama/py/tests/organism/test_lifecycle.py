import pytest
import time
from typing import Any

from kotodama.organism.lifecycle import (
    OrganismLifecycle,
    OrganismState,
    InvalidLifecycleTransition,
    BirthEvent,
    CloneEvent,
    RetireEvent,
    ExcommunicationEvent,
    event_from_lexicon,
    lifecycle_event_to_lexicon,
)
from kotodama.organism.organism import Organism
from kotodama.organism.cadence import ContentSource

def test_lifecycle_4_events_normal_transitions():
    lifecycle = OrganismLifecycle()

    assert lifecycle.state == OrganismState.INACTIVE

    # 1. Birth
    lifecycle.handle_birth("did:web:test", "bafy...birth")
    assert lifecycle.state == OrganismState.ACTIVE
    assert len(lifecycle.transition_history) == 1
    assert isinstance(lifecycle.transition_history[0][0], BirthEvent)

    # 2. Clone
    lifecycle.handle_clone("did:web:parent", "did:web:child", "shard-1")
    assert lifecycle.state == OrganismState.CLONED
    assert lifecycle.parent_did == "did:web:parent"
    assert len(lifecycle.transition_history) == 2
    assert isinstance(lifecycle.transition_history[1][0], CloneEvent)

def test_lifecycle_retire_and_excommunication():
    # Retire
    lifecycle1 = OrganismLifecycle()
    lifecycle1.handle_birth("did:web:1")
    lifecycle1.handle_retire("end of life")
    assert lifecycle1.state == OrganismState.RETIRED

    # Excommunication
    lifecycle2 = OrganismLifecycle()
    lifecycle2.handle_birth("did:web:2")
    chain = ["attest1", "attest2", "attest3", "attest4"]
    lifecycle2.handle_excommunication("bafy...excom", chain)
    assert lifecycle2.state == OrganismState.EXCOMMUNICATED

def test_invalid_transitions():
    lifecycle = OrganismLifecycle()

    # Cannot clone inactive
    with pytest.raises(InvalidLifecycleTransition):
        lifecycle.handle_clone("a", "b", "c")

    lifecycle.handle_birth("did:web:1")
    lifecycle.handle_retire("retire")

    # Cannot become active from retired
    with pytest.raises(InvalidLifecycleTransition):
        lifecycle.handle_birth("did:web:1")

def test_excommunication_requires_4_attestations():
    lifecycle = OrganismLifecycle()
    lifecycle.handle_birth("did:web:test")

    # 3 attestations -> raises
    with pytest.raises(InvalidLifecycleTransition, match="requires >=4/7"):
        lifecycle.handle_excommunication("bafy...excom", ["a1", "a2", "a3"])

    assert lifecycle.state == OrganismState.ACTIVE

    # 4 attestations -> passes
    lifecycle.handle_excommunication("bafy...excom", ["a1", "a2", "a3", "a4"])
    assert lifecycle.state == OrganismState.EXCOMMUNICATED

def test_organism_tick_lifecycle_skips():
    class DummyGraph:
        def invoke(self, state: Any) -> dict:
            return {"result": "ok"}

    # Active -> normal tick
    org = Organism(code="12345678", graph=DummyGraph())
    org.lifecycle.handle_birth("did:test")

    result = org.tick(now_ms=1000)
    # Check that it actually ran and returned a reasoned cadence
    assert "skipped" not in result.cadence.reason

    # Retired -> tick skipped
    org.lifecycle.handle_retire("tired")
    result2 = org.tick(now_ms=2000)
    assert "skipped" in result2.cadence.reason
    assert result2.cadence.should_post is False

def test_organism_cloned_metadata():
    class DummyGraph:
        def invoke(self, state: Any) -> dict:
            return {"result": "ok"}

    org = Organism(code="12345678", graph=DummyGraph())
    org.lifecycle.handle_birth("did:test")
    org.lifecycle.handle_clone("did:web:source", "did:web:target", "shard-2")

    result = org.tick(now_ms=1000)
    assert "skipped" not in result.cadence.reason
    assert result.metadata.get("parent_did") == "did:web:source"

def test_lexicon_roundtrip():
    # Test all 4 events
    events = [
        BirthEvent(reason="test", council_attestation="cid"),
        CloneEvent(source_shard="s1", target_shard="s2"),
        RetireEvent(reason="old"),
        ExcommunicationEvent(council_attestation="cid", chigiri_procedure_ref="ref")
    ]

    for event in events:
        lex_dict = lifecycle_event_to_lexicon(event)

        # Wrapped in main record style to test the record.get("event") logic
        record = {
            "actorDid": "did:web:test",
            "createdAt": "2024-01-01T00:00:00Z",
            "event": lex_dict
        }

        parsed = event_from_lexicon(record)
        assert parsed == event

        # Also test direct union object parsing
        parsed_direct = event_from_lexicon(lex_dict)
        assert parsed_direct == event
