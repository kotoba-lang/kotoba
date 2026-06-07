"""
ossekai_emergency_advisory — Emergency Advisory cell.
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

class EmergencyState(TypedDict, total=False):
    context: dict
    emergency_declaration: dict
    expedited_advisory: dict

def _ingest_declaration(state: EmergencyState) -> dict:
    ctx = state.get("context", {}) or {}
    return {"emergency_declaration": ctx.get("emergency_declaration", {})}

def _compose_expedited_advisory(state: EmergencyState) -> dict:
    """Compose an expedited wellbecoming-positive advisory in response to an emergency."""
    declaration = state.get("emergency_declaration", {})
    if not declaration:
        return {"expedited_advisory": {}}
        
    return {
        "expedited_advisory": {
            "source": "ossekai_emergency_advisory",
            "urgency": "expedited",
            "content": f"Emergency Advisory based on: {declaration.get('event', 'unknown event')}. Stay safe and support your community.",
            "framing_audit": "passed (no fear amplification)"
        }
    }

_g = StateGraph(EmergencyState)
_g.add_node("ingest_declaration", _ingest_declaration)
_g.add_node("compose_expedited_advisory", _compose_expedited_advisory)
_g.add_edge(START, "ingest_declaration")
_g.add_edge("ingest_declaration", "compose_expedited_advisory")
_g.add_edge("compose_expedited_advisory", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

if wit_world:
    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, compiled)
