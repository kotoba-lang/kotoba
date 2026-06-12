import json
import time
from datetime import datetime, timezone
from pathlib import Path


class NdjsonLifecyclePublisher:
    """Publishes organism lifecycle events to an NDJSON file for a specific actor."""

    def __init__(self, queue_path: Path, actor_did: str):
        self.queue_path = queue_path
        self.actor_did = actor_did
        # Ensure the directory exists
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, event_lexicon: dict) -> None:
        """Constructs a full drainer record and appends it to the queue file."""
        now = datetime.now(timezone.utc)
        record = {
            "v": 1,
            "ts": int(now.timestamp()),
            "actorDid": self.actor_did,
            "lexicon": "com.etzhayyim.organism.lifecycle",
            "createdAt": now.isoformat().replace("+00:00", "Z"),
            "event": event_lexicon,
        }

        # Atomic append
        try:
            with self.queue_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            # In a real scenario, we might want more robust error handling,
            # like logging or a dead-letter queue.
            # For now, we'll let the exception propagate.
            raise
