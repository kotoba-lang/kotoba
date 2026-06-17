"""kotodama.organism — joucho heartbeat-cadence + generic actor wrapper.

Per ADR-2605232345 (actor as ecosystem organism).

Python port of the TS heartbeat-cadence pattern in
``@etzhayyim/kotoba-kotodama-host-sdk/src/heartbeat-cadence.ts``. Wraps a
caller-supplied classify ``graph`` into a tick-able organism with joucho 情緒
mood, InboxBuffer, FollowerReward, Shannon content diversity, and Shinka post
emission. (The per-code UNSPSC agents this once wrapped were retired for the
clj unspsc actor; ``Organism.for_code`` now supplies a generic default graph.)
"""

from __future__ import annotations

from kotodama.organism.cadence import (
    CadenceState,
    ContentSource,
    HeartbeatCadence,
    resolve_heartbeat_cadence,
)
from kotodama.organism.inbox import (
    FollowerReward,
    FollowerSnapshot,
    InboundCommit,
    InboundReaction,
    InboxBuffer,
)
from kotodama.organism.joucho import (
    JouchoScores,
    Mood,
    apply_stress_scaling,
    determine_mood,
    mood_to_cadence,
)
from kotodama.organism.kaizen import (
    CharterFalsePositiveRateRule,
    KaizenObserver,
    KaizenProposal,
    KaizenRule,
    LeakAttempt,
    Observation,
    RULE_REGISTRY,
    SensorHealth,
    StaleSensorPinRule,
    TierCLeakBackstopRule,
    register_rule,
)
from kotodama.organism.post_sink import (
    LoggerPostSink,
    NdjsonQueuePostSink,
    NullPostSink,
    PostSink,
    resolve_post_sink,
)
from kotodama.organism.organism import (
    OrganismTickResult,
    Organism,
)

__all__ = [
    "CadenceState",
    "CharterFalsePositiveRateRule",
    "ContentSource",
    "FollowerReward",
    "FollowerSnapshot",
    "HeartbeatCadence",
    "InboundCommit",
    "InboundReaction",
    "InboxBuffer",
    "JouchoScores",
    "KaizenObserver",
    "KaizenProposal",
    "KaizenRule",
    "LeakAttempt",
    "LoggerPostSink",
    "Mood",
    "NdjsonQueuePostSink",
    "NullPostSink",
    "Observation",
    "OrganismTickResult",
    "PostSink",
    "RULE_REGISTRY",
    "SensorHealth",
    "StaleSensorPinRule",
    "TierCLeakBackstopRule",
    "Organism",
    "apply_stress_scaling",
    "determine_mood",
    "mood_to_cadence",
    "register_rule",
    "resolve_heartbeat_cadence",
    "resolve_post_sink",
]
