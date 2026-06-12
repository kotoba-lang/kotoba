"""
ossekai_arbitrage_observer — Information arbitrage observer cell.
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

class ObserverState(TypedDict, total=False):
    context: dict
    sensor_data: list
    arbitrage_gap_report: dict

def _consume_sensors(state: ObserverState) -> dict:
    """Consume sensor stream from context."""
    ctx = state.get("context", {}) or {}
    sensor_data = ctx.get("sensor_data", [])
    return {"sensor_data": sensor_data}

def _detect_arbitrage(state: ObserverState) -> dict:
    """Detect information asymmetry pockets."""
    sensor_data = state.get("sensor_data", [])
    # Basic logic to generate a report from data
    if not sensor_data:
        return {"arbitrage_gap_report": {}}
    
    return {
        "arbitrage_gap_report": {
            "source": "ossekai_arbitrage_observer",
            "findings": [f"Gap detected in {data}" for data in sensor_data]
        }
    }

_g = StateGraph(ObserverState)
_g.add_node("consume_sensors", _consume_sensors)
_g.add_node("detect_arbitrage", _detect_arbitrage)
_g.add_edge(START, "consume_sensors")
_g.add_edge("consume_sensors", "detect_arbitrage")
_g.add_edge("detect_arbitrage", END)

compiled = _g.compile(checkpointer=KotobaCheckpointer())

if wit_world:
    class WitWorld(wit_world.WitWorld):
        def run(self, ctx_cbor: bytes) -> bytes:
            return handle_invoke(ctx_cbor, compiled)
