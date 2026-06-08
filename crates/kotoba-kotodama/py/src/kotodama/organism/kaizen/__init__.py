"""KaizenObserver — ecosystem self-reflection.

Per ADR-2605240200. The observer ingests fleet healthz + NDJSON queue
tails, runs a pluggable rule registry, emits KaizenProposal NDJSON lines
to ``/var/lib/etzhayyim/kaizen-proposals/observer.ndjson``.

Public surface:
  - ``ShardHealthz`` dataclass (one shard's /healthz snapshot)
  - ``QueueSample`` dataclass (one shard's recent post window)
  - ``Observation`` dataclass (per-tick aggregate)
  - ``KaizenProposal`` dataclass (one structured proposal)
  - ``KaizenRule`` Protocol (pure: Observation → list[KaizenProposal])
  - ``KaizenObserver`` class (probes, runs rules, dedups, emits)
  - ``RULE_REGISTRY`` — six built-in rules per ADR
"""

from __future__ import annotations

import json
import logging
import statistics
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

logger = logging.getLogger("kotodama.organism.kaizen")


PROPOSAL_SCHEMA_VERSION = 1


# ── Inputs ────────────────────────────────────────────────────────────


@dataclass
class ShardHealthz:
    """One /healthz snapshot from a fleet cell shard."""

    shard: int
    reachable: bool
    owned_count: int = 0
    warm_count: int = 0
    warm_capacity: int = 0
    tick_count: int = 0
    last_tick_duration_ms: float = 0.0
    total_posts: int = 0
    total_classifications: int = 0
    total_errors: int = 0
    uptime_s: int = 0
    error: str | None = None


@dataclass
class QueueSample:
    """Tail-of-queue statistics for one shard."""

    shard: int
    sample_count: int = 0
    mood_distribution: dict[str, int] = field(default_factory=dict)
    content_source_distribution: dict[str, int] = field(default_factory=dict)
    unique_codes: int = 0
    earliest_ts: int = 0
    latest_ts: int = 0


@dataclass
class SensorHealth:
    """One DatasetSensor's health snapshot.

    Per ADR-2605262400 §5 — fed into rules R7 (stale-sensor-pin) and
    R8 (charter-fail-rate). Populated by the corpus assembler / sensor
    runtime; the KaizenObserver reads it as input.
    """

    name: str  # subdataset name, e.g. "netreg/rir-delegated/apnic"
    tier: str  # Tier letter — "A" / "B" / "C" / "D"
    license: str
    refresh_cadence_sec: int
    latest_pin_created_at_ms: int = 0
    last_polled_at_ms: int = 0
    last_charter_fp_count: int = 0
    last_charter_total_count: int = 0
    assigned_node_count: int = 0
    note: str = ""


@dataclass
class LeakAttempt:
    """One tier-C leak event observed by a PostSink wrapper.

    Per ADR-2605262400 §5 R9 — critical backstop. A leak attempt is
    when a SensorObservation tagged ``internal_only=True`` reached a
    PostSink that is not on the internal-allow list. R9 fires
    unconditionally on the first attempt (no dedup window).
    """

    sensor: str
    tier: str
    sink_kind: str  # "logger" / "ndjson-queue" / "social-post" / etc.
    actor_did: str
    ts_ms: int
    detail: str = ""


@dataclass
class Observation:
    """All inputs to the rule engine for one observer tick."""

    ts: int  # ms
    shards: list[ShardHealthz] = field(default_factory=list)
    queues: list[QueueSample] = field(default_factory=list)
    # Per-shard rolling history. observer maintains; rules may read.
    history: dict[int, list[float]] = field(default_factory=dict)
    # Per ADR-2605262400 §5 — dataset sensor inputs to R7 / R8 / R9.
    sensors: list[SensorHealth] = field(default_factory=list)
    leak_attempts: list[LeakAttempt] = field(default_factory=list)


# ── Output ────────────────────────────────────────────────────────────


@dataclass
class SuggestedAction:
    kind: str  # config-change | code-change | doc-change | infra-change | issue-only
    description: str
    target_files: list[str] = field(default_factory=list)
    patch_hint: str = ""
    test_plan: list[str] = field(default_factory=list)
    # Structured, machine-applicable edits (preferred over patch_hint string
    # parsing). Each edit targets one file by an unambiguous selector:
    #   env-set:        {"file", "var", "value"}  — set a k8s env var's value
    #   literal-replace:{"file", "old", "new"}    — first-occurrence str replace
    # The Kaizen PR agent applies these deterministically; patch_hint remains
    # the human-readable summary and the fallback path.
    patch_edits: list[dict[str, str]] = field(default_factory=list)


@dataclass
class PrAgentHint:
    branch_prefix: str
    labels: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=lambda: ["human"])


@dataclass
class KaizenProposal:
    """One structured proposal. Schema v1 per ADR-2605240200."""

    rule_id: str
    category: str  # performance | reliability | content | infra | governance
    severity: str  # info | warn | critical
    actor_scope: str  # fleet | shard:N | code:c{code} | observer
    summary: str
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_action: SuggestedAction | None = None
    pr_agent_hint: PrAgentHint | None = None

    def to_ndjson_dict(self, ts_ms: int) -> dict[str, Any]:
        out: dict[str, Any] = {
            "v": PROPOSAL_SCHEMA_VERSION,
            "ts": ts_ms,
            "kind": "kaizen-proposal",
            "ruleId": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "actorScope": self.actor_scope,
            "summary": self.summary,
            "detail": self.detail,
            "evidence": self.evidence,
        }
        if self.suggested_action is not None:
            sa = self.suggested_action
            out["suggestedAction"] = {
                "kind": sa.kind,
                "description": sa.description,
                "targetFiles": sa.target_files,
                "patchHint": sa.patch_hint,
                "testPlan": sa.test_plan,
                "patchEdits": sa.patch_edits,
            }
        if self.pr_agent_hint is not None:
            out["prAgentHint"] = {
                "branchPrefix": self.pr_agent_hint.branch_prefix,
                "labels": self.pr_agent_hint.labels,
                "reviewers": self.pr_agent_hint.reviewers,
            }
        out["createdAt"] = (
            datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        return out


# ── Rule registry ─────────────────────────────────────────────────────


class KaizenRule(Protocol):
    rule_id: str

    def __call__(self, obs: Observation) -> list[KaizenProposal]:  # pragma: no cover
        ...


RULE_REGISTRY: dict[str, KaizenRule] = {}


def register_rule(rule_cls):  # type: ignore[no-untyped-def]
    """Register a rule class. Instantiates immediately so the registry
    holds callable instances, not classes."""
    instance = rule_cls()
    RULE_REGISTRY[rule_cls.rule_id] = instance
    return rule_cls


# ── Built-in rules (six per ADR-2605240200) ───────────────────────────


def _next_pow2_up(n: int) -> int:
    """Smallest power of two strictly greater than ``n`` (min 2)."""
    p = 1
    while p <= n:
        p <<= 1
    return max(p, 2)


def _pow2_at_least(n: int) -> int:
    """Smallest power of two >= ``n`` (min 1)."""
    p = 1
    while p < n:
        p <<= 1
    return p


def _lru_patch_hint(cur_capacity: int, new_value: int) -> str:
    """Auto-applicable patch hint for the daemonset LRU_MAX env value.

    Emits the ``'old' -> 'new'`` form the Kaizen PR agent applies directly
    (literal first-occurrence replace), so an Observer proposal flows to a
    real PR without a human translating the hint. Targets the k8s env value
    line ``value: "<N>"`` where N == current LRU_MAX (== warm_capacity).
    """
    return f"'value: \"{cur_capacity}\"' -> 'value: \"{new_value}\"'"


@register_rule
class SweepLatencyP95Rule:
    rule_id = "sweep-latency-p95"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for shard in obs.shards:
            if not shard.reachable:
                continue
            history = obs.history.get(shard.shard, [])
            if len(history) < 6:
                continue
            p95 = statistics.quantiles(history, n=20)[18] if len(history) >= 20 else max(history)
            if p95 <= 1000.0:
                continue
            severity = "critical" if p95 > 5000.0 else "warn"
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="performance",
                    severity=severity,
                    actor_scope=f"shard:{shard.shard}",
                    summary=f"shard-{shard.shard} sweep p95 = {p95:.0f} ms (target ≤ 1000 ms)",
                    detail=(
                        f"Over the last {len(history)} observer ticks, shard-{shard.shard}'s "
                        f"sweep duration p95 reached {p95:.0f} ms. Per ADR-2605240000 "
                        f"§Capacity math, warm-state sweep budget is well under 1 s."
                    ),
                    evidence={
                        "shard": shard.shard,
                        "tickDurationMsP95": p95,
                        "warmCount": shard.warm_count,
                        "warmCapacity": shard.warm_capacity,
                        "ownedCount": shard.owned_count,
                        "windowTicks": len(history),
                    },
                    suggested_action=SuggestedAction(
                        kind="config-change",
                        description=(
                            f"Increase UNISPSC_ORGANISM_LRU_MAX on shard-{shard.shard} "
                            f"or extend tick interval."
                        ),
                        target_files=[
                            f"50-infra/k8s/unispsc-organism-fleet/shard-{shard.shard}/daemonset.yaml"
                        ],
                        # Auto-applicable: bump LRU_MAX to the next power of two
                        # so the PR agent can patch + open a PR without a human
                        # translating the hint. warm_capacity == current LRU_MAX.
                        patch_hint=(
                            _lru_patch_hint(shard.warm_capacity, _next_pow2_up(shard.warm_capacity))
                            if shard.warm_capacity > 0
                            else "env UNISPSC_ORGANISM_LRU_MAX → next power-of-two up; verify against limits.memory."
                        ),
                        patch_edits=(
                            [{
                                "file": f"50-infra/k8s/unispsc-organism-fleet/shard-{shard.shard}/daemonset.yaml",
                                "var": "UNISPSC_ORGANISM_LRU_MAX",
                                "value": str(_next_pow2_up(shard.warm_capacity)),
                            }]
                            if shard.warm_capacity > 0
                            else []
                        ),
                        test_plan=[
                            "kubectl apply -k 50-infra/k8s/unispsc-organism-fleet/",
                            "wait 30 min and probe /healthz: tickDurationMsP95 ≤ 1000",
                            "kubectl top pod -n etzhayyim-organism: memory within limits",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/sweep-latency-shard-{shard.shard}-",
                        labels=["kaizen", "performance", "organism-fleet"],
                    ),
                )
            )
        return out


@register_rule
class LruSaturationRule:
    rule_id = "lru-saturation"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for shard in obs.shards:
            if not shard.reachable or shard.warm_capacity == 0:
                continue
            saturation = shard.warm_count / shard.warm_capacity
            if saturation < 0.99 or shard.owned_count <= shard.warm_capacity:
                continue
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="performance",
                    severity="warn",
                    actor_scope=f"shard:{shard.shard}",
                    summary=(
                        f"shard-{shard.shard} LRU saturated "
                        f"({shard.warm_count}/{shard.warm_capacity}) with "
                        f"{shard.owned_count} owned codes"
                    ),
                    detail=(
                        f"LRU at capacity while {shard.owned_count - shard.warm_capacity} "
                        f"codes have nowhere to live in warm cache. Likely thrashing on "
                        f"organism reload — adverse to tick latency."
                    ),
                    evidence={
                        "shard": shard.shard,
                        "warmCount": shard.warm_count,
                        "warmCapacity": shard.warm_capacity,
                        "ownedCount": shard.owned_count,
                    },
                    suggested_action=SuggestedAction(
                        kind="config-change",
                        description=f"Raise UNISPSC_ORGANISM_LRU_MAX on shard-{shard.shard}.",
                        target_files=[
                            f"50-infra/k8s/unispsc-organism-fleet/shard-{shard.shard}/daemonset.yaml"
                        ],
                        # Auto-applicable: size LRU_MAX to the next power of two
                        # >= owned_count so warm cache can hold all owned codes.
                        patch_hint=_lru_patch_hint(
                            shard.warm_capacity, _pow2_at_least(shard.owned_count)
                        ),
                        patch_edits=[{
                            "file": f"50-infra/k8s/unispsc-organism-fleet/shard-{shard.shard}/daemonset.yaml",
                            "var": "UNISPSC_ORGANISM_LRU_MAX",
                            "value": str(_pow2_at_least(shard.owned_count)),
                        }],
                        test_plan=[
                            "Apply and observe warmCount == ownedCount after warmup",
                            "Memory headroom: kubectl top pod inside limits",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/lru-shard-{shard.shard}-",
                        labels=["kaizen", "performance"],
                    ),
                )
            )
        return out


@register_rule
class ErrorRateRule:
    rule_id = "error-rate"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for shard in obs.shards:
            if not shard.reachable:
                continue
            total_ops = shard.total_classifications + shard.total_errors
            if total_ops < 100:  # not enough volume to judge
                continue
            rate = shard.total_errors / total_ops
            if rate < 0.01:
                continue
            severity = "critical" if rate > 0.10 else "warn"
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="reliability",
                    severity=severity,
                    actor_scope=f"shard:{shard.shard}",
                    summary=f"shard-{shard.shard} error rate = {rate * 100:.1f}%",
                    detail=(
                        f"{shard.total_errors} errors over {total_ops} ops. Worth "
                        f"inspecting per-code import failures (cache.import_failures) "
                        f"and tick-level exceptions in container logs."
                    ),
                    evidence={
                        "shard": shard.shard,
                        "totalErrors": shard.total_errors,
                        "totalClassifications": shard.total_classifications,
                        "errorRate": round(rate, 4),
                    },
                    suggested_action=SuggestedAction(
                        kind="issue-only",
                        description=(
                            "Triage by inspecting kubectl logs and identifying which "
                            "UNSPSC code(s) are failing repeatedly."
                        ),
                        test_plan=[
                            "kubectl logs -n etzhayyim-organism ds/unispsc-organism-fleet-"
                            f"shard-{shard.shard} | grep WARNING",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/error-rate-shard-{shard.shard}-",
                        labels=["kaizen", "reliability", "triage"],
                    ),
                )
            )
        return out


@register_rule
class PostThroughputStalledRule:
    rule_id = "post-throughput-stalled"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for shard in obs.shards:
            if not shard.reachable:
                continue
            if shard.total_posts > 0:
                continue
            if shard.tick_count < 12:  # warmup window
                continue
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="content",
                    severity="warn",
                    actor_scope=f"shard:{shard.shard}",
                    summary=(
                        f"shard-{shard.shard} has emitted 0 posts after "
                        f"{shard.tick_count} ticks"
                    ),
                    detail=(
                        "Either the inbox is starving (no inbound commits reaching "
                        "this shard) or the joucho personalities suppress posting too "
                        "aggressively (e.g. high baseline stress)."
                    ),
                    evidence={
                        "shard": shard.shard,
                        "tickCount": shard.tick_count,
                        "totalPosts": 0,
                        "totalClassifications": shard.total_classifications,
                    },
                    suggested_action=SuggestedAction(
                        kind="code-change",
                        description=(
                            "Seed synthetic inbound commits per organism (mirror of "
                            "cell_main._seed_self_inbox) or rebalance personality bias "
                            "to lower baseline stress for this segment range."
                        ),
                        target_files=[
                            "20-actors/kotoba-kotodama/py/src/kotodama/organism/fleet_cell_main.py",
                            "20-actors/kotoba-kotodama/py/src/kotodama/organism/personality.py",
                        ],
                        test_plan=[
                            "Re-run unit tests for personality + fleet cell",
                            "Re-apply manifest, verify totalPosts > 0 after 1 hour",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/post-throughput-shard-{shard.shard}-",
                        labels=["kaizen", "content"],
                    ),
                )
            )
        return out


@register_rule
class MoodConcentrationRule:
    rule_id = "mood-concentration"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for q in obs.queues:
            if q.sample_count < 100:
                continue
            total = sum(q.mood_distribution.values())
            if total == 0:
                continue
            top_mood, top_n = max(q.mood_distribution.items(), key=lambda kv: kv[1])
            share = top_n / total
            if share < 0.80:
                continue
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="content",
                    severity="info",
                    actor_scope=f"shard:{q.shard}",
                    summary=(
                        f"shard-{q.shard} mood concentration: {top_mood} = "
                        f"{share * 100:.0f}% of last {q.sample_count} posts"
                    ),
                    detail=(
                        "Personality bias may be too narrow for this segment range. "
                        "Consider widening hash entropy or revisiting segment_bias."
                    ),
                    evidence={
                        "shard": q.shard,
                        "moodDistribution": q.mood_distribution,
                        "sampleCount": q.sample_count,
                    },
                    suggested_action=SuggestedAction(
                        kind="code-change",
                        description="Tweak _SEGMENT_BIAS for over-represented mood's segments.",
                        target_files=[
                            "20-actors/kotoba-kotodama/py/src/kotodama/organism/personality.py",
                        ],
                        test_plan=[
                            "Re-run test_personality_axes_clamped + "
                            "test_organisms_have_distinct_personalities_in_shard",
                            "Re-apply manifest, verify mood diversity improves",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/mood-bias-shard-{q.shard}-",
                        labels=["kaizen", "content", "personality"],
                    ),
                )
            )
        return out


@register_rule
class FleetUnreachableRule:
    rule_id = "fleet-unreachable"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for shard in obs.shards:
            if shard.reachable:
                continue
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="infra",
                    severity="critical",
                    actor_scope=f"shard:{shard.shard}",
                    summary=f"shard-{shard.shard} /healthz unreachable",
                    detail=(
                        f"Probe failed: {shard.error or 'no detail'}. Pod down, "
                        "Service / Endpoint misconfigured, or network partition."
                    ),
                    evidence={
                        "shard": shard.shard,
                        "error": shard.error,
                    },
                    suggested_action=SuggestedAction(
                        kind="issue-only",
                        description=(
                            "Operator: kubectl get pods -n etzhayyim-organism + "
                            "kubectl describe to root-cause."
                        ),
                        test_plan=[
                            "kubectl get pods -n etzhayyim-organism -l etzhayyim.com/"
                            f"shard='{shard.shard}'",
                            "kubectl logs --previous if Pod was recently restarted",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/fleet-down-shard-{shard.shard}-",
                        labels=["kaizen", "incident", "infra"],
                        reviewers=["human", "on-call"],
                    ),
                )
            )
        return out


# ── Dataset-sensor rules (R7 / R8 / R9 per ADR-2605262400 §5) ────────


@register_rule
class StaleSensorPinRule:
    """R7 — sensor's latest datasetPin is older than 4× its refresh cadence.

    Suggests re-pulling the upstream archive and emitting a fresh
    datasetPin record. Severity = warn (organism keeps operating with a
    stale pin, but the data is drifting).
    """

    rule_id = "stale-sensor-pin"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for s in obs.sensors:
            # cadence unknown → cannot reason about staleness; skip.
            # latest_pin_created_at_ms == 0 means "never received a pin"
            # (epoch), which is maximally stale, NOT a skip condition: a
            # sensor running past 4× its cadence with no pin is exactly the
            # drift R7 must surface (age = obs.ts - 0 = obs.ts).
            if s.refresh_cadence_sec <= 0:
                continue
            age_ms = obs.ts - s.latest_pin_created_at_ms
            threshold_ms = s.refresh_cadence_sec * 1000 * 4
            if age_ms <= threshold_ms:
                continue
            age_h = age_ms / 3_600_000
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="content",
                    severity="warn",
                    actor_scope=f"sensor:{s.name}",
                    summary=(
                        f"sensor '{s.name}' pin age = {age_h:.1f}h "
                        f"(threshold = {s.refresh_cadence_sec * 4 / 3600:.0f}h)"
                    ),
                    detail=(
                        f"DatasetSensor '{s.name}' (tier {s.tier}, license "
                        f"{s.license}) has not received a fresh "
                        f"com.etzhayyim.substrate.datasetPin record in "
                        f"{age_h:.1f}h. Upstream cadence is "
                        f"{s.refresh_cadence_sec}s ≈ "
                        f"{s.refresh_cadence_sec / 3600:.1f}h. Per "
                        f"ADR-2605262400 G12, refresh MUST NOT undercut "
                        f"upstream cadence — but stale-by-4x is the floor."
                    ),
                    evidence={
                        "sensor": s.name,
                        "tier": s.tier,
                        "ageMs": age_ms,
                        "thresholdMs": threshold_ms,
                        "refreshCadenceSec": s.refresh_cadence_sec,
                    },
                    suggested_action=SuggestedAction(
                        kind="infra-change",
                        description=(
                            f"Operator: re-run `e7m-dataset pull <source>` "
                            f"for '{s.name}' and `e7m-dataset publish-ipfs` "
                            f"+ datasetPin emit."
                        ),
                        test_plan=[
                            f"e7m-dataset verify {s.name}",
                            "Check assigned_node_count >= 2 (replicationMin G3)",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/stale-pin-{s.name.replace('/', '-')}-",
                        labels=["kaizen", "content", "dataset-pin"],
                    ),
                )
            )
        return out


@register_rule
class CharterFalsePositiveRateRule:
    """R8 — Charter Rider §2 scanner false-positive rate > 5% / 24h.

    The scanner is heuristic (ADR-2605192200) and is expected to have
    some FP. >5% sustained means either the scanner pattern set is too
    aggressive on this sensor's vocabulary, or the operator-curated
    allow-context is too narrow. Either way it should be reviewed.
    """

    rule_id = "charter-fail-rate"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for s in obs.sensors:
            if s.last_charter_total_count < 100:
                continue
            rate = s.last_charter_fp_count / s.last_charter_total_count
            if rate <= 0.05:
                continue
            severity = "warn" if rate <= 0.20 else "critical"
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="governance",
                    severity=severity,
                    actor_scope=f"sensor:{s.name}",
                    summary=(
                        f"sensor '{s.name}' Charter §2 FP rate = "
                        f"{rate * 100:.1f}% (cap = 5%)"
                    ),
                    detail=(
                        f"Out of {s.last_charter_total_count} Charter Rider §2 "
                        f"scan invocations against sensor '{s.name}' in the "
                        f"last 24h, {s.last_charter_fp_count} were demoted by "
                        f"allow-context (rate {rate * 100:.1f}%). Per "
                        f"ADR-2605262400 G11, this triggers a scanner-spec "
                        f"review (allow-context regex widening, or category "
                        f"pattern tightening)."
                    ),
                    evidence={
                        "sensor": s.name,
                        "fpCount": s.last_charter_fp_count,
                        "totalCount": s.last_charter_total_count,
                        "rate": round(rate, 4),
                    },
                    suggested_action=SuggestedAction(
                        kind="code-change",
                        description=(
                            "Inspect charter_rider._RULES allow_context "
                            "patterns for this sensor's vocabulary. Council "
                            "Lv6+ ratifies threshold revisions."
                        ),
                        target_files=[
                            "20-actors/kotoba-kotodama/py/src/kotodama/organism/"
                            "sensors/charter_rider.py",
                        ],
                        test_plan=[
                            "pytest 70-tools/e7m-dataset/tests/test_charter.py",
                            "Re-run scanner over a fixed sample and confirm "
                            "FP rate drops below 5%",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/charter-fp-{s.name.replace('/', '-')}-",
                        labels=["kaizen", "governance", "charter-rider"],
                    ),
                )
            )
        return out


@register_rule
class TierCLeakBackstopRule:
    """R9 — CRITICAL constitutional backstop for G13 NC-leak prevention.

    Any tier-C SensorObservation reaching a non-allow-listed PostSink
    is a Council-grade incident. Severity = critical, no dedup window
    (every leak attempt is emitted), suggested_action = halt the
    organism cell and escalate.
    """

    rule_id = "tier-c-leak"

    def __call__(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for la in obs.leak_attempts:
            if la.tier != "C":
                continue
            out.append(
                KaizenProposal(
                    rule_id=self.rule_id,
                    category="governance",
                    severity="critical",
                    actor_scope=f"actor:{la.actor_did}",
                    summary=(
                        f"tier-C leak attempt: sensor '{la.sensor}' → "
                        f"sink '{la.sink_kind}' (actor {la.actor_did})"
                    ),
                    detail=(
                        f"A tier-C SensorObservation with internal_only=True "
                        f"reached PostSink '{la.sink_kind}' on actor "
                        f"{la.actor_did}. Per ADR-2605262400 §5 R9 + G4, "
                        f"this is a constitutional backstop incident. The "
                        f"offending organism cell SHOULD be halted and the "
                        f"event escalated to Council Lv6+ for review. "
                        f"Detail: {la.detail}"
                    ),
                    evidence={
                        "sensor": la.sensor,
                        "tier": la.tier,
                        "sinkKind": la.sink_kind,
                        "actorDid": la.actor_did,
                        "tsMs": la.ts_ms,
                    },
                    suggested_action=SuggestedAction(
                        kind="infra-change",
                        description=(
                            "Halt the offending organism cell. Audit the "
                            "PostSink wiring on its host. Council Lv6+ "
                            "reviews the incident and clears the cell back "
                            "online once root cause is fixed."
                        ),
                        target_files=[
                            "20-actors/kotoba-kotodama/py/src/kotodama/organism/post_sink.py",
                        ],
                        test_plan=[
                            "Re-run R9 leak-test harness "
                            "(70-tools/baien-moemoekyun-train/tests/test_r9_leak.py)",
                            "Audit `PostSink.send()` callsites for tier-C drop",
                        ],
                    ),
                    pr_agent_hint=PrAgentHint(
                        branch_prefix=f"kaizen/tier-c-leak-{la.actor_did.split(':')[-1]}-",
                        labels=["kaizen", "governance", "constitutional", "critical"],
                        reviewers=["human", "council-lv6+"],
                    ),
                )
            )
        return out


# ── Probe helpers ─────────────────────────────────────────────────────


def probe_shard_healthz(
    url: str,
    *,
    timeout_s: float = 5.0,
    http_get: Callable[[str, float], dict] | None = None,
) -> ShardHealthz:
    """GET <url>/healthz and coerce to ShardHealthz."""
    shard_index = _shard_from_url(url)
    fetch = http_get or _default_http_get
    try:
        body = fetch(url, timeout_s)
    except Exception as exc:  # noqa: BLE001
        return ShardHealthz(shard=shard_index, reachable=False, error=str(exc))
    return ShardHealthz(
        shard=int(body.get("shard", shard_index)),
        reachable=True,
        owned_count=int(body.get("ownedCount", 0)),
        warm_count=int(body.get("warmCount", 0)),
        warm_capacity=int(body.get("warmCapacity", 0)),
        tick_count=int(body.get("tickCount", 0)),
        last_tick_duration_ms=float(body.get("lastTickDurationMs", 0.0) or 0.0),
        total_posts=int(body.get("totalPosts", 0)),
        total_classifications=int(body.get("totalClassifications", 0)),
        total_errors=int(body.get("totalErrors", 0)),
        uptime_s=int(body.get("uptimeS", 0)),
    )


def _shard_from_url(url: str) -> int:
    # Best-effort: port 13040/50/60 → shard 0/1/2.
    if ":13040" in url:
        return 0
    if ":13050" in url:
        return 1
    if ":13060" in url:
        return 2
    return -1


def _default_http_get(url: str, timeout_s: float) -> dict:
    import urllib.request

    req = urllib.request.Request(f"{url.rstrip('/')}/healthz")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — internal LAN only
        return json.loads(resp.read().decode("utf-8"))


def sample_queue(path: str | Path, *, tail_lines: int = 1000) -> QueueSample:
    """Read the last ``tail_lines`` from an NDJSON queue and compute stats."""
    p = Path(path)
    shard_index = _shard_from_queue_path(p)
    if not p.exists():
        return QueueSample(shard=shard_index)
    # Simple tail: read whole file if small, otherwise seek from end.
    try:
        with p.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            # Heuristic: 1 KB per line is generous; tail_lines * 1 KB is enough.
            window = min(size, tail_lines * 1024)
            f.seek(max(0, size - window), 0)
            raw = f.read().decode("utf-8", errors="replace")
    except OSError:
        return QueueSample(shard=shard_index)
    lines = raw.splitlines()[-tail_lines:]
    moods: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    codes: set[str] = set()
    earliest = 0
    latest = 0
    parsed = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed += 1
        m = str(obj.get("mood") or "")
        if m:
            moods[m] += 1
        cs = str(obj.get("contentSourceKind") or "")
        if cs:
            sources[cs] += 1
        c = str(obj.get("code") or "")
        if c:
            codes.add(c)
        ts = int(obj.get("ts", 0) or 0)
        if ts > 0:
            earliest = ts if earliest == 0 else min(earliest, ts)
            latest = max(latest, ts)
    return QueueSample(
        shard=shard_index,
        sample_count=parsed,
        mood_distribution=dict(moods),
        content_source_distribution=dict(sources),
        unique_codes=len(codes),
        earliest_ts=earliest,
        latest_ts=latest,
    )


def _shard_from_queue_path(p: Path) -> int:
    name = p.name
    for n in (0, 1, 2):
        if f"shard-{n}" in name:
            return n
    return -1


# ── Observer ──────────────────────────────────────────────────────────


@dataclass
class _DedupKey:
    rule_id: str
    actor_scope: str


class KaizenObserver:
    """Probes the fleet, runs rules, emits proposals.

    Maintains a per-shard rolling history of ``lastTickDurationMs`` so
    rules can compute p95 without recomputing every tick.

    Dedup: same ``(rule_id, actor_scope)`` within ``dedup_window_s``
    (default 2 hours) is suppressed.
    """

    def __init__(
        self,
        shard_urls: Iterable[str],
        queue_paths: Iterable[Path | str],
        proposal_path: Path | str,
        *,
        history_size: int = 144,  # 24h at 10-min cadence
        dedup_window_s: int = 2 * 3600,
        http_get: Callable[[str, float], dict] | None = None,
    ):
        self.shard_urls = list(shard_urls)
        self.queue_paths = [Path(q) for q in queue_paths]
        self.proposal_path = Path(proposal_path)
        self.history_size = history_size
        self.dedup_window_s = dedup_window_s
        self.http_get = http_get
        self._history: dict[int, list[float]] = {}
        self._last_emit: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()
        self.actor_did = "did:web:etzhayyim.com:actor:kaizen-observer"
        self.tick_count = 0
        self.last_observation: Observation | None = None
        self.proposal_path.parent.mkdir(parents=True, exist_ok=True)
        self.proposal_path.touch(exist_ok=True)

    def probe(self, *, now_ms: int | None = None) -> Observation:
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        shards = [
            probe_shard_healthz(url, http_get=self.http_get) for url in self.shard_urls
        ]
        for s in shards:
            if not s.reachable:
                continue
            hist = self._history.setdefault(s.shard, [])
            hist.append(s.last_tick_duration_ms)
            if len(hist) > self.history_size:
                del hist[: len(hist) - self.history_size]
        queues = [sample_queue(q) for q in self.queue_paths]
        obs = Observation(ts=now, shards=shards, queues=queues, history=dict(self._history))
        self.last_observation = obs
        return obs

    def run_rules(self, obs: Observation) -> list[KaizenProposal]:
        out: list[KaizenProposal] = []
        for rule in RULE_REGISTRY.values():
            try:
                out.extend(rule(obs))
            except Exception as exc:  # noqa: BLE001 — observer stays alive
                logger.warning("rule %s failed: %s", getattr(rule, "rule_id", "?"), exc)
        return out

    def _filter_dedup(self, proposals: list[KaizenProposal], now_ms: int) -> list[KaizenProposal]:
        kept: list[KaizenProposal] = []
        window_ms = self.dedup_window_s * 1000
        for p in proposals:
            key = (p.rule_id, p.actor_scope)
            last = self._last_emit.get(key)
            if last is not None and now_ms - last < window_ms:
                continue
            self._last_emit[key] = now_ms
            kept.append(p)
        return kept

    def emit(self, proposals: list[KaizenProposal], *, ts_ms: int) -> int:
        if not proposals:
            return 0
        try:
            with self._lock, self.proposal_path.open("a", encoding="utf-8") as f:
                for p in proposals:
                    f.write(
                        json.dumps(
                            p.to_ndjson_dict(ts_ms),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("proposal emit failed: %s", exc)
            return 0
        return len(proposals)

    def tick(self, *, now_ms: int | None = None) -> dict[str, Any]:
        """One observation cycle. Returns a status dict for logging/tests."""
        self.tick_count += 1
        ts = now_ms if now_ms is not None else int(time.time() * 1000)
        obs = self.probe(now_ms=ts)
        proposals = self.run_rules(obs)
        kept = self._filter_dedup(proposals, ts)
        written = self.emit(kept, ts_ms=ts)
        return {
            "tickCount": self.tick_count,
            "shardCount": len(obs.shards),
            "reachable": sum(1 for s in obs.shards if s.reachable),
            "proposalsRaised": len(proposals),
            "proposalsAfterDedup": len(kept),
            "proposalsWritten": written,
        }


__all__ = [
    "CharterFalsePositiveRateRule",
    "ErrorRateRule",
    "FleetUnreachableRule",
    "KaizenObserver",
    "KaizenProposal",
    "KaizenRule",
    "LeakAttempt",
    "LruSaturationRule",
    "MoodConcentrationRule",
    "Observation",
    "PROPOSAL_SCHEMA_VERSION",
    "PostThroughputStalledRule",
    "PrAgentHint",
    "QueueSample",
    "RULE_REGISTRY",
    "SensorHealth",
    "ShardHealthz",
    "StaleSensorPinRule",
    "SuggestedAction",
    "SweepLatencyP95Rule",
    "TierCLeakBackstopRule",
    "probe_shard_healthz",
    "register_rule",
    "sample_queue",
]
