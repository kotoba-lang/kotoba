"""Organism Messaging sender and receiver stubs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

@dataclass
class OrganismMessage:
    actor_did: str
    recipient_did: str
    text: str
    created_at: datetime
    thread_id: str | None = None

    def to_ndjson_line(self) -> str:
        """Convert to NDJSON line matching the TS drainer format."""
        d = {
            "lexicon": "com.etzhayyim.organism.message",
            "v": 1,
            "actorDid": self.actor_did,
            "recipientDid": self.recipient_did,
            "text": self.text,
            "createdAt": self.created_at.isoformat(),
        }
        if self.thread_id is not None:
            d["threadId"] = self.thread_id
        return json.dumps(d)


class OrganismMessageSender:
    def __init__(self, queue_path: str | Path) -> None:
        self.queue_path = Path(queue_path)

    def send(self, message: OrganismMessage) -> None:
        line = message.to_ndjson_line()
        # append to file
        with self.queue_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


class OrganismMessageReceiver(Protocol):
    def receive_for(self, recipient_did: str, since: datetime) -> Iterable[OrganismMessage]:
        ...


class MockPdsReceiver:
    def __init__(self) -> None:
        self.messages: dict[str, list[OrganismMessage]] = {}

    def receive_for(self, recipient_did: str, since: datetime) -> Iterable[OrganismMessage]:
        msgs = self.messages.get(recipient_did, [])
        for m in msgs:
            if m.created_at >= since:
                yield m


class AtProtoFirehoseReceiver:
    def receive_for(self, recipient_did: str, since: datetime) -> Iterable[OrganismMessage]:
        raise NotImplementedError("R1.1 persist required")
