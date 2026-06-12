# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23241610"
UNISPSC_TITLE = "Laser Proc"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23241610"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    beam_frequency_hz: float
    focal_depth_mm: float
    cooling_water_temp_c: float
    gas_shroud_active: bool


def check_environmental_status(state: State) -> dict[str, Any]:
    """Verifies cooling system and shroud gas state before activation."""
    inp = state.get("input") or {}
    temp = float(inp.get("target_temp", 22.5))
    shroud = inp.get("shroud_enabled", True)
    return {
        "log": [f"{UNISPSC_CODE}:check_environmental_status"],
        "cooling_water_temp_c": temp,
        "gas_shroud_active": shroud,
    }


def adjust_beam_optics(state: State) -> dict[str, Any]:
    """Sets beam frequency and focal depth based on processing requirements."""
    inp = state.get("input") or {}
    freq = float(inp.get("freq", 5000.0))
    depth = float(inp.get("depth", 2.5))
    return {
        "log": [f"{UNISPSC_CODE}:adjust_beam_optics"],
        "beam_frequency_hz": freq,
        "focal_depth_mm": depth,
    }


def process_laser_cycle(state: State) -> dict[str, Any]:
    """Executes the laser processing cycle and captures telemetry."""
    is_safe = state.get("cooling_water_temp_c", 100.0) < 30.0
    status = "nominal" if is_safe else "high_temp_warning"
    return {
        "log": [f"{UNISPSC_CODE}:process_laser_cycle:{status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "cycle_status": status,
            "params": {
                "freq": state.get("beam_frequency_hz"),
                "depth": state.get("focal_depth_mm"),
                "temp": state.get("cooling_water_temp_c"),
            },
            "ok": is_safe,
        },
    }


_g = StateGraph(State)
_g.add_node("check_env", check_environmental_status)
_g.add_node("adjust_optics", adjust_beam_optics)
_g.add_node("process_cycle", process_laser_cycle)

_g.add_edge(START, "check_env")
_g.add_edge("check_env", "adjust_optics")
_g.add_edge("adjust_optics", "process_cycle")
_g.add_edge("process_cycle", END)

graph = _g.compile()
