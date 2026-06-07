# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c26101300 — Motor (segment 26).

This agent manages motor specifications, efficiency calculations, and
procurement validation for industrial electric motors.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "26101300"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "26"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c26101300"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    power_kw: float
    voltage_v: int
    efficiency_class: str
    specs_validated: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Inspects motor power and voltage ratings for standard compliance."""
    inp = state.get("input") or {}
    power = float(inp.get("power", 0.0))
    voltage = int(inp.get("voltage", 230))

    # Simple validation logic for industrial motors
    is_valid = power > 0 and voltage in [230, 400, 460, 690]

    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "power_kw": power,
        "voltage_v": voltage,
        "specs_validated": is_valid,
    }


def classify_efficiency(state: State) -> dict[str, Any]:
    """Determines the IE efficiency class based on provided input metadata."""
    inp = state.get("input") or {}
    eff_input = inp.get("efficiency_target", "IE1")

    # Map input to standard International Efficiency (IE) classes
    classes = {"IE1", "IE2", "IE3", "IE4"}
    eff_class = eff_input if eff_input in classes else "IE1"

    return {
        "log": [f"{UNISPSC_CODE}:classify_efficiency"],
        "efficiency_class": eff_class,
    }


def finalize_asset_record(state: State) -> dict[str, Any]:
    """Prepares the final result dictionary for the motor actor."""
    status = "VALIDATED" if state.get("specs_validated") else "INCOMPLETE"

    return {
        "log": [f"{UNISPSC_CODE}:finalize_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "power_kw": state.get("power_kw"),
            "efficiency": state.get("efficiency_class"),
            "status": status,
            "ok": state.get("specs_validated", False),
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_specifications)
_g.add_node("classify", classify_efficiency)
_g.add_node("finalize", finalize_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "classify")
_g.add_edge("classify", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
