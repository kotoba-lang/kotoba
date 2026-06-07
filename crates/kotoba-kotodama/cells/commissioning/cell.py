"""
CommissioningCell — kuni-umi Phase 4 Pregel cell.

Per ADR-2605201400 §1 (Actor topology — Phase 4 leader on ``simeon``,
hand-off to open-ot WASM PLC).

When a ``recordConstructionProgress`` record reaches phase
``handoff-ready``, this cell:

  1. Registers the commissioned utility assets with the relevant
     ``open-denki`` / ``open-gas`` / ``open-water`` / ``open-network``
     CIM lexicons (placeholder — real wiring calls into each open-*
     XRPC service).
  2. Registers steady-state control loops with ``open-ot defineLoop``
     so the WASM PLC can take over the closed-loop control surface.
  3. Runs the acceptance test (testReportCid + openOtCellFingerprints).
  4. Routes on outcome:
        - passed              → siteState = ``operational``
        - failed, recoverable → siteState = ``punch-list``
        - unrecoverable       → siteState = ``rejected``
  5. Records the steward operator hand-over; **the cell becomes
     observer-only after this point** — open-ot WASM PLC owns
     steady-state operation.
  6. Emits a ``commissionDeployment`` procedure record to MST.

LangGraph nodes (7 nodes):

  START → parse_handoff           → load planDid + handoff-ready record
        → register_utility_assets → open-* CIM record creation (stub)
        → register_open_ot_loops  → open-ot defineLoop (stub)
        → run_acceptance_test     → acceptance test + report CID (stub)
        → acceptance_router       → operational / punch-list / rejected
        → transition_to_operator  → record stewardOperatorDid hand-over
        → emit_commission_record  → write commissionDeployment → END
"""

from __future__ import annotations

import logging
import time
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("CommissioningCell")


class CommissioningState(TypedDict, total=False):
    # ── inputs ───────────────────────────────────────────────────────
    handoff_uri: str
    handoff_record: dict[str, Any]
    planDid: str
    siteDid: str

    # ── commissioning artifacts ─────────────────────────────────────
    utilityAssetDids: list[str]
    openOtLoopDids: list[str]
    acceptanceTest: dict[str, Any]
    stewardOperatorDid: str

    # ── lifecycle ───────────────────────────────────────────────────
    siteState: str  # 'operational' | 'punch-list' | 'rejected'
    observerOnly: bool
    commissionDid: str
    commissionedAt: str
    commission_at_uri: str
    error: str


# ── Node functions ──────────────────────────────────────────────────


def parse_handoff(state: CommissioningState) -> dict[str, Any]:
    """Load the handoff-ready ``recordConstructionProgress`` record."""
    rec = state.get("handoff_record") or {}
    if not isinstance(rec, dict):
        rec = {}
    plan_did = rec.get("planDid") or state.get("planDid") or "did:web:etzhayyim.com:plan:unknown"
    site_did = rec.get("siteDid") or state.get("siteDid") or "did:web:etzhayyim.com:site:unknown"
    return {
        "handoff_record": rec,
        "planDid": plan_did,
        "siteDid": site_did,
        # Default empty lists/dicts so downstream nodes can append safely.
        "utilityAssetDids": list(state.get("utilityAssetDids") or []),
        "openOtLoopDids": list(state.get("openOtLoopDids") or []),
        "acceptanceTest": dict(state.get("acceptanceTest") or {}),
    }


def register_utility_assets(state: CommissioningState) -> dict[str, Any]:
    """Create open-* CIM utility records for the commissioned assets.

    Scaffold: emits one placeholder DID per detected utility class.
    Real wiring calls into open-denki / open-gas / open-water /
    open-network XRPC services with the BoM-derived asset metadata.
    """
    site_did = state.get("siteDid") or "did:web:etzhayyim.com:site:unknown"
    existing = list(state.get("utilityAssetDids") or [])
    if existing:
        return {}  # Already populated (e.g., by event payload).
    ts = int(time.time())
    placeholders = [
        f"{site_did}:open-denki:generation-node:{ts}",
        f"{site_did}:open-network:link:{ts}",
    ]
    return {"utilityAssetDids": existing + placeholders}


def register_open_ot_loops(state: CommissioningState) -> dict[str, Any]:
    """Register steady-state control loops with open-ot defineLoop.

    Scaffold: emits one placeholder loop DID per registered utility
    asset. Real wiring calls
    ``com.etzhayyim.apps.openot.defineLoop`` per asset class.
    """
    existing = list(state.get("openOtLoopDids") or [])
    if existing:
        return {}
    site_did = state.get("siteDid") or "did:web:etzhayyim.com:site:unknown"
    assets = state.get("utilityAssetDids") or []
    ts = int(time.time())
    loops = [f"{site_did}:open-ot:loop:{i}:{ts}" for i, _ in enumerate(assets)]
    if not loops:
        # Always register at least one default monitoring loop so the
        # cell hand-over is testable.
        loops = [f"{site_did}:open-ot:loop:default:{ts}"]
    return {"openOtLoopDids": existing + loops}


def run_acceptance_test(state: CommissioningState) -> dict[str, Any]:
    """Run the acceptance test + record the IPFS test report CID.

    Scaffold: marks the test as passed with a synthetic report CID +
    open-ot WASM AOT fingerprints. Real wiring runs the integration
    suite against the live WASM PLC + records evidence.
    """
    existing = state.get("acceptanceTest") or {}
    if existing.get("passed") is not None:
        return {}  # honour caller-supplied verdict
    ts = int(time.time())
    report = {
        "passed": True,
        "testReportCid": f"bafyaccept{ts:024d}",
        "openOtCellFingerprints": [
            f"wasm-aot-fingerprint:{ts}:01",
        ],
    }
    return {"acceptanceTest": report}


def acceptance_router(state: CommissioningState) -> dict[str, Any]:
    """Map the acceptance test outcome to a lexicon ``siteState``.

    - ``passed = True``                 → ``operational``
    - ``passed = False``, recoverable   → ``punch-list``
    - ``passed = False``, unrecoverable → ``rejected``

    The lexicon's ``acceptanceTest`` dict only carries ``passed`` +
    ``testReportCid`` + ``openOtCellFingerprints``, so we treat any
    non-empty ``rejectionReason`` field as the unrecoverable signal
    (extension-friendly without breaking the schema).
    """
    test = state.get("acceptanceTest") or {}
    if test.get("passed"):
        return {"siteState": "operational"}
    rejection = test.get("rejectionReason") or ""
    if rejection and "unrecoverable" in str(rejection).lower():
        return {"siteState": "rejected"}
    return {"siteState": "punch-list"}


def transition_to_operator(state: CommissioningState) -> dict[str, Any]:
    """Record the steward operator hand-over.

    After this node the cell is observer-only — the open-ot WASM PLC
    owns steady-state operation. We flag this with ``observerOnly``
    so the cell-runner can downgrade the cell's subscription level.

    Only operational sites trigger the full hand-over; punch-list /
    rejected sites stay under construction-orchestration custody.
    """
    if state.get("siteState") != "operational":
        return {"observerOnly": False}
    steward = (
        state.get("stewardOperatorDid")
        or "did:web:etzhayyim.com:steward:unassigned"
    )
    return {
        "stewardOperatorDid": steward,
        "observerOnly": True,
    }


def emit_commission_record(state: CommissioningState) -> dict[str, Any]:
    """Write the ``commissionDeployment`` record to MST.

    Scaffold: stamps a synthetic at:// URI + commissionDid. Real
    wiring uses etzhayyim_sdk PdsClient + the cell's DID + signed
    envelope.
    """
    site_did = state.get("siteDid") or "did:web:etzhayyim.com:site:unknown"
    plan_did = state.get("planDid") or "did:web:etzhayyim.com:plan:unknown"
    ts_ms = int(time.time() * 1000)
    commission_did = f"{plan_did}:commission:{ts_ms}"
    commission_uri = (
        f"at://{site_did}/com.etzhayyim.apps.etzhayyim.kuniUmi.commissionDeployment/"
        f"{ts_ms}"
    )
    commissioned_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "commissionDid": commission_did,
        "commission_at_uri": commission_uri,
        "commissionedAt": commissioned_at,
    }


# ── Graph build ─────────────────────────────────────────────────────


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(CommissioningState)

    g.add_node("parse_handoff", parse_handoff)
    g.add_node("register_utility_assets", register_utility_assets)
    g.add_node("register_open_ot_loops", register_open_ot_loops)
    g.add_node("run_acceptance_test", run_acceptance_test)
    g.add_node("acceptance_router", acceptance_router)
    g.add_node("transition_to_operator", transition_to_operator)
    g.add_node("emit_commission_record", emit_commission_record)

    g.add_edge(START, "parse_handoff")
    g.add_edge("parse_handoff", "register_utility_assets")
    g.add_edge("register_utility_assets", "register_open_ot_loops")
    g.add_edge("register_open_ot_loops", "run_acceptance_test")
    g.add_edge("run_acceptance_test", "acceptance_router")
    g.add_edge("acceptance_router", "transition_to_operator")
    g.add_edge("transition_to_operator", "emit_commission_record")
    g.add_edge("emit_commission_record", END)

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


graph = build_graph()


# ── kotoba-kotodama cell-runner contract (ADR-2605202200) ─────────────────


def state_from_event(event: dict[str, Any]) -> CommissioningState:
    """Map an MST ``commissionDeployment`` event into the cell's TypedDict
    state.

    The commissionDeployment lexicon carries acceptanceTest and the asset
    DID lists on the record; fold them in so the acceptance_router can
    see caller-supplied failure shape (otherwise the cell ignores
    acceptanceTest.passed=False and always marks siteState=operational).
    """
    rec = event.get("record") or event.get("value") or {}
    if not isinstance(rec, dict):
        rec = {}
    acceptance_in = rec.get("acceptanceTest")
    if not isinstance(acceptance_in, dict):
        acceptance_in = {}
    return {
        "handoff_uri": event.get("uri", ""),
        "handoff_record": rec,
        "planDid": rec.get("planDid") or event.get("repo", ""),
        "siteDid": rec.get("siteDid", ""),
        "utilityAssetDids": rec.get("utilityAssetDids") or [],
        "openOtLoopDids": rec.get("openOtLoopDids") or [],
        "acceptanceTest": acceptance_in,
        "stewardOperatorDid": rec.get("stewardOperatorDid", ""),
    }


def thread_id_from_event(event: dict[str, Any]) -> str:
    return f"commissioning-{event.get('uri', '').replace('/', '-')[-40:]}"


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "CommissioningCell",
        "phase": "kuni-umi-4",
        "node": "simeon",
        "handsOffTo": "open-ot WASM PLC defineLoop",
        "observerOnlyAfterHandoff": True,
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
    "CommissioningState",
    "build_graph",
    "graph",
    "state_from_event",
    "thread_id_from_event",
    "handle_mst_event",
    "healthz",
]
