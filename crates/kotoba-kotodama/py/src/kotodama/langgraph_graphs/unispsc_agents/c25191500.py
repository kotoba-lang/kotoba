# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25191500"
UNISPSC_TITLE = "Aviation"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25191500"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain-specific fields for Aviation mission control
    flight_id: str
    airworthiness_status: str
    fuel_load_kg: float
    manifest_count: int
    clearance_code: str


def validate_flight_readiness(state: State) -> dict[str, Any]:
    """Inspects the input for flight identity and initial airworthiness."""
    inp = state.get("input") or {}
    f_id = inp.get("flight_id", "AV-999")
    # Simulate a check on aircraft status from input data
    is_ready = inp.get("airworthy", True)

    return {
        "log": [f"{UNISPSC_CODE}:validate_flight_readiness - Flight {f_id} ready: {is_ready}"],
        "flight_id": f_id,
        "airworthiness_status": "Passed" if is_ready else "Failed"
    }


def pre_flight_processing(state: State) -> dict[str, Any]:
    """Handles fuel calculations and cargo manifest verification."""
    inp = state.get("input") or {}
    fuel = float(inp.get("fuel_load", 0.0))
    cargo_items = int(inp.get("cargo_count", 0))

    # Logic: derive clearance from flight ID and validation state
    f_id = state.get("flight_id", "AV-999")

    return {
        "log": [f"{UNISPSC_CODE}:pre_flight_processing - Fuel: {fuel}kg, Cargo: {cargo_items}"],
        "fuel_load_kg": fuel,
        "manifest_count": cargo_items,
        "clearance_code": f"ATC-{f_id}-PROCEED"
    }


def finalize_mission(state: State) -> dict[str, Any]:
    """Compiles the final aviation mission report and issues formal clearance."""
    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "flight_id": state.get("flight_id"),
        "clearance": state.get("clearance_code"),
        "status": state.get("airworthiness_status"),
        "fuel_verified": state.get("fuel_load_kg", 0) > 0,
        "ok": state.get("airworthiness_status") == "Passed",
    }
    return {
        "log": [f"{UNISPSC_CODE}:finalize_mission"],
        "result": res
    }


_g = StateGraph(State)
_g.add_node("validate", validate_flight_readiness)
_g.add_node("process", pre_flight_processing)
_g.add_node("finalize", finalize_mission)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
