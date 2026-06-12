import json
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from kotodama.organism.lifecycle import (
    BirthEvent,
    CloneEvent,
    ExcommunicationEvent,
    OrganismLifecycle,
    OrganismState,
    RetireEvent,
    lifecycle_event_to_lexicon,
)
from kotodama.organism.lifecycle_publisher import NdjsonLifecyclePublisher


@pytest.fixture
def test_did():
    return "did:test:123"


@pytest.fixture
def queue_file(tmp_path: Path) -> Path:
    return tmp_path / "lifecycle_queue.ndjson"


def test_ndjson_publisher_writes_record(queue_file: Path, test_did: str):
    """Verify the publisher writes a complete, correctly-formatted NDJSON record."""
    publisher = NdjsonLifecyclePublisher(queue_path=queue_file, actor_did=test_did)
    birth_event = BirthEvent(reason="test birth")
    lexicon_event = lifecycle_event_to_lexicon(birth_event)

    publisher(lexicon_event)

    with queue_file.open("r") as f:
        line = f.readline()
        record = json.loads(line)

    assert record["v"] == 1
    assert record["lexicon"] == "com.etzhayyim.organism.lifecycle"
    assert record["actorDid"] == test_did
    assert "ts" in record
    assert "createdAt" in record
    assert record["createdAt"].endswith("Z")
    assert record["event"]["$type"] == "com.etzhayyim.organism.lifecycle#birth"
    assert record["event"]["reason"] == "test birth"


def test_lifecycle_calls_publisher_on_transition(test_did: str):
    """Check that a state transition in OrganismLifecycle triggers the publisher."""
    mock_publisher = MagicMock()
    lifecycle = OrganismLifecycle(event_publisher=mock_publisher)

    assert mock_publisher.call_count == 0
    lifecycle.handle_birth(actor_did=test_did)
    assert mock_publisher.call_count == 1

    # The publisher should be called with the lexicon representation of the event
    call_args, _ = mock_publisher.call_args
    sent_event_lexicon = call_args[0]
    assert sent_event_lexicon["$type"] == "com.etzhayyim.organism.lifecycle#birth"
    assert f"Birth of {test_did}" in sent_event_lexicon["reason"]


def test_lifecycle_no_publisher_is_safe(queue_file: Path, test_did: str):
    """Ensure no error occurs and no file is written if the publisher is None."""
    lifecycle = OrganismLifecycle(event_publisher=None)
    lifecycle.handle_birth(actor_did=test_did)

    assert not queue_file.exists()


def test_all_event_types_are_publishable(queue_file: Path, test_did: str):
    """Verify all four event types are serialized and published correctly."""
    publisher = NdjsonLifecyclePublisher(queue_path=queue_file, actor_did=test_did)
    lifecycle = OrganismLifecycle(event_publisher=publisher)

    # 1. Birth
    lifecycle.handle_birth(actor_did=test_did, council_attestation_cid="test_cid")

    # 2. Retire
    lifecycle.handle_retire(reason="end of service")

    # 3. Excommunication
    lifecycle.state = OrganismState.ACTIVE  # Reset state for next transition
    lifecycle.handle_excommunication(
        council_attestation_cid="excom_cid",
        council_attestation_chain=["att1", "att2", "att3", "att4"],
    )

    # 4. Clone
    lifecycle.state = OrganismState.ACTIVE  # Reset state for next transition
    lifecycle.handle_clone(
        source_did=test_did, target_did="did:test:456", shard="shard-A"
    )

    lines = queue_file.read_text().strip().split("\n")
    assert len(lines) == 4

    # Check each record
    birth_record = json.loads(lines[0])
    assert birth_record["event"]["$type"] == "com.etzhayyim.organism.lifecycle#birth"
    assert birth_record["event"]["councilAttestation"] == "test_cid"

    retire_record = json.loads(lines[1])
    assert retire_record["event"]["$type"] == "com.etzhayyim.organism.lifecycle#retire"
    assert retire_record["event"]["reason"] == "end of service"

    excom_record = json.loads(lines[2])
    assert (
        excom_record["event"]["$type"]
        == "com.etzhayyim.organism.lifecycle#excommunication"
    )
    assert excom_record["event"]["councilAttestation"] == "excom_cid"

    clone_record = json.loads(lines[3])
    assert clone_record["event"]["$type"] == "com.etzhayyim.organism.lifecycle#clone"
    assert clone_record["event"]["sourceShard"] == "shard-A"
