"""End-to-end tests for inter-organism messaging."""

import pytest
from pathlib import Path
import time
from datetime import datetime, timezone

from kotodama.organism.testing import E2EMessagingHarness
from kotodama.organism.lifecycle import OrganismState
from kotodama.organism.observation import TextObservation
from kotodama.organism.messaging import OrganismMessage

@pytest.fixture
def harness(tmp_path: Path) -> E2EMessagingHarness:
    """Provides a configured E2EMessagingHarness instance."""
    return E2EMessagingHarness.create(tmp_path)

def test_normal_message_round_trip(harness: E2EMessagingHarness):
    """Test 1: A normal message from A to B is processed and affects B's joucho."""
    initial_joucho = harness.organism_b.tick(now_ms=int(time.time() * 1000)).cadence.joucho
    assert initial_joucho.calm == 50
    assert initial_joucho.focus == 50

    # To see a change in joucho, we need to send enough messages to overcome the
    # integer division in the apply_sensor_delta function.
    # calm_delta is tier_a_obs_count // 8
    # focus_delta is tier_a_obs_count // 4
    # Sending 8 messages should result in calm_delta=1 and focus_delta=2.
    for i in range(8):
        harness.send_from_a_to_b(f"hello world, this is test message {i}")

    # Tick B to process the messages and get the result from this tick
    tick_result = harness.tick_b()

    # The inbox is cleared after the tick
    assert len(harness.organism_b.inbox.observations) == 0

    # Check that B's joucho has changed as expected
    final_joucho = tick_result.cadence.joucho

    # Joy is not expected to change for TextObservation based on current logic
    assert final_joucho.joy == initial_joucho.joy
    assert final_joucho.calm == initial_joucho.calm + 1
    assert final_joucho.focus == initial_joucho.focus + 2


def test_adversarial_message_blocked_by_l1(harness: E2EMessagingHarness):
    """Test 2: An adversarial message with Cyrillic confusables is dropped."""
    adversarial_text = "helаo" # "а" is Cyrillic

    message = OrganismMessage(
        actor_did=harness.organism_a.actor_did,
        recipient_did=harness.organism_b.actor_did,
        text=adversarial_text,
        created_at=datetime.now(timezone.utc),
    )

    # The ValueError is raised by TextObservation's validator, which is
    # called by ingest_message. The main tick() method catches this exception,
    # so to test the failure, we must call the lower-level method directly.
    with pytest.raises(ValueError, match="L1 adversarial input detected"):
        harness.organism_b.inbox.ingest_message(message)

    # Ensure no observations were added
    assert len(harness.organism_b.inbox.observations) == 0


def test_lifecycle_gating_retired_organism(harness: E2EMessagingHarness):
    """Test 3: A retired organism does not ingest messages."""
    harness.organism_b.lifecycle.handle_retire("test retirement")

    harness.send_from_a_to_b("You should not see this.")

    tick_result = harness.tick_b()

    # Tick should be a no-op for a retired organism
    assert "skipped (state=retired)" in tick_result.cadence.reason

    # Verify the message was not ingested
    recipient_did = harness.organism_b.actor_did
    messages_in_queue = harness.pds_receiver_b.messages.get(recipient_did, [])
    assert len(messages_in_queue) == 1

    # The tick for a retired organism doesn't run message receiving logic.
    assert len(harness.organism_b.inbox.observations) == 0


def test_thread_id_propagation(harness: E2EMessagingHarness):
    """Test 4: thread_id is correctly propagated to the observation metadata."""
    # Ensure the inbox is clear before starting
    harness.organism_b.inbox.observations.clear()

    thread_id = "test-thread-123"
    harness.send_from_a_to_b("msg1", thread_id=thread_id)
    harness.send_from_a_to_b("msg2", thread_id=thread_id)

    # Manually run the message ingestion part of the tick to inspect observations
    # before they are consumed by the full tick cycle.
    messages = list(harness.pds_receiver_b.receive_for(harness.organism_b.actor_did, datetime.min.replace(tzinfo=timezone.utc)))
    assert len(messages) == 2

    harness.organism_b.inbox.ingest_message(messages[0])
    harness.organism_b.inbox.ingest_message(messages[1])

    assert len(harness.organism_b.inbox.observations) == 2
    obs1, obs2 = harness.organism_b.inbox.observations

    assert isinstance(obs1, TextObservation)
    assert hasattr(obs1, "metadata")
    assert obs1.metadata["thread_id"] == thread_id

    assert isinstance(obs2, TextObservation)
    assert hasattr(obs2, "metadata")
    assert obs2.metadata["thread_id"] == thread_id

def test_message_order_preservation(harness: E2EMessagingHarness):
    """Test 5: Two messages sent in order are processed in the same order."""
    # Ensure the inbox is clear before starting
    harness.organism_b.inbox.observations.clear()

    harness.send_from_a_to_b("message one")
    # A small delay to ensure distinct created_at, which MockPdsReceiver uses.
    time.sleep(0.01)
    harness.send_from_a_to_b("message two")

    # Manually ingest to inspect observations before they are cleared by the full tick
    messages = list(harness.pds_receiver_b.receive_for(harness.organism_b.actor_did, datetime.min.replace(tzinfo=timezone.utc)))
    assert len(messages) == 2

    harness.organism_b.inbox.ingest_message(messages[0])
    harness.organism_b.inbox.ingest_message(messages[1])

    assert len(harness.organism_b.inbox.observations) == 2
    obs1, obs2 = harness.organism_b.inbox.observations

    assert isinstance(obs1, TextObservation)
    assert obs1.text == "message one"
    assert isinstance(obs2, TextObservation)
    assert obs2.text == "message two"
