# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122610 — Laser Processing (segment 20).

Bespoke graph logic for industrial laser processing workflows, including
parameter configuration, safety verification, and execution.
"""

from __future__ import annotations

import operator
# No-op import to ensure typing works with Annotated and operator.add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122610"
UNISPSC_TITLE = "Laser Processing"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122610"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    beam_intensity_watts: float
    focal_depth_mm: float
    assist_gas_type: str
    safety_check_passed: bool


def configure_laser(state: State) -> dict[str, Any]:
    """Configures laser intensity and gas based on material specifications."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "mild_steel")).lower()
    thickness = float(inp.get("thickness_mm", 2.0))

    # Calculate power based on thickness (approx 800W per mm for steel)
    base_power = 800.0 if "steel" in material else 500.0
    required_power = base_power * thickness

    return {
        "log": [f"{UNISPSC_CODE}:configure_laser(material={material}, thickness={thickness}mm)"],
        "beam_intensity_watts": required_power,
        "focal_depth_mm": thickness * 0.5,
        "assist_gas_type": "Oxygen" if thickness > 3.0 else "Nitrogen",
    }


def verify_safety(state: State) -> dict[str, Any]:
    """Checks safety interlocks and power range limits."""
    power = state.get("beam_intensity_watts", 0.0)
    # Ensure power doesn't exceed industrial safety limits for this unit
    is_safe = 0 < power <= 10000.0

    return {
        "log": [f"{UNISPSC_CODE}:verify_safety(power_ok={is_safe})"],
        "safety_check_passed": is_safe,
    }


def execute_processing(state: State) -> dict[str, Any]:
    """Simulates the final laser processing execution."""
    if not state.get("safety_check_passed"):
        return {
            "log": [f"{UNISPSC_CODE}:execute_processing: FAILED_SAFETY"],
            "result": {"ok": False, "error": "Safety check failed"}
        }

    return {
        "log": [f"{UNISPSC_CODE}:execute_processing: COMPLETED"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "Success",
            "parameters_used": {
                "intensity": state.get("beam_intensity_watts"),
                "gas": state.get("assist_gas_type"),
                "focus": state.get("focal_depth_mm"),
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("configure", configure_laser)
_g.add_node("verify", verify_safety)
_g.add_node("execute", execute_processing)

_g.add_edge(START, "configure")
_g.add_edge("configure", "verify")
_g.add_edge("verify", "execute")
_g.add_edge("execute", END)

graph = _g.compile()
