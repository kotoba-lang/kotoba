"""InboxBuffer + FollowerReward — what an organism receives between ticks.

Port of ``heartbeat-cadence.ts`` §Types + §Follower wellness/dojo query +
§detectFollowerRewards. Bounded buffers (commits 100, reactions 50) match
the TS source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ReactionType = Literal["like", "repost", "reply", "mention"]
FollowerMetric = Literal["wellness", "dojo", "both"]
RewardType = Literal["like", "love"]

_MAX_COMMITS = 100
_MAX_REACTIONS = 50
_MAX_OBSERVATIONS = 100


@dataclass
class InboundCommit:
    collection: str
    repo: str
    rkey: str
    time: str


@dataclass
class InboundReaction:
    type: ReactionType
    uri: str
    from_: str
    time: str


@dataclass
class FollowerSnapshot:
    wellness_score: float
    dojo_score: float
    rank: str


@dataclass
class FollowerCurrentScore:
    """Latest follower score read (input to reward delta detection)."""

    did: str
    wellness_score: float
    dojo_score: float
    rank: str
    latest_post_uri: str | None = None


@dataclass
class FollowerReward:
    did: str
    metric: FollowerMetric
    wellness_delta: float
    dojo_delta: float
    reward_type: RewardType
    latest_post_uri: str | None


@dataclass
class InboxBuffer:
    """Bounded buffer of inbound events between ticks."""

    inbound_commits: list[InboundCommit] = field(default_factory=list)
    reactions: list[InboundReaction] = field(default_factory=list)
    observations: list["Observation"] = field(default_factory=list)
    prev_joucho: "object | None" = None  # JouchoScores at last tick (avoid cyclic import)
    follower_snapshots: dict[str, FollowerSnapshot] = field(default_factory=dict)
    profile_incomplete: bool = False

    def push(self, observation: 'str | "Observation"') -> None:
        import time

        if isinstance(observation, str):
            from kotodama.organism.observation import TextObservation
            obs = TextObservation(
                actorDid="",
                createdAt=int(time.time() * 1000),
                tier="A",
                text=observation,
            )
        else:
            obs = observation

        # tier == "C" -> bind internal_only=True flag
        if obs.tier == "C":
            obs.internal_only = True

        self.observations.append(obs)
        if len(self.observations) > _MAX_OBSERVATIONS:
            del self.observations[: len(self.observations) - _MAX_OBSERVATIONS]

    def ingest_message(self, message: "OrganismMessage") -> None:
        """Convert an OrganismMessage into a TextObservation and push it to the buffer."""
        import time
        from kotodama.organism.observation import TextObservation

        obs = TextObservation(
            actorDid=message.actor_did,
            createdAt=int(time.time() * 1000),
            tier="A",
            text=message.text,
        )
        if message.thread_id is not None:
            # We use BaseModel's extra="allow" to attach arbitrary fields like metadata
            obs.metadata = {"thread_id": message.thread_id}

        self.push(obs)

    def flush_to_warm(self, memory: "MemoryPersistence") -> list[str]:
        """Flush old observations to warm storage if capacity exceeds 75%.
        Keeps the newest 25% in the hot buffer to maintain context.
        """
        threshold = int(_MAX_OBSERVATIONS * 0.75)
        keep_count = int(_MAX_OBSERVATIONS * 0.25)

        if len(self.observations) > threshold:
            flush_count = len(self.observations) - keep_count
            to_flush = self.observations[:flush_count]

            cids = memory.warm_flush(to_flush)

            self.observations = self.observations[flush_count:]
            return cids
        return []

    def add_commit(self, commit: InboundCommit) -> None:
        self.inbound_commits.append(commit)
        if len(self.inbound_commits) > _MAX_COMMITS:
            del self.inbound_commits[: len(self.inbound_commits) - _MAX_COMMITS]

    def add_reaction(self, reaction: InboundReaction) -> None:
        self.reactions.append(reaction)
        if len(self.reactions) > _MAX_REACTIONS:
            del self.reactions[: len(self.reactions) - _MAX_REACTIONS]


def detect_follower_rewards(
    current: list[FollowerCurrentScore],
    snapshots: dict[str, FollowerSnapshot],
) -> list[FollowerReward]:
    """Compare current scores to last-tick snapshots; emit like/love for positive deltas.

    Reward rule (port of TS):
      - skip if no snapshot (first observation)
      - skip if both deltas ≤0
      - "love" if wellness_delta ≥10 OR dojo_delta ≥1; else "like"
      - sort by total improvement descending
    """
    rewards: list[FollowerReward] = []
    for f in current:
        prev = snapshots.get(f.did)
        if prev is None:
            continue
        w_delta = f.wellness_score - prev.wellness_score
        d_delta = f.dojo_score - prev.dojo_score
        if w_delta <= 0 and d_delta <= 0:
            continue
        if w_delta > 0 and d_delta > 0:
            metric: FollowerMetric = "both"
        elif w_delta > 0:
            metric = "wellness"
        else:
            metric = "dojo"
        reward_type: RewardType = "love" if (w_delta >= 10 or d_delta >= 1) else "like"
        rewards.append(
            FollowerReward(
                did=f.did,
                metric=metric,
                wellness_delta=w_delta,
                dojo_delta=d_delta,
                reward_type=reward_type,
                latest_post_uri=f.latest_post_uri,
            )
        )
    rewards.sort(key=lambda r: r.wellness_delta + r.dojo_delta, reverse=True)
    return rewards


def update_follower_snapshots(
    snapshots: dict[str, FollowerSnapshot],
    current: list[FollowerCurrentScore],
) -> None:
    for f in current:
        snapshots[f.did] = FollowerSnapshot(
            wellness_score=f.wellness_score,
            dojo_score=f.dojo_score,
            rank=f.rank,
        )


__all__ = [
    "FollowerCurrentScore",
    "FollowerMetric",
    "FollowerReward",
    "FollowerSnapshot",
    "InboundCommit",
    "InboundReaction",
    "InboxBuffer",
    "ReactionType",
    "RewardType",
    "detect_follower_rewards",
    "update_follower_snapshots",
]
