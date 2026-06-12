"""resolve_heartbeat_cadence — main entry point.

Port of ``heartbeat-cadence.ts`` §Main resolver + §Content source resolution
+ §Shannon content diversity. Numbers + branch ordering match the TS source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from kotodama.organism.inbox import (
    FollowerCurrentScore,
    FollowerReward,
    InboxBuffer,
    detect_follower_rewards,
    update_follower_snapshots,
)
from kotodama.organism.joucho import (
    JouchoScores,
    Mood,
    apply_stress_scaling,
    determine_mood,
    mood_to_cadence,
)

# ── ContentSource ─────────────────────────────────────────────────────────

ContentSourceKind = Literal[
    "inbound",
    "reaction",
    "recordAnalysis",
    "moodShift",
    "milestone",
    "followerCelebration",
    "dataRepair",
    "none",
]


@dataclass
class ContentSource:
    """Discriminated union — what the organism should post about.

    Only one of ``commit / reaction / reward / prev_mood / detail`` is set,
    based on ``kind``. The discriminator is the source of truth.
    """

    kind: ContentSourceKind
    commit: "object | None" = None
    reaction: "object | None" = None
    reward: FollowerReward | None = None
    prev_mood: Mood | None = None
    current_mood: Mood | None = None
    detail: str | None = None


# ── HeartbeatCadence + CadenceState ───────────────────────────────────────


@dataclass
class HeartbeatCadence:
    should_post: bool
    should_analyze: bool
    should_drill: bool
    should_validate: bool
    should_engage: bool
    should_repair: bool
    follower_rewards: list[FollowerReward]
    content_source: ContentSource
    joucho: JouchoScores
    mood: Mood
    post_cooldown_ms: int
    reason: str


@dataclass
class _RecentPostType:
    type: str
    ts: int


@dataclass
class CadenceState:
    last_post_at: int = 0
    last_analyze_at: int = 0
    last_drill_at: int = 0
    last_validate_at: int = 0
    last_engage_at: int = 0
    last_reward_at: int = 0
    recent_post_types: list[_RecentPostType] = field(default_factory=list)


# ── Shannon content diversity ─────────────────────────────────────────────

_MAX_SAME_TYPE_CONSECUTIVE = 2
_DIVERSITY_WINDOW_MS = 2 * 3_600_000


def _is_content_type_saturated(state: CadenceState, source_type: str, now_ms: int) -> bool:
    state.recent_post_types = [
        e for e in state.recent_post_types if now_ms - e.ts < _DIVERSITY_WINDOW_MS
    ]
    consecutive = 0
    for entry in reversed(state.recent_post_types):
        if entry.type == source_type:
            consecutive += 1
        else:
            break
    return consecutive >= _MAX_SAME_TYPE_CONSECUTIVE


def _record_post_type(state: CadenceState, source_type: str, now_ms: int) -> None:
    state.recent_post_types.append(_RecentPostType(type=source_type, ts=now_ms))
    if len(state.recent_post_types) > 20:
        del state.recent_post_types[: len(state.recent_post_types) - 20]


# ── Content source resolution ─────────────────────────────────────────────


def _resolve_content_source(
    mood: Mood,
    inbox: InboxBuffer,
    rewards: list[FollowerReward],
) -> ContentSource:
    if inbox.profile_incomplete:
        return ContentSource(kind="dataRepair", detail="profile")

    prev_mood: Mood | None
    if inbox.prev_joucho is not None and isinstance(inbox.prev_joucho, JouchoScores):
        prev_mood = determine_mood(inbox.prev_joucho)
    else:
        prev_mood = None
    mood_shifted = prev_mood is not None and prev_mood != mood

    has_commits = len(inbox.inbound_commits) > 0
    has_reactions = len(inbox.reactions) > 0
    has_rewards = len(rewards) > 0

    if mood == "joyful":
        if has_rewards:
            return ContentSource(kind="followerCelebration", reward=rewards[0])
        if has_commits:
            return ContentSource(kind="inbound", commit=inbox.inbound_commits[0])
        if mood_shifted:
            return ContentSource(kind="moodShift", prev_mood=prev_mood, current_mood=mood)
        return ContentSource(kind="recordAnalysis")

    if mood == "calm":
        if has_reactions:
            return ContentSource(kind="reaction", reaction=inbox.reactions[0])
        if has_commits:
            return ContentSource(kind="inbound", commit=inbox.inbound_commits[0])
        if mood_shifted:
            return ContentSource(kind="moodShift", prev_mood=prev_mood, current_mood=mood)
        return ContentSource(kind="recordAnalysis")

    if mood == "stressed":
        return ContentSource(kind="none")

    if mood == "grateful":
        if has_reactions:
            return ContentSource(kind="reaction", reaction=inbox.reactions[0])
        if has_rewards:
            return ContentSource(kind="followerCelebration", reward=rewards[0])
        if has_commits:
            return ContentSource(kind="inbound", commit=inbox.inbound_commits[0])
        return ContentSource(kind="recordAnalysis")

    if mood == "focused":
        if has_commits:
            return ContentSource(kind="inbound", commit=inbox.inbound_commits[0])
        return ContentSource(kind="recordAnalysis")

    # neutral
    if has_reactions:
        return ContentSource(kind="reaction", reaction=inbox.reactions[0])
    if has_commits:
        return ContentSource(kind="inbound", commit=inbox.inbound_commits[0])
    if has_rewards:
        return ContentSource(kind="followerCelebration", reward=rewards[0])
    return ContentSource(kind="recordAnalysis")


# ── Main entry ────────────────────────────────────────────────────────────

JouchoProvider = Callable[[str], JouchoScores]
FollowerScoreProvider = Callable[[str], list[FollowerCurrentScore]]


def _default_joucho_provider(_did: str) -> JouchoScores:
    return JouchoScores()


def _default_follower_provider(_did: str) -> list[FollowerCurrentScore]:
    return []


def resolve_heartbeat_cadence(
    actor_did: str,
    state: CadenceState,
    inbox: InboxBuffer,
    now_ms: int,
    *,
    joucho_provider: JouchoProvider | None = None,
    follower_score_provider: FollowerScoreProvider | None = None,
) -> HeartbeatCadence:
    """Decide what the organism should do this tick.

    Three outputs (matching TS):
      1. cadence flags (should_post / should_engage / should_drill /
         should_analyze / should_validate / should_repair)
      2. content_source — what to post about
      3. follower_rewards — who to like/love

    Args:
        actor_did: DID of the organism (passed to providers).
        state: mutable cooldown timestamps + post-type window.
        inbox: mutable inbound buffer.
        now_ms: current time in ms (caller-supplied for testability).
        joucho_provider: 5-axis score lookup; default returns neutral.
        follower_score_provider: follower score lookup; default returns [].
    """
    jp = joucho_provider or _default_joucho_provider
    fp = follower_score_provider or _default_follower_provider

    joucho = jp(actor_did)
    follower_scores = (
        fp(actor_did) if (now_ms - state.last_reward_at) >= 5 * 60_000 else []
    )

    mood = determine_mood(joucho)
    cadence = mood_to_cadence(mood)
    cadence = apply_stress_scaling(cadence, joucho.stress)

    follower_rewards = (
        detect_follower_rewards(follower_scores, inbox.follower_snapshots)
        if follower_scores
        else []
    )
    if follower_scores:
        update_follower_snapshots(inbox.follower_snapshots, follower_scores)

    should_post = cadence.post_enabled and (now_ms - state.last_post_at >= cadence.post_cooldown_ms)
    should_analyze = cadence.analyze_enabled and (
        now_ms - state.last_analyze_at >= cadence.analyze_cooldown_ms
    )
    should_drill = cadence.drill_enabled and (now_ms - state.last_drill_at >= cadence.drill_cooldown_ms)
    should_validate = cadence.validate_enabled and (
        now_ms - state.last_validate_at >= cadence.validate_cooldown_ms
    )
    should_engage = cadence.engage_enabled and (now_ms - state.last_engage_at >= cadence.engage_cooldown_ms)
    should_repair = bool(inbox.profile_incomplete)

    if should_repair:
        content_source = _resolve_content_source(mood, inbox, follower_rewards)
    elif should_post:
        content_source = _resolve_content_source(mood, inbox, follower_rewards)
    else:
        content_source = ContentSource(kind="none")

    # Shannon diversity gate
    if (
        should_post
        and content_source.kind != "none"
        and content_source.kind != "dataRepair"
        and _is_content_type_saturated(state, content_source.kind, now_ms)
    ):
        alternatives: list[ContentSourceKind] = [
            "inbound",
            "reaction",
            "recordAnalysis",
            "followerCelebration",
            "moodShift",
        ]
        replaced = False
        for alt in alternatives:
            if alt == content_source.kind:
                continue
            if _is_content_type_saturated(state, alt, now_ms):
                continue
            if alt == "inbound" and inbox.inbound_commits:
                content_source = ContentSource(kind="inbound", commit=inbox.inbound_commits[0])
                replaced = True
                break
            if alt == "reaction" and inbox.reactions:
                content_source = ContentSource(kind="reaction", reaction=inbox.reactions[0])
                replaced = True
                break
            if alt == "recordAnalysis":
                content_source = ContentSource(kind="recordAnalysis")
                replaced = True
                break
            if alt == "followerCelebration" and follower_rewards:
                content_source = ContentSource(kind="followerCelebration", reward=follower_rewards[0])
                replaced = True
                break
        if not replaced:
            content_source = ContentSource(kind="none")

    if should_post and content_source.kind != "none":
        _record_post_type(state, content_source.kind, now_ms)

    # Consume the inbox item that drove the chosen content source
    if (should_post or should_repair) and content_source.kind != "none":
        if content_source.kind == "inbound" and inbox.inbound_commits:
            inbox.inbound_commits.pop(0)
        elif content_source.kind == "reaction" and inbox.reactions:
            inbox.reactions.pop(0)

    inbox.prev_joucho = joucho

    parts: list[str] = []
    if should_repair:
        parts.append(f"repair:{content_source.kind}")
    if should_post:
        parts.append(f"post:{content_source.kind}")
    if should_engage:
        parts.append("engage")
    if follower_rewards:
        parts.append(f"reward:{len(follower_rewards)}")
    if should_drill:
        parts.append("drill")
    if should_analyze:
        parts.append("analyze")
    if should_validate:
        parts.append("validate")
    action_str = "+".join(parts) if parts else "noop"
    reason = (
        f"{mood} (j={joucho.joy} c={joucho.calm} s={joucho.stress} "
        f"g={joucho.gratitude} f={joucho.focus}) → {action_str}"
    )

    return HeartbeatCadence(
        should_post=should_post,
        should_analyze=should_analyze,
        should_drill=should_drill,
        should_validate=should_validate,
        should_engage=should_engage,
        should_repair=should_repair,
        follower_rewards=follower_rewards,
        content_source=content_source,
        joucho=joucho,
        mood=mood,
        post_cooldown_ms=cadence.post_cooldown_ms,
        reason=reason,
    )


__all__ = [
    "CadenceState",
    "ContentSource",
    "ContentSourceKind",
    "FollowerScoreProvider",
    "HeartbeatCadence",
    "JouchoProvider",
    "resolve_heartbeat_cadence",
]
