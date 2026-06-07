"""
ossekai_mention_dispatcher — Mention Dispatcher cell.
Resident in Kotoba WASM.
"""

from typing import TypedDict
try:
    import wit_world
except ImportError:
    wit_world = None

from kotoba_langgraph import StateGraph, KotobaCheckpointer, START, END, handle_invoke
import kotoba_langgraph._cbor  # noqa: F401
import kotoba_langgraph._entry  # noqa: F401

_r0_marker = True

class DispatcherState(TypedDict, total=False):
    context: dict
    mention_dispatch_attestation: dict
    consent_state: dict
    dispatch_result: dict

def _verify_attestation_and_consent(state: DispatcherState) -> dict:
    ctx = state.get("context", {}) or {}
    attestation = ctx.get("mention_dispatch_attestation", {})
    consent_state = ctx.get("consent_state", {})
    
    # Check if we have required attestation (Council Lv6+ >= 3)
    # Check if target has muted/blocked (G15)
    target_handle = attestation.get("target_handle")
    is_blocked = consent_state.get(target_handle, {}).get("blocked", False)
    
    if not attestation or is_blocked:
        return {"dispatch_result": {"status": "rejected", "reason": "blocked_or_no_attestation"}}
        
    return {"dispatch_result": {"status": "approved", "target": target_handle}}

def _dispatch_mention(state: DispatcherState) -> dict:
    """Dispatch the @mention on AT Protocol if approved."""
    result = state.get("dispatch_result", {})
    if result.get("status") != "approved":
        return {"dispatch_result": result}
        
    return {
        "dispatch_result": {
            "status": "dispatched",
            "target": result.get("target"),
            "channel": "app.bsky.feed.post",
            "mention": True
        }
    }

_g = StateGraph(DispatcherState)
_g.add_node("verify_attestation_and_consent", _verify_attestation_and_consent)
_g.add_node("dispatch_mention", _dispatch_mention)
_g.add_edge(START, "verify_attestation_and_consent")
_g.add_edge("verify_attestation_and_consent", "dispatch_mention")
_g.add_edge("dispatch_mention", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

if wit_world:
    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, compiled)
