import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Union

class OrganismState(Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    CLONED = "cloned"
    RETIRED = "retired"
    EXCOMMUNICATED = "excommunicated"

class InvalidLifecycleTransition(Exception):
    """Raised when an organism attempts an invalid state transition."""
    pass

@dataclass
class BirthEvent:
    reason: str
    council_attestation: Optional[str] = None
    _type: str = "com.etzhayyim.organism.lifecycle#birth"

@dataclass
class CloneEvent:
    source_shard: str
    target_shard: str
    _type: str = "com.etzhayyim.organism.lifecycle#clone"

@dataclass
class RetireEvent:
    reason: str
    _type: str = "com.etzhayyim.organism.lifecycle#retire"

@dataclass
class ExcommunicationEvent:
    council_attestation: str
    chigiri_procedure_ref: str
    _type: str = "com.etzhayyim.organism.lifecycle#excommunication"

LifecycleEvent = Union[BirthEvent, CloneEvent, RetireEvent, ExcommunicationEvent]

def event_from_lexicon(record: dict) -> LifecycleEvent:
    """Parse a LifecycleEvent from a Lexicon record or union object."""
    obj = record.get("event", record)
    event_type = obj.get("$type")

    if event_type == "com.etzhayyim.organism.lifecycle#birth":
        return BirthEvent(
            reason=obj.get("reason", ""),
            council_attestation=obj.get("councilAttestation")
        )
    elif event_type == "com.etzhayyim.organism.lifecycle#clone":
        return CloneEvent(
            source_shard=obj.get("sourceShard", ""),
            target_shard=obj.get("targetShard", "")
        )
    elif event_type == "com.etzhayyim.organism.lifecycle#retire":
        return RetireEvent(
            reason=obj.get("reason", "")
        )
    elif event_type == "com.etzhayyim.organism.lifecycle#excommunication":
        return ExcommunicationEvent(
            council_attestation=obj.get("councilAttestation", ""),
            chigiri_procedure_ref=obj.get("chigiriProcedureRef", "")
        )
    raise ValueError(f"Unknown event type: {event_type}")

def lifecycle_event_to_lexicon(event: LifecycleEvent) -> dict:
    """Emit a Lexicon union object from a LifecycleEvent."""
    if isinstance(event, BirthEvent):
        res = {
            "$type": event._type,
            "reason": event.reason,
        }
        if event.council_attestation:
            res["councilAttestation"] = event.council_attestation
        return res
    elif isinstance(event, CloneEvent):
        return {
            "$type": event._type,
            "sourceShard": event.source_shard,
            "targetShard": event.target_shard,
        }
    elif isinstance(event, RetireEvent):
        return {
            "$type": event._type,
            "reason": event.reason,
        }
    elif isinstance(event, ExcommunicationEvent):
        return {
            "$type": event._type,
            "councilAttestation": event.council_attestation,
            "chigiriProcedureRef": event.chigiri_procedure_ref,
        }
    raise ValueError(f"Unknown event: {event}")

class OrganismLifecycle:
    def __init__(self, event_publisher: Optional[Callable[[dict], None]] = None) -> None:
        self.state = OrganismState.INACTIVE
        # List of (event, from_state, to_state, attestation_cid, timestamp)
        self.transition_history: list[tuple[LifecycleEvent, OrganismState, OrganismState, Optional[str], int]] = []
        self.parent_did: Optional[str] = None
        self.event_publisher = event_publisher

    def _record_transition(self, event: LifecycleEvent, to_state: OrganismState, attestation_cid: Optional[str]) -> None:
        from_state = self.state
        now = int(time.time())
        self.transition_history.append((event, from_state, to_state, attestation_cid, now))
        self.state = to_state

        if self.event_publisher:
            lexicon_event = lifecycle_event_to_lexicon(event)
            self.event_publisher(lexicon_event)

    def handle_birth(self, actor_did: str, council_attestation_cid: Optional[str] = None) -> None:
        if self.state != OrganismState.INACTIVE:
            raise InvalidLifecycleTransition(f"Cannot birth from state {self.state}")
        event = BirthEvent(
            reason=f"Birth of {actor_did}",
            council_attestation=council_attestation_cid
        )
        self._record_transition(event, OrganismState.ACTIVE, council_attestation_cid)

    def handle_clone(self, source_did: str, target_did: str, shard: str) -> None:
        if self.state != OrganismState.ACTIVE:
            raise InvalidLifecycleTransition(f"Cannot clone from state {self.state}")
        event = CloneEvent(source_shard=shard, target_shard=shard)
        self._record_transition(event, OrganismState.CLONED, None)
        self.parent_did = source_did

    def handle_retire(self, reason: str) -> None:
        if self.state != OrganismState.ACTIVE:
            raise InvalidLifecycleTransition(f"Cannot retire from state {self.state}")
        event = RetireEvent(reason=reason)
        self._record_transition(event, OrganismState.RETIRED, None)

    def handle_excommunication(self, council_attestation_cid: str, council_attestation_chain: list[str]) -> None:
        if self.state != OrganismState.ACTIVE:
            raise InvalidLifecycleTransition(f"Cannot excommunicate from state {self.state}")

        # >=4/7 Council attestation REQUIRED
        if len(council_attestation_chain) < 4:
            raise InvalidLifecycleTransition("Excommunication requires >=4/7 Council attestations")

        event = ExcommunicationEvent(
            council_attestation=council_attestation_cid,
            chigiri_procedure_ref=f"chigiri-G12-{council_attestation_cid}"
        )
        self._record_transition(event, OrganismState.EXCOMMUNICATED, council_attestation_cid)
