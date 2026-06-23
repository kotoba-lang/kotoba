"""Test harness for end-to-end, inter-organism messaging simulations."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from kotodama.organism.joucho import JouchoScores
from kotodama.organism.lifecycle import OrganismState
from kotodama.organism.messaging import MockPdsReceiver, OrganismMessage
from kotodama.organism.organism import OrganismTickResult, Organism


@dataclass
class E2EMessagingHarness:
    """A test harness for simulating messaging between two organisms, A and B."""

    organism_a: Organism
    organism_b: Organism
    pds_receiver_b: MockPdsReceiver

    @classmethod
    def create(cls, tmp_path: Path, code_a: str = "10101500", code_b: str = "10101505") -> E2EMessagingHarness:
        """Factory method to set up two organisms in a temporary directory."""
        pds_receiver = MockPdsReceiver()

        org_a = Organism.for_code(code=code_a)
        # Birth organism A so it's active
        org_a.lifecycle.handle_birth(actor_did=org_a.actor_did)

        org_b = Organism.for_code(
            code=code_b,
            messaging_receiver=pds_receiver
        )
        # Birth organism B so it's active
        org_b.lifecycle.handle_birth(actor_did=org_b.actor_did)

        return cls(
            organism_a=org_a,
            organism_b=org_b,
            pds_receiver_b=pds_receiver,
        )

    def send_from_a_to_b(self, text: str, thread_id: str | None = None) -> OrganismMessage:
        """Simulates sending a message from organism A to organism B."""
        message = OrganismMessage(
            actor_did=self.organism_a.actor_did,
            recipient_did=self.organism_b.actor_did,
            text=text,
            created_at=datetime.now(timezone.utc),
            thread_id=thread_id,
        )

        # Simulate publishing to the mock PDS that organism B reads from
        if message.recipient_did not in self.pds_receiver_b.messages:
            self.pds_receiver_b.messages[message.recipient_did] = []
        self.pds_receiver_b.messages[message.recipient_did].append(message)
        return message

    def tick_b(self) -> OrganismTickResult:
        """Executes one tick of organism B."""
        return self.organism_b.tick(now_ms=int(time.time() * 1000))

    def get_joucho_b(self) -> JouchoScores:
        """Retrieves the current joucho scores for organism B."""
        # Joucho is resolved during the tick, so we need to tick to get the latest
        tick_result = self.tick_b()
        return tick_result.cadence.joucho
