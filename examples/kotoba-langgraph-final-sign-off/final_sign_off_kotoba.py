"""final_sign_off_kotoba — FinalSignOffCell compiled to WASM.

Port of `20-actors/gov-municipality/cells/final_sign_off/cell.py`
onto the WASM-native `kotoba_langgraph` API so it compiles to a kotoba-node component.

Build:
    ../../scripts/build-pywasm.bb final_sign_off_kotoba.py -o final_sign_off_kotoba.wasm
"""

from __future__ import annotations
from typing import Any, TypedDict
import wit_world

from kotoba_langgraph import StateGraph, KotobaCheckpointer, START, END, handle_invoke
import kotoba_langgraph._cbor  # noqa: F401
import kotoba_langgraph._entry  # noqa: F401

class SignOffStateDict(TypedDict, total=False):
    projectId: str
    signoff_state: dict[str, Any]
    next_node: str
    permits_finalized_record: dict[str, Any]

def _initialize_state(state: SignOffStateDict) -> SignOffStateDict:
    return {"signoff_state": {"phase": "init", "projectId": state.get("projectId", "unknown"), "completionPct": 0}, "next_node": "validate"}

def _validate_inspections(state: SignOffStateDict) -> SignOffStateDict:
    return {"signoff_state": {**state.get("signoff_state", {}), "phase": "inspections_validated", "completionPct": 40}, "next_node": "request"}

def _request_authority_signature(state: SignOffStateDict) -> SignOffStateDict:
    mock_sig = {"authority_did": "did:web:tokyo.lg.jp:building", "signature": "aB3cD6eF9gH...", "occupancy_clearance": True}
    return {"signoff_state": {**state.get("signoff_state", {}), "phase": "signed", "signature": mock_sig, "completionPct": 100}, "next_node": "emit"}

def _emit_occupancy_clearance(state: SignOffStateDict) -> SignOffStateDict:
    return {"signoff_state": state.get("signoff_state", {}), "permits_finalized_record": {"projectId": state.get("signoff_state", {}).get("projectId"), "occupancy_clearance": True, "authority_signature": state.get("signoff_state", {}).get("signature", {})}, "next_node": "end"}

_g = StateGraph(SignOffStateDict)
_g.add_node("init", _initialize_state)
_g.add_node("validate", _validate_inspections)
_g.add_node("request", _request_authority_signature)
_g.add_node("emit", _emit_occupancy_clearance)
_g.add_edge(START, "init")
_g.add_edge("init", "validate")
_g.add_edge("validate", "request")
_g.add_edge("request", "emit")
_g.add_edge("emit", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

class WitWorld(wit_world.WitWorld):
    def run(self, ctx_cbor: bytes) -> bytes:
        return handle_invoke(ctx_cbor, compiled)
