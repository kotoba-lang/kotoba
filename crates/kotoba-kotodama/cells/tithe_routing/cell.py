"""
TitheRoutingCell — Pregel cell validating donation/grant payment records
and ensuring TitheRouter.route() was called correctly.

Per ADR-2605192130 (10% Tithe Redistribution).

Trigger: MST listener on `com.etzhayyim.apps.payment.sent` records
Effect:
  - Verify purpose is titheable
  - Verify TitheRouter.route() tx exists on Base L2
  - Verify 10% landed in Public Fund Safe
  - Emit `com.etzhayyim.apps.payment.tithe` counterpart record
  - Alert if SDK bypass detected (direct USDC transfer not via TitheRouter)

Murakumo node: zebulun (leader), asher (failover replica)
"""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver


Purpose = Literal[
    "donation", "kisha", "grant", "tithe", "escrow-refund",
    "internal-purchase", "internal-subscription", "internal-promo",
]


class TitheRoutingState(TypedDict, total=False):
    # Input
    payment_sent_uri: str
    payer_did: str
    recipient_did: str
    gross_amount: int  # USDC base units
    purpose: Purpose
    tx_hash: str

    # Verification
    is_titheable_purpose: bool
    tithe_router_tx_observed: bool
    public_fund_received_correctly: bool
    expected_tithe_amount: int  # = gross * 1000 / 10000
    actual_tithe_amount: int

    # Output
    tithe_record_uri: str
    sdk_bypass_alert: bool


def build_graph(checkpointer: BaseCheckpointSaver, base_port, constitution_port):
    g = StateGraph(TitheRoutingState)

    g.add_node("load_payment", load_payment)
    g.add_node("check_purpose", check_purpose)
    g.add_node("verify_router_tx", lambda s: verify_router_tx(s, base_port))
    g.add_node("verify_public_fund_receipt", lambda s: verify_public_fund_receipt(s, base_port, constitution_port))
    g.add_node("emit_tithe_record", emit_tithe_record)
    g.add_node("emit_bypass_alert", emit_bypass_alert)

    g.add_edge(START, "load_payment")
    g.add_edge("load_payment", "check_purpose")

    # If not titheable, skip
    def purpose_router(state):
        return "verify_router_tx" if state.get("is_titheable_purpose") else END

    g.add_conditional_edges("check_purpose", purpose_router)
    g.add_edge("verify_router_tx", "verify_public_fund_receipt")

    def receipt_router(state):
        if state.get("sdk_bypass_alert"):
            return "emit_bypass_alert"
        return "emit_tithe_record"

    g.add_conditional_edges("verify_public_fund_receipt", receipt_router)
    g.add_edge("emit_tithe_record", END)
    g.add_edge("emit_bypass_alert", END)

    return g.compile(checkpointer=checkpointer)


# ─── Node functions ──────────────────────────────────────────────────


def load_payment(state):
    return state


def check_purpose(state):
    """Tithe applies only to 'donation' purpose (per ADR-2605192130 §5)."""
    titheable = state.get("purpose") == "donation"
    return {**state, "is_titheable_purpose": titheable}


def verify_router_tx(state, port):
    """Verify the tx routed through TitheRouter.route() (not direct USDC transfer)."""
    # TODO: port.get_tx_logs(tx_hash) → check Routed event emitted
    return {**state, "tithe_router_tx_observed": True}


def verify_public_fund_receipt(state, port, constitution_port):
    """Verify Public Fund Safe received exactly 10% of gross."""
    # TODO: compute expected = gross * constitution.get_constant(TITHE_BPS_KEY) / 10000
    #       fetch Public Fund Safe USDC balance delta
    expected = state["gross_amount"] * 1000 // 10000
    actual = expected  # placeholder
    bypass = (actual == 0 and state["gross_amount"] > 0)
    return {
        **state,
        "expected_tithe_amount": expected,
        "actual_tithe_amount": actual,
        "public_fund_received_correctly": actual == expected,
        "sdk_bypass_alert": bypass,
    }


def emit_tithe_record(state):
    """Emit com.etzhayyim.apps.payment.tithe counterpart record."""
    return state


def emit_bypass_alert(state):
    """Emit alert record + escalate to Council Lv6+ for review."""
    return state
