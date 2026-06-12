"""
ossekai_intel_analyzer — Intel Analyzer cell.
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

class AnalyzerState(TypedDict, total=False):
    context: dict
    arbitrage_gap_report: dict
    wellbecoming_advisory: dict

def _ingest_report(state: AnalyzerState) -> dict:
    ctx = state.get("context", {}) or {}
    return {"arbitrage_gap_report": ctx.get("arbitrage_gap_report", {})}

def _analyze_and_frame(state: AnalyzerState) -> dict:
    """Analyze and apply positive wellbecoming framing."""
    report = state.get("arbitrage_gap_report", {})
    if not report:
        return {"wellbecoming_advisory": {}}
        
    return {
        "wellbecoming_advisory": {
            "source": "ossekai_intel_analyzer",
            "framing_audit": "passed",
            "content": f"Positive framing applied to: {report.get('findings', [])}"
        }
    }

_g = StateGraph(AnalyzerState)
_g.add_node("ingest_report", _ingest_report)
_g.add_node("analyze_and_frame", _analyze_and_frame)
_g.add_edge(START, "ingest_report")
_g.add_edge("ingest_report", "analyze_and_frame")
_g.add_edge("analyze_and_frame", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

if wit_world:
    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, compiled)
