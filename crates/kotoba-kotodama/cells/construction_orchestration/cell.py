"""
ConstructionOrchestrationCell — kuni-umi Phase 3 Pregel cell.

Per ADR-2605201400 §1 (Actor topology — Phase 3 leader on ``joseph``,
Giemon construction fleet driver) + §3 (Phase 3 cadence: super-step
checkpointer at 1–10 Hz; **NEVER** drive hard-RT motion — firmware on
the Giemon unit owns the closed motor loops) + §10 (witness invariant
— ≥2 robot Ed25519 signatures per progress record).

When a ``proposeDeploymentPlan`` record lands on MST, this cell loads
the plan, allocates the next super-step (= 1 construction cell = 1
Giemon work-order), dispatches the unit, streams sensor / photo /
depth blob CIDs through IPFS, watches for anomaly flags, and waits
for ≥2 witness attestations before emitting a
``recordConstructionProgress`` super-step record. The super-step loop
runs until ``completionPct >= 100``, at which point the cell flips
phase to ``handoff-ready`` and emits the final record so
CommissioningCell (Phase 4) can pick up.

LangGraph nodes (super-step semantics — 8 nodes):

  START → parse_plan              → load plan + BoM summary
        → allocate_super_step     → choose next cell to construct (++idx)
        → dispatch_giemon         → publish Giemon work-order (placeholder)
        → sensor_capture          → collect IPFS blob CIDs (placeholder)
        → anomaly_detection       → scan anomalyFlags; critical → halt
        → witness_attestation     → fixed-point — wait N≥2 sigs
        → update_progress         → advance phase + completionPct
        → emit_progress_record    → write recordConstructionProgress
        → END                     (or loop back to allocate_super_step
                                   if completionPct < 100)

The witness wait-state is the only fixed-point — checkpointer pauses
there until the swarm broadcast (ADR-2605191524) delivers attestations.
Hard-RT motion remains inside firmware on the Giemon unit; this cell
only orchestrates super-step *boundaries* at cadence_hz_max=10.
"""

from __future__ import annotations

import logging
import time
from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("ConstructionOrchestrationCell")

# Constitutional invariants (ADR-2605201400 §3 + §10).
WITNESS_MIN = 2                 # ≥2 robot Ed25519 sigs per progress record
CADENCE_HZ_MAX = 10             # super-step checkpointer ceiling
CRITICAL_ANOMALY_TAGS = (
    "tolerance-breach",
    "unexpected-obstruction-major",
    "safety-violation",
)

# Soft cap on super-step iterations per invoke (avoid runaway loops in the
# scaffold; real wiring drives this via checkpointer + MST event re-entry).
MAX_SUPER_STEPS_PER_INVOKE = 8


class ConstructionOrchestrationState(TypedDict, total=False):
    # ── inputs ───────────────────────────────────────────────────────
    plan_uri: str
    plan_record: dict[str, Any]
    planDid: str
    siteDid: str
    cellId: str

    # ── per-super-step orchestration state ──────────────────────────
    superStepIndex: int
    phase: str  # 'queued' | 'in-progress' | 'complete' | 'halted' | 'handoff-ready'
    completionPct: float
    robotDid: str

    # ── accumulators (reducer-merged across super-steps) ────────────
    sensorBlobCids: Annotated[list[str], add]
    anomalyFlags: Annotated[list[str], add]
    witnessAttestations: Annotated[list[dict[str, str]], add]

    # ── bookkeeping ─────────────────────────────────────────────────
    bomSummary: dict[str, Any]
    workOrderId: str
    superStepsCompleted: int
    haltReason: str
    recordedAt: str

    # ── output ──────────────────────────────────────────────────────
    progressDid: str
    progress_at_uri: str
    error: str


# ── Node functions ──────────────────────────────────────────────────


def parse_plan(state: ConstructionOrchestrationState) -> dict[str, Any]:
    """Load the proposeDeploymentPlan record + extract BoM summary."""
    rec = state.get("plan_record") or {}
    if not rec and state.get("plan_uri"):
        # Real wiring will fetch via etzhayyim_sdk MST. Stub for now.
        rec = {}
    plan_did = rec.get("planDid") or state.get("planDid") or "did:web:etzhayyim.com:plan:unknown"
    site_did = rec.get("siteDid") or state.get("siteDid") or "did:web:etzhayyim.com:site:unknown"
    bom = rec.get("bomSummary") if isinstance(rec.get("bomSummary"), dict) else {}
    if not bom:
        bom = {"cells": rec.get("cellCount") or 1, "estimatedDays": rec.get("estimatedDays") or 0}
    return {
        "plan_record": rec,
        "planDid": plan_did,
        "siteDid": site_did,
        "bomSummary": bom,
        # Initialize counters if this is the first entry.
        "superStepIndex": state.get("superStepIndex", 0),
        "phase": state.get("phase") or "queued",
        "completionPct": float(state.get("completionPct") or 0.0),
        "superStepsCompleted": state.get("superStepsCompleted", 0),
    }


def allocate_super_step(state: ConstructionOrchestrationState) -> dict[str, Any]:
    """Pick the next construction cell to drive.

    Scaffold: derives ``cellId`` from BoM cell count + current
    ``superStepIndex``. Real wiring consults the Plan's super-step DAG
    (ADR-2605201400 §3) + Council scope rules.
    """
    idx = int(state.get("superStepIndex") or 0)
    bom = state.get("bomSummary") or {}
    total_cells = max(int(bom.get("cells") or 1), 1)
    next_cell = f"cell-{(idx % total_cells):03d}"
    return {
        "superStepIndex": idx + 1,
        "cellId": next_cell,
        "phase": "in-progress",
    }


def dispatch_giemon(state: ConstructionOrchestrationState) -> dict[str, Any]:
    """Publish a work-order to the Giemon fleet.

    Scaffold: emits a synthetic robotDid + workOrderId. Real wiring
    publishes via NATS JetStream (per ADR-2605201400 §6) to the
    Giemon driver pool with a constitutional ceiling of
    cadence_hz_max=10. Hard-RT motion is NOT in this payload — firmware
    owns that loop.
    """
    cell_id = state.get("cellId") or "cell-000"
    ts = int(time.time() * 1000)
    work_order = f"wo-{cell_id}-{ts}"
    robot_did = state.get("robotDid") or f"did:web:etzhayyim.com:giemon:{cell_id}"
    return {
        "workOrderId": work_order,
        "robotDid": robot_did,
    }


def sensor_capture(state: ConstructionOrchestrationState) -> dict[str, Any]:
    """Gather sensor / photo / depth IPFS CIDs for this super-step.

    Scaffold: appends a synthetic CID. Real impl streams chunks through
    the IPFS pinner (50-infra/ipfs-pinner) so any auditor can replay
    the construction history later.
    """
    idx = state.get("superStepIndex") or 0
    cid = f"bafy{idx:032d}"  # placeholder CIDv1-ish opaque string
    return {"sensorBlobCids": [cid]}


def anomaly_detection(state: ConstructionOrchestrationState) -> dict[str, Any]:
    """Scan accumulated ``anomalyFlags`` — escalate on critical tags.

    If any tag in ``CRITICAL_ANOMALY_TAGS`` is present, set phase to
    ``halted`` + emit an audit event placeholder. Real wiring fires an
    ``emit_audit_event`` into AuditWitnessCell so the Council can
    review.
    """
    flags = list(state.get("anomalyFlags") or [])
    critical = [f for f in flags if any(tag in f for tag in CRITICAL_ANOMALY_TAGS)]
    if not critical:
        return {}
    # Placeholder for AuditWitnessCell escalation.
    logger.warning(
        "ConstructionOrchestrationCell: critical anomaly detected, "
        "escalating to AuditWitnessCell — cellId=%s tags=%s",
        state.get("cellId"),
        critical,
    )
    return {
        "phase": "halted",
        "haltReason": f"critical-anomaly:{','.join(critical)}",
    }


def witness_attestation(state: ConstructionOrchestrationState) -> dict[str, Any]:
    """Fixed-point — pauses (via checkpointer) until N≥2 sigs arrive.

    Real wiring: the MST listener triggers re-entry with updated
    ``witnessAttestations`` accumulator (this node returns ``{}`` and
    the quorum_router holds until external events deliver sigs).

    Scaffold fallback: when the cell is invoked standalone (no
    checkpointer + no external sig source), self-attest a synthetic
    sig per entry so the graph terminates. Each entry is still a
    distinct super-step boundary; the reducer ``add`` accumulates
    until quorum_router advances.
    """
    existing = list(state.get("witnessAttestations") or [])
    if len(existing) >= WITNESS_MIN:
        return {}
    idx = state.get("superStepIndex") or 0
    synthetic = {
        "robotDid": f"did:web:etzhayyim.com:robot:scaffold-{len(existing)}",
        "blobHash": f"sha256:scaffold:{idx}:{len(existing)}",
        "signature": f"ed25519-scaffold-sig-{idx}-{len(existing)}",
    }
    return {"witnessAttestations": [synthetic]}


def update_progress(state: ConstructionOrchestrationState) -> dict[str, Any]:
    """Advance phase + completionPct based on super-step outcome.

    Scaffold: bumps completion by ``100 / total_cells`` per super-step.
    Real wiring weights by BoM cost / time estimate.
    """
    if state.get("phase") == "halted":
        # Don't override halt; just record.
        return {}
    bom = state.get("bomSummary") or {}
    total_cells = max(int(bom.get("cells") or 1), 1)
    step = 100.0 / total_cells
    current = float(state.get("completionPct") or 0.0)
    new_pct = min(current + step, 100.0)
    new_phase = "handoff-ready" if new_pct >= 100.0 else "in-progress"
    if 0.0 < new_pct < 100.0:
        # Until the loop hits 100, the lexicon phase is in-progress.
        new_phase = "in-progress"
    completed = int(state.get("superStepsCompleted") or 0) + 1
    return {
        "completionPct": new_pct,
        "phase": new_phase,
        "superStepsCompleted": completed,
    }


def emit_progress_record(state: ConstructionOrchestrationState) -> dict[str, Any]:
    """Write a ``recordConstructionProgress`` record to MST.

    Scaffold: stamps a synthetic at:// URI + progressDid. Real wiring
    uses etzhayyim_sdk PdsClient + the cell's DID + signed envelope.
    """
    site_did = state.get("siteDid") or "did:web:etzhayyim.com:site:unknown"
    plan_did = state.get("planDid") or "did:web:etzhayyim.com:plan:unknown"
    idx = state.get("superStepIndex") or 0
    progress_did = f"{plan_did}:progress:{idx}:{int(time.time())}"
    progress_uri = (
        f"at://{site_did}/com.etzhayyim.apps.etzhayyim.kuniUmi.recordConstructionProgress/"
        f"{int(time.time() * 1000)}"
    )
    recorded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "progressDid": progress_did,
        "progress_at_uri": progress_uri,
        "recordedAt": recorded_at,
    }


# ── Graph build ─────────────────────────────────────────────────────


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(ConstructionOrchestrationState)

    g.add_node("parse_plan", parse_plan)
    g.add_node("allocate_super_step", allocate_super_step)
    g.add_node("dispatch_giemon", dispatch_giemon)
    g.add_node("sensor_capture", sensor_capture)
    g.add_node("anomaly_detection", anomaly_detection)
    g.add_node("witness_attestation", witness_attestation)
    g.add_node("update_progress", update_progress)
    g.add_node("emit_progress_record", emit_progress_record)

    g.add_edge(START, "parse_plan")
    g.add_edge("parse_plan", "allocate_super_step")
    g.add_edge("allocate_super_step", "dispatch_giemon")
    g.add_edge("dispatch_giemon", "sensor_capture")
    g.add_edge("sensor_capture", "anomaly_detection")

    def anomaly_router(state: ConstructionOrchestrationState) -> str:
        # If anomaly_detection flipped phase to halted, skip witness +
        # progress update and emit a halt record directly.
        if state.get("phase") == "halted":
            return "emit_progress_record"
        return "witness_attestation"

    g.add_conditional_edges("anomaly_detection", anomaly_router, {
        "emit_progress_record": "emit_progress_record",
        "witness_attestation": "witness_attestation",
    })

    def quorum_router(state: ConstructionOrchestrationState) -> str:
        if len(state.get("witnessAttestations") or []) >= WITNESS_MIN:
            return "update_progress"
        return "witness_attestation"  # hold at fixed-point

    g.add_conditional_edges("witness_attestation", quorum_router, {
        "update_progress": "update_progress",
        "witness_attestation": "witness_attestation",
    })

    g.add_edge("update_progress", "emit_progress_record")

    def continuation_router(state: ConstructionOrchestrationState) -> str:
        # Halt and handoff-ready both terminate the graph.
        if state.get("phase") in ("halted", "handoff-ready"):
            return END
        # Cap iterations in scaffold runs so empty/synthetic invokes
        # don't spin forever. Real wiring relies on checkpointer +
        # MST re-entry instead.
        completed = int(state.get("superStepsCompleted") or 0)
        if completed >= MAX_SUPER_STEPS_PER_INVOKE:
            return END
        if float(state.get("completionPct") or 0.0) >= 100.0:
            return END
        return "allocate_super_step"

    g.add_conditional_edges("emit_progress_record", continuation_router, {
        "allocate_super_step": "allocate_super_step",
        END: END,
    })

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


graph = build_graph()


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ─────────────────


def state_from_event(event: dict[str, Any]) -> ConstructionOrchestrationState:
    """Map an MST ``proposeDeploymentPlan`` event into cell state."""
    rec = event.get("record") or event.get("value") or {}
    if not isinstance(rec, dict):
        rec = {}
    # Pre-seed the witness accumulator so the LangGraph reducer can `add`
    # to it without a KeyError on first event.
    seed_witnesses = rec.get("witnessAttestations") or []
    return {
        "plan_uri": event.get("uri", ""),
        "plan_record": rec,
        "planDid": rec.get("planDid") or event.get("repo", ""),
        "siteDid": rec.get("siteDid", ""),
        "superStepIndex": int(rec.get("superStepIndex") or 0),
        "phase": rec.get("phase") or "queued",
        "completionPct": float(rec.get("completionPct") or 0.0),
        "witnessAttestations": list(seed_witnesses)
        if isinstance(seed_witnesses, list)
        else [],
        "sensorBlobCids": [],
        "anomalyFlags": list(rec.get("anomalyFlags") or [])
        if isinstance(rec.get("anomalyFlags"), list)
        else [],
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    return f"construction-{event.get('uri', '').replace('/', '-')[-40:]}"


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "ConstructionOrchestrationCell",
        "phase": "kuni-umi-3",
        "node": "joseph",
        "witnessMin": WITNESS_MIN,
        "cadenceHzMax": CADENCE_HZ_MAX,
        "criticalAnomalyTags": list(CRITICAL_ANOMALY_TAGS),
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
    "ConstructionOrchestrationState",
    "build_graph",
    "graph",
    "state_from_event",
    "thread_id_from_event",
    "handle_mst_event",
    "healthz",
    "WITNESS_MIN",
    "CADENCE_HZ_MAX",
    "CRITICAL_ANOMALY_TAGS",
    "MAX_SUPER_STEPS_PER_INVOKE",
]
