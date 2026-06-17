"""UnispscOrganism — wrap a classify graph into a tick-able organism.

Per ADR-2605232345. Combines:
  - a caller-supplied classify ``graph`` (``.invoke(state) -> dict``)
  - ``kotodama.organism.cadence.resolve_heartbeat_cadence`` (heartbeat)

The class is substrate-agnostic by design. ``post_sink`` and
``follower_score_provider`` are caller-supplied so the same class runs in
unit tests, the cell-runner LAN cell, and K8s Pods without modification.

The per-code ``unispsc_agents.c{code}`` generated agents were retired in
favour of the clj actor (etzhayyim/root@20-actors/unspsc); ``for_code`` now
builds a generic organism with a default no-op classify graph (every code
behaves as "no custom agent"), mirroring the runtime's prior fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from kotodama.organism.messaging import OrganismMessageReceiver
    from pathlib import Path

from kotodama.organism.cadence import (
    CadenceState,
    ContentSource,
    HeartbeatCadence,
    resolve_heartbeat_cadence,
)
from kotodama.organism.lifecycle import OrganismLifecycle, OrganismState
from kotodama.organism.inbox import (
    FollowerCurrentScore,
    FollowerReward,
    InboxBuffer,
)
from kotodama.organism.joucho import (
    JouchoScores,
    apply_sensor_delta,
)
from kotodama.organism.sensors.base import DatasetSensor, SensorObservation
from kotodama.organism.sensors.tier_gate import TierGate


# Bounded ring for sensor observations between organism ticks. Keeps
# memory predictable on long-running organisms — the sensor's
# `hot_sample(n)` yields a small slice each tick, but if a downstream
# consumer is slow to drain we don't want unbounded growth.
_MAX_SENSOR_OBSERVATIONS = 256

logger = logging.getLogger("kotodama.organism")


class _DefaultClassifyGraph:
    """No-op classify graph used when a code has no bespoke agent.

    The per-code ``unispsc_agents.c{code}`` modules were retired (the clj
    actor supersedes them); every code now resolves to this generic graph,
    mirroring the loader's prior ``no_custom_agent_found`` fallback.
    """

    def invoke(self, state: Any) -> dict[str, Any]:
        return {"result": "no_custom_agent"}


ClassifyInputFactory = Callable[["object"], dict[str, Any]]
# Legacy sink shape (text only). New code should pass a ``PostSink`` from
# kotodama.organism.post_sink that accepts kwargs (ctx + mood + source).
LegacyPostSink = Callable[[str], None]
PostSink = LegacyPostSink  # backwards-compatible alias
JouchoProvider = Callable[[str], JouchoScores]
FollowerScoreProvider = Callable[[str], list[FollowerCurrentScore]]


@dataclass
class OrganismTickResult:
    """What happened this tick."""

    cadence: HeartbeatCadence
    classifications: list[dict[str, Any]] = field(default_factory=list)
    posts: list[str] = field(default_factory=list)
    rewards: list[FollowerReward] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _default_classify_input_factory(commit: object) -> dict[str, Any]:
    """Default: pass the commit's rkey as the classify description."""
    rkey = getattr(commit, "rkey", "")
    return {"description": rkey}


def _format_post(
    code: str,
    title: str,
    cadence: HeartbeatCadence,
    classifications: list[dict[str, Any]],
) -> str | None:
    """Format the Shinka post text from the chosen content source.

    Returns None if cadence says not to post.
    """
    if not cadence.should_post or cadence.content_source.kind == "none":
        return None

    src = cadence.content_source
    if src.kind == "inbound" and classifications:
        last = classifications[-1]
        result = last.get("result") if isinstance(last, dict) else None
        permit = (result or {}).get("permit") if isinstance(result, dict) else None
        return (
            f"[{code}/{title}] inbound classify → "
            f"permit={permit!r} mood={cadence.mood}"
        )
    if src.kind == "reaction":
        return f"[{code}/{title}] reacted to engagement (mood={cadence.mood})"
    if src.kind == "recordAnalysis":
        return f"[{code}/{title}] mood={cadence.mood}; reflecting on recent classify history"
    if src.kind == "followerCelebration" and src.reward is not None:
        r = src.reward
        return (
            f"[{code}/{title}] celebrating follower {r.did} "
            f"({r.reward_type} on {r.metric})"
        )
    if src.kind == "moodShift":
        return f"[{code}/{title}] mood shifted {src.prev_mood} → {src.current_mood}"
    if src.kind == "dataRepair":
        return f"[{code}/{title}] dataRepair tick (missing={src.detail})"
    if src.kind == "milestone":
        return f"[{code}/{title}] milestone {src.detail}"
    return None


class UnispscOrganism:
    """Wrap one classify ``graph`` into a tick-able organism.

    The classify engine is the caller-supplied ``graph`` (``.invoke(state)``).
    The organism layer adds joucho mood + InboxBuffer + Shinka emission on
    top. ``for_code`` supplies a generic default graph (the per-code
    ``unispsc_agents.c{code}`` agents were retired for the clj actor).
    """

    def __init__(
        self,
        *,
        code: str,
        graph: Any,
        title: str = "",
        actor_did: str = "",
        classify_input_factory: ClassifyInputFactory | None = None,
        post_sink: PostSink | None = None,
        joucho_provider: JouchoProvider | None = None,
        follower_score_provider: FollowerScoreProvider | None = None,
        sensors: tuple[DatasetSensor, ...] = (),
        sensor_sample_size: int = 8,
        messaging_receiver: "OrganismMessageReceiver | None" = None,
        lifecycle_event_queue_path: "Path | None" = None,
    ) -> None:
        self.code = code
        self.title = title or f"c{code}"
        self.actor_did = actor_did or f"did:web:etzhayyim.com:actor:c{code}"
        self.graph = graph
        self.classify_input_factory = classify_input_factory or _default_classify_input_factory
        self.post_sink = post_sink
        self.joucho_provider = joucho_provider
        self.follower_score_provider = follower_score_provider
        self.messaging_receiver = messaging_receiver
        self.last_message_fetch_time: "datetime | None" = None
        self.inbox = InboxBuffer()
        self.cadence_state = CadenceState()

        publisher = None
        if lifecycle_event_queue_path:
            from kotodama.organism.lifecycle_publisher import NdjsonLifecyclePublisher

            publisher = NdjsonLifecyclePublisher(
                queue_path=lifecycle_event_queue_path,
                actor_did=self.actor_did,
            )
        self.lifecycle = OrganismLifecycle(event_publisher=publisher)

        self.tick_count = 0
        # Per ADR-2605262400 §4.3 — dataset sensor wiring.
        # ``sensors`` is a tuple of DatasetSensor instances. Each tick the
        # organism polls those whose `refresh_cadence_sec` has elapsed
        # since their last poll, asks them for `hot_sample(n=
        # sensor_sample_size)`, and stores the observations in a bounded
        # ring. The cadence wiring (joucho mood reflecting sensor
        # observations) is incremental — Wave-1 just exposes the
        # observations; deeper integration into joucho 情緒 lands in a
        # follow-up wave.
        self.sensors: tuple[DatasetSensor, ...] = tuple(sensors)
        self.sensor_sample_size = sensor_sample_size
        self.sensor_observations: list[SensorObservation] = []
        self.sensor_last_poll_ms: dict[str, int] = {}
        # Per ADR-2605262400 §4.3 Wave-3 — TierGate is auto-wired with
        # the organism's actor_did so external callers can wrap their
        # own SensorObservation sinks with ``organism.tier_gate.guard(
        # classification, sink_kind=..., wrapped=...)`` and the leak
        # backstop event count flows into the joucho stress delta.
        # Without external wiring, ``pop_leaks()`` returns an empty
        # list and the joucho path is no-op.
        self.tier_gate = TierGate(actor_did=self.actor_did)

    @classmethod
    def for_code(
        cls,
        code: str,
        *,
        title: str = "",
        actor_did: str = "",
        classify_input_factory: ClassifyInputFactory | None = None,
        post_sink: PostSink | None = None,
        joucho_provider: JouchoProvider | None = None,
        follower_score_provider: FollowerScoreProvider | None = None,
        sensors: tuple[DatasetSensor, ...] = (),
        sensor_sample_size: int = 8,
        messaging_receiver: "OrganismMessageReceiver | None" = None,
        lifecycle_event_queue_path: "Path | None" = None,
    ) -> "UnispscOrganism":
        """Build a generic organism for ``code`` with a default classify graph.

        The per-code ``c{code}`` agents were retired (superseded by the clj
        actor); every code now wraps the no-op :class:`_DefaultClassifyGraph`.
        """
        graph = _DefaultClassifyGraph()
        resolved_title = title or f"c{code}"
        resolved_did = actor_did or f"did:web:etzhayyim.com:actor:c{code}"
        return cls(
            code=code,
            graph=graph,
            title=resolved_title,
            actor_did=resolved_did,
            classify_input_factory=classify_input_factory,
            post_sink=post_sink,
            joucho_provider=joucho_provider,
            follower_score_provider=follower_score_provider,
            sensors=sensors,
            sensor_sample_size=sensor_sample_size,
            messaging_receiver=messaging_receiver,
            lifecycle_event_queue_path=lifecycle_event_queue_path,
        )

    def poll_sensors(self, now_ms: int) -> list[SensorObservation]:
        """Poll due sensors and append observations to the ring.

        A sensor is "due" when at least ``refresh_cadence_sec`` has
        elapsed since the organism's last poll of it. The first tick
        always polls every sensor (last_poll_ms unset).

        Returns the list of observations gathered this call (also
        appended to ``self.sensor_observations`` up to the ring cap).
        """
        gathered: list[SensorObservation] = []
        for s in self.sensors:
            last = self.sensor_last_poll_ms.get(s.name, 0)
            if last > 0:
                age_ms = now_ms - last
                if age_ms < s.refresh_cadence_sec * 1000:
                    continue
            try:
                pin = s.latest_pin()
                obs = s.hot_sample(pin, self.sensor_sample_size)
            except Exception as exc:  # noqa: BLE001 — sensors stay best-effort
                logger.warning(
                    "organism c%s sensor '%s' poll failed: %s",
                    self.code, s.name, exc,
                )
                continue
            gathered.extend(obs)
            self.sensor_last_poll_ms[s.name] = now_ms
        if gathered:
            self.sensor_observations.extend(gathered)
            # Bound the ring.
            excess = len(self.sensor_observations) - _MAX_SENSOR_OBSERVATIONS
            if excess > 0:
                del self.sensor_observations[:excess]
        return gathered

    def tick(self, *, now_ms: int) -> OrganismTickResult:
        """Run one heartbeat. Returns what was done.

        Synchronous so unit tests can drive ticks deterministically.
        Cell-runner wraps this in ``asyncio.to_thread`` if the heartbeat
        period is short enough to need cooperative scheduling.

        Per ADR-2605262400 §4.3 — sensors are polled first so the
        observations are visible to the cadence resolver in subsequent
        ticks (Wave-1 wiring just gathers; deeper joucho integration is
        a follow-up wave).
        """
        if self.lifecycle.state not in (OrganismState.ACTIVE, OrganismState.CLONED):
            from kotodama.organism.cadence import HeartbeatCadence, ContentSource
            dummy_cadence = HeartbeatCadence(
                should_post=False,
                should_analyze=False,
                should_drill=False,
                should_validate=False,
                should_engage=False,
                should_repair=False,
                follower_rewards=[],
                content_source=ContentSource(kind="none"),
                joucho=JouchoScores(),
                mood="neutral",
                post_cooldown_ms=0,
                reason=f"skipped (state={self.lifecycle.state.value})",
            )
            return OrganismTickResult(cadence=dummy_cadence)

        self.tick_count += 1
        tick_obs: list[SensorObservation] = []
        if self.sensors:
            tick_obs = self.poll_sensors(now_ms)

        if self.messaging_receiver is not None:
            # fetch messages since last fetch, or from epoch if never fetched
            since = self.last_message_fetch_time or datetime.fromtimestamp(0, tz=timezone.utc)
            fetch_time = datetime.now(timezone.utc)
            try:
                for msg in self.messaging_receiver.receive_for(self.actor_did, since):
                    self.inbox.ingest_message(msg)
                self.last_message_fetch_time = fetch_time
            except Exception as exc:  # noqa: BLE001
                logger.warning("c%s message receive failed: %s", self.code, exc)

        inbox_obs = list(self.inbox.observations)
        self.inbox.observations.clear()

        # Per ADR-2605262400 §4.3 Wave-2: wrap the caller's joucho
        # provider with a sensor-aware augmenter so the just-gathered
        # observations bias mood incrementally.
        tier_a_count = sum(1 for o in tick_obs if o.tier == "A") + sum(1 for o in inbox_obs if getattr(o, "tier", None) == "A")
        tier_c_count = sum(1 for o in tick_obs if o.tier == "C") + sum(1 for o in inbox_obs if getattr(o, "tier", None) == "C")

        from kotodama.organism.observation import (
            JouchoDelta,
            image_joucho_delta,
            audio_joucho_delta,
            numeric_joucho_delta,
            timeseries_joucho_delta,
        )

        mm_deltas: list[JouchoDelta] = []
        for obs in inbox_obs:
            if getattr(obs, "kind", None) == "image":
                mm_deltas.append(image_joucho_delta(obs))
            elif getattr(obs, "kind", None) == "audio":
                mm_deltas.append(audio_joucho_delta(obs))
            elif getattr(obs, "kind", None) == "numeric":
                baseline = float(getattr(obs, "context", {}).get("baseline", 0.0)) if getattr(obs, "context", None) else 0.0
                mm_deltas.append(numeric_joucho_delta(obs, baseline))
            elif getattr(obs, "kind", None) == "timeseries":
                mm_deltas.append(timeseries_joucho_delta(obs))

        # §4.3 Wave-3 — drain LeakAttempts accumulated by the organism's
        # TierGate since the previous tick. External callers wrap their
        # observation sinks with `organism.tier_gate.guard(...)`; tier-C
        # observations routed to an EXTERNAL_FACING sink are dropped
        # there and counted here so the stress delta rises.
        leaks_this_tick = self.tier_gate.pop_leaks()
        leak_count = sum(1 for la in leaks_this_tick if la.tier == "C")
        if leak_count > 0:
            logger.warning(
                "organism c%s observed %d tier-C leak attempt(s) this tick — R9 backstop pre-firing",
                self.code, leak_count,
            )
        base_provider = self.joucho_provider

        def _augmented_joucho(did: str) -> JouchoScores:
            base = base_provider(did) if base_provider else JouchoScores()
            if tier_a_count == 0 and tier_c_count == 0 and leak_count == 0 and not mm_deltas:
                return base
            return apply_sensor_delta(
                base,
                tier_a_obs_count=tier_a_count,
                tier_c_obs_count=tier_c_count,
                leak_attempts=leak_count,
                multi_modal_deltas=mm_deltas,
            )

        cadence = resolve_heartbeat_cadence(
            self.actor_did,
            self.cadence_state,
            self.inbox,
            now_ms=now_ms,
            # Use the augmented provider when sensors are configured OR
            # when leak attempts were recorded this tick — leaks can
            # come from an externally-instantiated TierGate even on an
            # organism that has no sensors of its own.
            joucho_provider=(
                _augmented_joucho
                if (self.sensors or leak_count > 0 or inbox_obs)
                else self.joucho_provider
            ),
            follower_score_provider=self.follower_score_provider,
        )

        classifications: list[dict[str, Any]] = []
        # If the chosen content source consumed an inbound commit, also
        # invoke the underlying classify graph on it. This is the bridge
        # from "organism" back to "specialist UNSPSC agent".
        src = cadence.content_source
        if cadence.should_post and src.kind == "inbound" and src.commit is not None:
            try:
                input_state = self.classify_input_factory(src.commit)
                terminal = self.graph.invoke(input_state)
                if isinstance(terminal, dict):
                    classifications.append(terminal)
                else:
                    classifications.append({"value": terminal})
            except Exception as exc:  # noqa: BLE001 — organism stays alive on classify failure
                logger.warning("c%s classify failed on tick %d: %s", self.code, self.tick_count, exc)

        posts: list[str] = []
        text = _format_post(self.code, self.title, cadence, classifications)
        if text is not None:
            posts.append(text)
            if self.post_sink is not None:
                try:
                    self._dispatch_post(text, cadence)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("c%s post_sink failed: %s", self.code, exc)
            self.cadence_state.last_post_at = now_ms

        if cadence.should_engage:
            self.cadence_state.last_engage_at = now_ms
        if cadence.should_analyze:
            self.cadence_state.last_analyze_at = now_ms
        if cadence.should_drill:
            self.cadence_state.last_drill_at = now_ms
        if cadence.should_validate:
            self.cadence_state.last_validate_at = now_ms
        if cadence.follower_rewards:
            self.cadence_state.last_reward_at = now_ms

        metadata: dict[str, Any] = {}
        if self.lifecycle.state == OrganismState.CLONED and self.lifecycle.parent_did:
            metadata["parent_did"] = self.lifecycle.parent_did

        return OrganismTickResult(
            cadence=cadence,
            classifications=classifications,
            posts=posts,
            rewards=list(cadence.follower_rewards),
            metadata=metadata,
        )

    def _dispatch_post(self, text: str, cadence: Any) -> None:
        """Call post_sink with the right signature.

        Supports both the legacy text-only ``Callable[[str], None]`` and
        the ADR-2605240100 context-aware ``PostSink`` from
        ``kotodama.organism.post_sink``.
        """
        sink = self.post_sink
        if sink is None:
            return
        try:
            sink(  # type: ignore[call-arg]
                text,
                ctx=self,
                mood=cadence.mood,
                content_source_kind=cadence.content_source.kind,
            )
            return
        except TypeError:
            pass
        sink(text)  # legacy text-only signature


__all__ = [
    "ClassifyInputFactory",
    "FollowerScoreProvider",
    "JouchoProvider",
    "OrganismTickResult",
    "PostSink",
    "UnispscOrganism",
]
