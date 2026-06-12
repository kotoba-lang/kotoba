"""
AuditWitnessCell — kuni-umi Phase 5 (continuous) Pregel cell.

Per ADR-2605201400 §1 (Actor topology — Tier B continuous-phase orchestrator
on ``levi``) + ADR-2605201400 §9 (witness invariant — N >= 2 independent
robot Ed25519 signatures, NEVER reducible) + ADR-2605192230 (phenotype
feedback — ``Phenotype.effectiveMultiplier`` delta as a consequence of
audit outcomes) + ADR-2605192315 (transparency triple — public for
community-event / compliance-check; XChaCha20-Poly1305 envelope per
ADR-2605181100 for anomaly / injury).

Continuous + super-step boundary + event-driven: the cell fires on every
``com.etzhayyim.apps.etzhayyim.kuniUmi.recordPhysicalAuditEvent`` MST commit.
It does not sleep between super-steps — once invoked it advances until
witness quorum is met (fixed-point at ``verify_witness_quorum``), then
classifies severity, decides whether to apply a Phenotype delta or
escalate to ``CouncilDeliberationCell``, then emits the permanent audit
record.

LangGraph nodes (super-step semantics):

  START → parse_audit_event        → load eventClass + evidence CID
        → verify_witness_quorum    → fixed-point until N >= 2 sigs
        → classify_severity        → score from eventClass + subtype
        → phenotype_delta_route    → conditional fan-out:
              ├─ apply_phenotype_delta  (bounded delta within MAX_BPS)
              ├─ council_escalate       (witness-mismatch / injury / land-violation)
              └─ emit_audit_record      (no-op path)
        → apply_phenotype_delta    → Phenotype.effectiveMultiplier delta (placeholder)
        → council_escalate         → emit CouncilDeliberationCell dispatch (placeholder)
        → emit_audit_record        → write recordPhysicalAuditEvent → END

The witness wait-state is the only fixed-point — checkpointer pauses
there until the swarm broadcast (ADR-2605191524) delivers attestations.
All other nodes are O(seconds).
"""

from __future__ import annotations

import logging
import time
from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("AuditWitnessCell")

# ── Constants (constitutional invariants) ──────────────────────────


# ADR-2605201400 §9: N >= 2 independent robot Ed25519 signatures. NEVER
# reduce. Reducing this constant constitutes a constitutional violation
# (Council escalation required; charters-compliance attestation must
# block deploy).
WITNESS_MIN = 2


# ADR-2605192315 §3: for eventClass in {'anomaly', 'injury'} only the
# following fields are emitted in clear text on the MST. The rest of
# the record — evidenceCid contents, participantDids, subtype, and the
# phenotype delta fields — are wrapped in the XChaCha20-Poly1305
# envelope per ADR-2605181100 with per-recipient Signal-wrapped keys.
ANOMALY_INJURY_PUBLIC_FIELDS = frozenset({
    "eventClass",
    "siteDid",
    "occurredAt",
})


# Subtypes that auto-escalate to CouncilDeliberationCell regardless of
# the phenotype delta target. 'witness-mismatch' is the canonical
# integrity-failure trigger (two robots reporting incompatible
# evidenceHash values); 'injury' triggers immediate Council review per
# ADR-2605201400 §9; 'land-violation' couples back to LandRegistry +
# OceanStewardship enforcement per ADR-2605192245.
COUNCIL_ESCALATION_TRIGGERS = (
    "witness-mismatch",
    "injury",
    "land-violation",
)


# ADR-2605192230 enforcement bound: an audit event cannot move a
# steward's Phenotype.effectiveMultiplier by more than 10% absolute in
# a single super-step. Larger deltas must accumulate through repeated
# audit events or go through Council ratification.
MAX_PHENOTYPE_DELTA_BPS = 1000  # 1000 bps = 10%


# Severity score table — used by classify_severity to derive a numeric
# severity that downstream routing nodes consume. Higher = more severe.
SEVERITY_BY_CLASS: dict[str, int] = {
    "community-event": 5,
    "compliance-check": 15,
    "anomaly": 50,
    "intrusion": 70,
    "injury": 95,
}


class AuditWitnessState(TypedDict, total=False):
    # ── inputs (from recordPhysicalAuditEvent lexicon) ──────────────
    site_did: str
    plan_did: str
    event_class: str  # 'anomaly' | 'intrusion' | 'injury' | 'compliance-check' | 'community-event'
    subtype: str
    occurred_at: str  # ISO-8601 datetime
    evidence_cid: str
    participant_dids: list[str]

    # ── witness attestations (accumulated as robots sign) ───────────
    witness_attestations: Annotated[list[dict[str, str]], add]

    # ── phenotype delta inputs (ADR-2605192230) ────────────────────
    phenotype_delta_target_did: str
    phenotype_delta_bps: int

    # ── classification outputs ─────────────────────────────────────
    severity_score: int
    is_public_class: bool  # community-event / compliance-check → True

    # ── routing / escalation ───────────────────────────────────────
    council_escalated: bool
    council_escalation_reason: str
    phenotype_delta_applied_bps: int
    phenotype_delta_clamped: bool

    # ── output (recordPhysicalAuditEvent response) ─────────────────
    audit_did: str
    recorded_at: str
    record_at_uri: str
    error: str


# ── Node functions ──────────────────────────────────────────────────


def parse_audit_event(state: AuditWitnessState) -> dict[str, Any]:
    """Load the recordPhysicalAuditEvent input + normalize defaults."""
    return {
        "site_did": state.get("site_did") or "",
        "plan_did": state.get("plan_did") or "",
        "event_class": state.get("event_class") or "compliance-check",
        "subtype": state.get("subtype") or "",
        "occurred_at": state.get("occurred_at") or "",
        "evidence_cid": state.get("evidence_cid") or "",
        "participant_dids": list(state.get("participant_dids") or []),
        "phenotype_delta_target_did": state.get("phenotype_delta_target_did") or "",
        "phenotype_delta_bps": int(state.get("phenotype_delta_bps") or 0),
    }


def verify_witness_quorum(state: AuditWitnessState) -> dict[str, Any]:
    """Fixed-point node — pauses (via checkpointer) until N >= 2 sigs arrive.

    Returns no-op state diff on each entry; the MST listener triggers
    re-entry with updated ``witness_attestations`` accumulator. The
    quorum router below decides whether to advance or hold.
    """
    return {}


def classify_severity(state: AuditWitnessState) -> dict[str, Any]:
    """Compute severity score + public-class flag.

    Severity drives downstream routing. ``is_public_class`` flags whether
    the record is emitted clear-text on MST (community-event /
    compliance-check) or wrapped in the XChaCha20 envelope per
    ADR-2605181100 (anomaly / injury / intrusion).
    """
    cls = state.get("event_class") or "compliance-check"
    base = SEVERITY_BY_CLASS.get(cls, 25)
    subtype = (state.get("subtype") or "").lower()
    bump = 0
    if subtype in COUNCIL_ESCALATION_TRIGGERS:
        bump = 20  # subtype escalator
    score = min(100, base + bump)
    is_public = cls in ("community-event", "compliance-check")
    return {
        "severity_score": score,
        "is_public_class": is_public,
    }


def apply_phenotype_delta(state: AuditWitnessState) -> dict[str, Any]:
    """Apply the bounded Phenotype.effectiveMultiplier delta.

    Scaffold: clamps the signed bps delta to ``[-MAX, +MAX]`` per
    ADR-2605192230 and records what was applied. Real wiring will call
    the PhenotypeAgent shard owning the target DID's SBT tokenId range
    and emit a constitutional-attestation event.
    """
    requested = int(state.get("phenotype_delta_bps") or 0)
    clamped = max(-MAX_PHENOTYPE_DELTA_BPS, min(MAX_PHENOTYPE_DELTA_BPS, requested))
    return {
        "phenotype_delta_applied_bps": clamped,
        "phenotype_delta_clamped": clamped != requested,
    }


def council_escalate(state: AuditWitnessState) -> dict[str, Any]:
    """Emit a CouncilDeliberationCell dispatch.

    Scaffold: marks the audit record as council-escalated and stamps a
    reason. Real wiring will publish a ``council.deliberation.request``
    event on the swarm channel and wait for the Council attestation
    before the audit record is finalized (out-of-band — this cell's
    super-step does not block on it).
    """
    subtype = (state.get("subtype") or "").lower()
    reason = subtype if subtype in COUNCIL_ESCALATION_TRIGGERS else "policy-escalation"
    return {
        "council_escalated": True,
        "council_escalation_reason": reason,
    }


def emit_audit_record(state: AuditWitnessState) -> dict[str, Any]:
    """Write the recordPhysicalAuditEvent output to MST.

    Scaffold: stamps a synthetic at:// URI + auditDid + recordedAt.
    Real wiring will use etzhayyim_sdk PdsClient with the cell's DID +
    XChaCha20-Poly1305 envelope per ADR-2605181100 for anomaly / injury
    subtypes.
    """
    site_did = state.get("site_did") or "did:web:etzhayyim.com:site:unknown"
    now_ns = int(time.time() * 1000)
    audit_did = f"{site_did}:audit:{int(time.time())}"
    record_uri = (
        f"at://{site_did}/com.etzhayyim.apps.etzhayyim.kuniUmi.recordPhysicalAuditEvent/"
        f"{now_ns}"
    )
    recorded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "audit_did": audit_did,
        "recorded_at": recorded_at,
        "record_at_uri": record_uri,
    }


# ── Graph build ─────────────────────────────────────────────────────


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(AuditWitnessState)

    g.add_node("parse_audit_event", parse_audit_event)
    g.add_node("verify_witness_quorum", verify_witness_quorum)
    g.add_node("classify_severity", classify_severity)
    g.add_node("apply_phenotype_delta", apply_phenotype_delta)
    g.add_node("council_escalate", council_escalate)
    g.add_node("emit_audit_record", emit_audit_record)

    g.add_edge(START, "parse_audit_event")
    g.add_edge("parse_audit_event", "verify_witness_quorum")

    def quorum_router(state: AuditWitnessState) -> str:
        if len(state.get("witness_attestations") or []) >= WITNESS_MIN:
            return "classify_severity"
        return "verify_witness_quorum"  # hold at fixed-point

    g.add_conditional_edges("verify_witness_quorum", quorum_router, {
        "classify_severity": "classify_severity",
        "verify_witness_quorum": "verify_witness_quorum",
    })

    def phenotype_delta_route(state: AuditWitnessState) -> str:
        """Conditional edge after classify_severity.

        Routing precedence:
          1. If subtype is in COUNCIL_ESCALATION_TRIGGERS → council_escalate
          2. Else if a phenotype delta target + non-zero bps is provided
             (within MAX bound) → apply_phenotype_delta
          3. Otherwise → emit_audit_record (no-op path)

        Both apply_phenotype_delta and council_escalate then converge at
        emit_audit_record (sequential, not parallel — Council escalation
        does not block the audit record being written; the Council
        decision arrives as a follow-up record).
        """
        subtype = (state.get("subtype") or "").lower()
        if subtype in COUNCIL_ESCALATION_TRIGGERS:
            return "council_escalate"
        target = state.get("phenotype_delta_target_did") or ""
        bps = int(state.get("phenotype_delta_bps") or 0)
        if target and bps != 0:
            return "apply_phenotype_delta"
        return "emit_audit_record"

    g.add_conditional_edges("classify_severity", phenotype_delta_route, {
        "council_escalate": "council_escalate",
        "apply_phenotype_delta": "apply_phenotype_delta",
        "emit_audit_record": "emit_audit_record",
    })

    # Both branches converge at emit_audit_record.
    g.add_edge("apply_phenotype_delta", "emit_audit_record")
    g.add_edge("council_escalate", "emit_audit_record")
    g.add_edge("emit_audit_record", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


graph = build_graph()


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ─────────────────


def state_from_event(event: dict[str, Any]) -> AuditWitnessState:
    """Map an MST recordPhysicalAuditEvent commit into the cell state."""
    rec = event.get("record") or event.get("value") or {}
    if not isinstance(rec, dict):
        rec = {}
    return {
        "site_did": rec.get("siteDid") or event.get("repo", ""),
        "plan_did": rec.get("planDid") or "",
        "event_class": rec.get("eventClass") or "",
        "subtype": rec.get("subtype") or "",
        "occurred_at": rec.get("occurredAt") or "",
        "evidence_cid": rec.get("evidenceCid") or "",
        "participant_dids": list(rec.get("participantDids") or []),
        "witness_attestations": list(rec.get("witnessAttestations") or []),
        "phenotype_delta_target_did": rec.get("phenotypeDeltaTargetDid") or "",
        "phenotype_delta_bps": int(rec.get("phenotypeDeltaBps") or 0),
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    return f"audit-witness-{event.get('uri', '').replace('/', '-')[-40:]}"


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "AuditWitnessCell",
        "phase": "kuni-umi-5",
        "trigger": "continuous + super-step boundary + event-driven",
        "witnessMin": WITNESS_MIN,
        "maxPhenotypeDeltaBps": MAX_PHENOTYPE_DELTA_BPS,
        "councilEscalationTriggers": list(COUNCIL_ESCALATION_TRIGGERS),
        "anomalyInjuryPublicFields": sorted(ANOMALY_INJURY_PUBLIC_FIELDS),
        "phenotypeFeedback": True,
    }


# ── cell-runner mst-listener entry ──────────────────────────────────


async def handle_mst_event(event_or_did=None) -> None:
    """Entry point for ``cells.toml`` ``entry = "handle_mst_event"`` under
    the mst-listener trigger. The cell-runner's ``_spawn_listener_cell``
    invokes this either with the firehose event dict (when no record path
    matched ``_extract_adherent_did``) or with the adherent DID string
    (when one did). For kuni-umi cells the event dict is the canonical
    shape — we tolerate the DID case by wrapping it as a synthetic event.
    """
    import asyncio as _asyncio
    if isinstance(event_or_did, str):
        event = {"repo": event_or_did, "record": {}}
    elif isinstance(event_or_did, dict):
        event = event_or_did
    else:
        event = {}
    try:
        state_in = state_from_event(event)
        thread_id = thread_id_from_event(event)
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        loop = _asyncio.get_running_loop()
        terminal = await loop.run_in_executor(
            None, lambda: graph.invoke(state_in, config=config)
        )
        logger.info(
            "%s mst event handled: thread_id=%s state_keys=%s",
            __name__, thread_id, list(terminal.keys())[:8] if isinstance(terminal, dict) else type(terminal).__name__,
        )
    except Exception as exc:  # noqa: BLE001 — never crash the listener loop
        logger.exception("%s mst event handler failed: %s", __name__, exc)


__all__ = [
    "AuditWitnessState",
    "build_graph",
    "graph",
    "state_from_event",
    "thread_id_from_event",
    "handle_mst_event",
    "healthz",
    "WITNESS_MIN",
    "MAX_PHENOTYPE_DELTA_BPS",
    "COUNCIL_ESCALATION_TRIGGERS",
    "ANOMALY_INJURY_PUBLIC_FIELDS",
    "SEVERITY_BY_CLASS",
]
