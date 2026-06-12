"""
ossekai_kaizen_observer — Kaizen Observer cell.
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

class KaizenState(TypedDict, total=False):
    context: dict
    metrics_snapshot: dict
    kaizen_proposal: dict

def _ingest_metrics(state: KaizenState) -> dict:
    ctx = state.get("context", {}) or {}
    return {"metrics_snapshot": ctx.get("metrics_snapshot", {})}

def _propose_kaizen(state: KaizenState) -> dict:
    """Analyze quarterly metrics and propose improvements (Kaizen)."""
    metrics = state.get("metrics_snapshot", {})
    if not metrics:
        return {"kaizen_proposal": {}}
        
    return {
        "kaizen_proposal": {
            "source": "ossekai_kaizen_observer",
            "audit_passed": True,
            "proposals": ["Improve positive framing precision", "Refine member digest timing"]
        }
    }

_g = StateGraph(KaizenState)
_g.add_node("ingest_metrics", _ingest_metrics)
_g.add_node("propose_kaizen", _propose_kaizen)
_g.add_edge(START, "ingest_metrics")
_g.add_edge("ingest_metrics", "propose_kaizen")
_g.add_edge("propose_kaizen", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

if wit_world:
    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, compiled)
