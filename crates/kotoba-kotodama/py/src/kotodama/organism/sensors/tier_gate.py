"""TierGate — the G4 / R9 enforcement seam for SensorObservation routing.

Per ADR-2605262400 §5 + G4. SensorObservations flow from a sensor's
``hot_sample`` / ``stream`` into a sink (InboxBuffer, PostSink-adapter,
file writer, etc.). When the observation carries ``internal_only=True``
it MUST be dropped on any external-facing sink, and the attempt MUST
be recorded as a ``LeakAttempt`` for the R9 backstop rule.

This module provides the gate as a small middleware that any caller
(an organism tick, the corpus assembler, a debug script) wraps around
its observation-handling callback. Direct sink callsites that want to
emit observations to non-internal destinations MUST route through this
gate.

Three sink classifications:

  - ``EXTERNAL_FACING`` — anything reachable by the open internet
    (PostSink → atproto, public NDJSON queues read by the public
    drainer, broadcast peers). MUST drop tier-C internal_only=True.
  - ``INTERNAL_ONLY`` — fleet-internal-only paths (judah LiteLLM +
    SBT-gate, in-memory inbox, encrypted-record persistence). MAY
    pass tier-C observations.
  - ``OBSERVABILITY`` — telemetry/logging that NEVER reaches the open
    internet (Murakumo-local OTLP, per-cell debug log). MAY pass.

Wiring example:

    from kotodama.organism.sensors.tier_gate import (
        TierGate, SinkClassification,
    )
    from kotodama.organism.kaizen import LeakAttempt

    gate = TierGate(actor_did="did:web:etzhayyim.com:actor:c12345678")

    def external_sink(obs):  # writes to a public NDJSON queue
        public_queue.append(obs.payload)

    @gate.guard(SinkClassification.EXTERNAL_FACING, sink_kind="public-ndjson",
                wrapped=external_sink)
    def routed_sink(obs):
        pass

    routed_sink(some_tier_c_observation)
    # → dropped + leak_attempts collected (visible via gate.pop_leaks())
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Callable

from kotodama.organism.kaizen import LeakAttempt

from .base import SensorObservation


class SinkClassification(enum.Enum):
    EXTERNAL_FACING = "external-facing"
    INTERNAL_ONLY = "internal-only"
    OBSERVABILITY = "observability"


SinkCallable = Callable[[SensorObservation], None]


@dataclass
class TierGate:
    """A per-actor gate that records leak attempts as it drops observations.

    Not a global; one TierGate per organism cell. The cell pumps
    ``pop_leaks()`` into the KaizenObserver Observation each tick so the
    R9 rule can fire.
    """

    actor_did: str = "did:web:etzhayyim.com:actor:unknown"
    leak_attempts: list[LeakAttempt] = field(default_factory=list)

    def pop_leaks(self) -> list[LeakAttempt]:
        """Return + clear the pending leak attempts."""
        out = self.leak_attempts
        self.leak_attempts = []
        return out

    def guard(
        self,
        classification: SinkClassification,
        *,
        sink_kind: str,
        wrapped: SinkCallable,
    ) -> SinkCallable:
        """Wrap a sink callable with the tier-C drop policy."""

        def _gated(obs: SensorObservation) -> None:
            if obs.internal_only and classification is SinkClassification.EXTERNAL_FACING:
                # G4 drop + R9 leak-attempt record.
                self.leak_attempts.append(
                    LeakAttempt(
                        sensor=obs.sensor,
                        tier=obs.tier,
                        sink_kind=sink_kind,
                        actor_did=self.actor_did,
                        ts_ms=int(time.time() * 1000),
                        detail=(
                            f"dropped internal_only observation at "
                            f"external-facing sink '{sink_kind}'"
                        ),
                    )
                )
                return
            wrapped(obs)

        return _gated


__all__ = ["SinkClassification", "TierGate"]
