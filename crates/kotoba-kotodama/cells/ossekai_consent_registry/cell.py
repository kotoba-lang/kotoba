"""
ossekai_consent_registry — Consent Registry cell.
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

class RegistryState(TypedDict, total=False):
    context: dict
    block_mute_events: list
    consent_state: dict

def _ingest_events(state: RegistryState) -> dict:
    ctx = state.get("context", {}) or {}
    return {"block_mute_events": ctx.get("block_mute_events", [])}

def _update_consent_state(state: RegistryState) -> dict:
    """Continuously update the consent state based on block/mute events."""
    events = state.get("block_mute_events", [])
    
    # In a real implementation, this would merge with the persisted state.
    # For now, we just project the current events into a state dict.
    state_updates = {}
    for event in events:
        target = event.get("target")
        action = event.get("action")
        if target and action in ["block", "mute"]:
            state_updates[target] = {"blocked": True, "reason": action}
            
    return {"consent_state": state_updates}

_g = StateGraph(RegistryState)
_g.add_node("ingest_events", _ingest_events)
_g.add_node("update_consent_state", _update_consent_state)
_g.add_edge(START, "ingest_events")
_g.add_edge("ingest_events", "update_consent_state")
_g.add_edge("update_consent_state", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

if wit_world:
    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, compiled)
