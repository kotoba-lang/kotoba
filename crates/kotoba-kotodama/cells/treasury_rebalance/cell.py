"""
TreasuryRebalanceCell — Pregel cell that detects drift between the
current 護持金庫 three-tier NAV split and the constitutional target
ratios, and (when drift exceeds the band) submits a governance
proposal to rebalance.

Per ADR-2605172300 §3.3 + §4. The cell is the ONLY actor that proposes
asset moves; nothing here moves funds directly. Governance.propose()
plus the 72h timelock gate every execution.

Trigger: monthly cron (1st of month, 00:00 UTC)
Effect:
  - Read TreasuryMirror.tierLatest(LIQUID/RESERVE/CORPUS)
  - Read Constitution target ratios (tier_liquid_bps / tier_reserve_bps /
    tier_corpus_bps) and κ band
  - Compute observed-vs-target drift per tier
  - If max(|drift|) > drift_threshold_bps → build Safe rebalance tx +
    TreasuryMirror.updateNAV oracle update calldata
  - Submit via Governance.propose(targets, calldatas, descCid)
  - Emit com.etzhayyim.apps.payment.treasury-rebalance-proposal AT Record

Murakumo node: zebulun (leader), asher (failover replica)
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver


TIER_LIQUID = 0
TIER_RESERVE = 1
TIER_CORPUS = 2
TIER_COUNT = 3

DEFAULT_DRIFT_THRESHOLD_BPS = 500  # 5% absolute drift triggers a proposal


class TreasuryRebalanceState(TypedDict, total=False):
    # Cron context
    epoch_seconds: int

    # On-chain reads (USDC base units, 6 decimals)
    nav_liquid: int
    nav_reserve: int
    nav_corpus: int
    nav_total: int

    # Constitution targets (basis points, sum = 10_000)
    target_liquid_bps: int
    target_reserve_bps: int
    target_corpus_bps: int
    kappa_bps: int

    # Drift analysis
    observed_liquid_bps: int
    observed_reserve_bps: int
    observed_corpus_bps: int
    drift_liquid_bps: int   # signed: observed - target
    drift_reserve_bps: int
    drift_corpus_bps: int
    drift_threshold_bps: int
    needs_rebalance: bool

    # Proposal payload (only populated when needs_rebalance)
    proposal_targets: list[str]    # 0x… contract addresses
    proposal_calldatas: list[str]  # 0x… ABI-encoded calldata
    proposal_desc_cid: str         # IPFS CID of rationale doc

    # Outputs
    proposal_id: int
    proposal_tx_hash: str
    at_record_uri: str
    skipped_reason: str            # populated when no proposal emitted


def build_graph(
    checkpointer: BaseCheckpointSaver,
    treasury_port,
    constitution_port,
    governance_port,
    pds_port,
):
    g = StateGraph(TreasuryRebalanceState)

    g.add_node("load_nav", lambda s: load_nav(s, treasury_port))
    g.add_node("load_constitution", lambda s: load_constitution(s, constitution_port))
    g.add_node("compute_drift", compute_drift)
    g.add_node("propose_rebalance_payload", lambda s: propose_rebalance_payload(s, treasury_port))
    g.add_node("submit_to_governance", lambda s: submit_to_governance(s, governance_port))
    g.add_node("emit_at_record", lambda s: emit_at_record(s, pds_port))
    g.add_node("emit_skip_record", lambda s: emit_skip_record(s, pds_port))

    g.add_edge(START, "load_nav")
    g.add_edge("load_nav", "load_constitution")
    g.add_edge("load_constitution", "compute_drift")

    def drift_router(state):
        return "propose_rebalance_payload" if state.get("needs_rebalance") else "emit_skip_record"

    g.add_conditional_edges("compute_drift", drift_router)
    g.add_edge("propose_rebalance_payload", "submit_to_governance")
    g.add_edge("submit_to_governance", "emit_at_record")
    g.add_edge("emit_at_record", END)
    g.add_edge("emit_skip_record", END)

    return g.compile(checkpointer=checkpointer)


# ─── Node functions ──────────────────────────────────────────────────


def load_nav(state, port):
    """Read TreasuryMirror.tierLatest() for all three tiers."""
    liquid = port.tier_latest(TIER_LIQUID)
    reserve = port.tier_latest(TIER_RESERVE)
    corpus = port.tier_latest(TIER_CORPUS)
    return {
        **state,
        "nav_liquid": liquid,
        "nav_reserve": reserve,
        "nav_corpus": corpus,
        "nav_total": liquid + reserve + corpus,
    }


def load_constitution(state, port):
    """Read target tier ratios + κ band from Constitution."""
    return {
        **state,
        "target_liquid_bps": port.get_mutable_uint("tier_liquid_bps"),
        "target_reserve_bps": port.get_mutable_uint("tier_reserve_bps"),
        "target_corpus_bps": port.get_mutable_uint("tier_corpus_bps"),
        "kappa_bps": port.get_mutable_uint("kappa_bps"),
    }


def compute_drift(state):
    """Compute observed ratio per tier and signed drift vs target.

    If total NAV is zero (empty treasury), skip with reason. Otherwise
    flag rebalance if any tier's absolute drift exceeds the threshold.
    """
    total = state.get("nav_total", 0)
    threshold = state.get("drift_threshold_bps") or DEFAULT_DRIFT_THRESHOLD_BPS

    if total == 0:
        return {
            **state,
            "needs_rebalance": False,
            "skipped_reason": "treasury_empty",
            "drift_threshold_bps": threshold,
        }

    observed_liquid = state["nav_liquid"] * 10_000 // total
    observed_reserve = state["nav_reserve"] * 10_000 // total
    observed_corpus = state["nav_corpus"] * 10_000 // total

    drift_liquid = observed_liquid - state["target_liquid_bps"]
    drift_reserve = observed_reserve - state["target_reserve_bps"]
    drift_corpus = observed_corpus - state["target_corpus_bps"]

    max_abs = max(abs(drift_liquid), abs(drift_reserve), abs(drift_corpus))
    needs = max_abs > threshold

    out = {
        **state,
        "observed_liquid_bps": observed_liquid,
        "observed_reserve_bps": observed_reserve,
        "observed_corpus_bps": observed_corpus,
        "drift_liquid_bps": drift_liquid,
        "drift_reserve_bps": drift_reserve,
        "drift_corpus_bps": drift_corpus,
        "drift_threshold_bps": threshold,
        "needs_rebalance": needs,
    }
    if not needs:
        out["skipped_reason"] = "within_band"
    return out


def propose_rebalance_payload(state, port):
    """Build the Safe rebalance tx + TreasuryMirror.updateNAV calldata.

    The cell does NOT execute the moves — it constructs the payload
    that Governance.propose() will queue for the 72h timelock. The
    Safe-side execution happens off-chain after governance approval.
    """
    targets, calldatas, desc_cid = port.build_rebalance_proposal(
        target_liquid_bps=state["target_liquid_bps"],
        target_reserve_bps=state["target_reserve_bps"],
        target_corpus_bps=state["target_corpus_bps"],
        nav_liquid=state["nav_liquid"],
        nav_reserve=state["nav_reserve"],
        nav_corpus=state["nav_corpus"],
    )
    return {
        **state,
        "proposal_targets": targets,
        "proposal_calldatas": calldatas,
        "proposal_desc_cid": desc_cid,
    }


def submit_to_governance(state, port):
    """Governance.propose(targets, calldatas, descCid) on geth-private."""
    proposal_id, tx_hash = port.propose(
        targets=state["proposal_targets"],
        calldatas=state["proposal_calldatas"],
        desc_cid=state["proposal_desc_cid"],
    )
    return {
        **state,
        "proposal_id": proposal_id,
        "proposal_tx_hash": tx_hash,
    }


def emit_at_record(state, port):
    """Write com.etzhayyim.apps.payment.treasury-rebalance-proposal AT Record."""
    uri = port.create_record(
        collection="com.etzhayyim.apps.payment.treasury-rebalance-proposal",
        record={
            "proposalId": state["proposal_id"],
            "txHash": state["proposal_tx_hash"],
            "descCid": state["proposal_desc_cid"],
            "navLiquidUsdcMicros": state["nav_liquid"],
            "navReserveUsdcMicros": state["nav_reserve"],
            "navCorpusUsdcMicros": state["nav_corpus"],
            "navTotalUsdcMicros": state["nav_total"],
            "observedLiquidBps": state["observed_liquid_bps"],
            "observedReserveBps": state["observed_reserve_bps"],
            "observedCorpusBps": state["observed_corpus_bps"],
            "targetLiquidBps": state["target_liquid_bps"],
            "targetReserveBps": state["target_reserve_bps"],
            "targetCorpusBps": state["target_corpus_bps"],
            "driftLiquidBps": state["drift_liquid_bps"],
            "driftReserveBps": state["drift_reserve_bps"],
            "driftCorpusBps": state["drift_corpus_bps"],
            "driftThresholdBps": state["drift_threshold_bps"],
            "kappaBps": state["kappa_bps"],
            "epochSeconds": state["epoch_seconds"],
        },
    )
    return {**state, "at_record_uri": uri}


def emit_skip_record(state, port):
    """Write a skip-trail AT Record so the monthly tick is observable
    even when no proposal was needed (within band or empty treasury)."""
    uri = port.create_record(
        collection="com.etzhayyim.apps.payment.treasury-rebalance-skip",
        record={
            "reason": state.get("skipped_reason", "unknown"),
            "navLiquidUsdcMicros": state.get("nav_liquid", 0),
            "navReserveUsdcMicros": state.get("nav_reserve", 0),
            "navCorpusUsdcMicros": state.get("nav_corpus", 0),
            "navTotalUsdcMicros": state.get("nav_total", 0),
            "observedLiquidBps": state.get("observed_liquid_bps", 0),
            "observedReserveBps": state.get("observed_reserve_bps", 0),
            "observedCorpusBps": state.get("observed_corpus_bps", 0),
            "targetLiquidBps": state.get("target_liquid_bps", 0),
            "targetReserveBps": state.get("target_reserve_bps", 0),
            "targetCorpusBps": state.get("target_corpus_bps", 0),
            "driftThresholdBps": state.get("drift_threshold_bps", DEFAULT_DRIFT_THRESHOLD_BPS),
            "epochSeconds": state.get("epoch_seconds", 0),
        },
    )
    return {**state, "at_record_uri": uri}
