# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23181804 — Welding Graph (segment 23).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23181804"
UNISPSC_TITLE = "Welding Graph"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23181804"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Welding domain fields
    material: str
    joint_type: str
    weld_speed: float
    gas_flow_rate: float
    integrity_verified: bool


def plan_welding_sequence(state: State) -> dict[str, Any]:
    """Analyzes requirements and sets initial welding parameters."""
    inp = state.get("input") or {}
    material = inp.get("material", "carbon_steel")
    joint = inp.get("joint", "butt")

    # Calculate initial speed based on material density simulation
    weld_speed = 5.0 if material == "aluminum" else 3.5

    return {
        "log": [f"{UNISPSC_CODE}:plan_welding_sequence material={material} joint={joint}"],
        "material": material,
        "joint_type": joint,
        "weld_speed": weld_speed,
    }


def calibrate_equipment(state: State) -> dict[str, Any]:
    """Simulates gas flow calibration for the specific material selected."""
    material = state.get("material", "carbon_steel")
    # Higher flow rate required for non-ferrous materials
    flow_rate = 15.0 if material == "carbon_steel" else 22.5

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_equipment gas_flow={flow_rate}cfh"],
        "gas_flow_rate": flow_rate,
    }


def verify_weld_integrity(state: State) -> dict[str, Any]:
    """Performs simulated visual and ultrasonic inspection on the joint."""
    speed = state.get("weld_speed", 0.0)
    flow = state.get("gas_flow_rate", 0.0)

    # Simple validation logic: speed and flow must be within nominal ranges
    is_valid = (2.0 <= speed <= 6.0) and (flow >= 10.0)

    return {
        "log": [f"{UNISPSC_CODE}:verify_weld_integrity status={'PASS' if is_valid else 'FAIL'}"],
        "integrity_verified": is_valid,
    }


def emit_production_report(state: State) -> dict[str, Any]:
    """Finalizes the welding operation record and result payload."""
    verified = state.get("integrity_verified", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_production_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("material"),
                "joint_type": state.get("joint_type"),
                "parameters": {
                    "speed": state.get("weld_speed"),
                    "gas_flow": state.get("gas_flow_rate"),
                }
            },
            "status": "COMPLETED" if verified else "REJECTED",
            "ok": verified,
        },
    }


_g = StateGraph(State)
_g.add_node("plan", plan_welding_sequence)
_g.add_node("calibrate", calibrate_equipment)
_g.add_node("verify", verify_weld_integrity)
_g.add_node("emit", emit_production_report)

_g.add_edge(START, "plan")
_g.add_edge("plan", "calibrate")
_g.add_edge("calibrate", "verify")
_g.add_edge("verify", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
