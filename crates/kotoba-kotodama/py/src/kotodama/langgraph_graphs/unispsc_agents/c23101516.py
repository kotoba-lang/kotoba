# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c23101516 — Milling (segment 23).
Bespoke industrial milling logic providing material processing and inspection nodes.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "23101516"
UNISPSC_TITLE = "Milling"
UNISPSC_SEGMENT = "23"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c23101516"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_type: str
    tool_diameter_mm: float
    spindle_speed_rpm: int
    tolerance_threshold: float
    quality_report: str


def setup_milling_operation(state: State) -> dict[str, Any]:
    """Initializes tool and material parameters from input."""
    inp = state.get("input") or {}
    return {
        "log": [f"{UNISPSC_CODE}:setup_milling_operation"],
        "material_type": inp.get("material", "Aluminum"),
        "tool_diameter_mm": float(inp.get("tool_dia", 10.0)),
        "spindle_speed_rpm": int(inp.get("rpm", 1500)),
        "tolerance_threshold": float(inp.get("tolerance", 0.05)),
    }


def execute_toolpath(state: State) -> dict[str, Any]:
    """Simulates the physical milling process and tool wear impact."""
    rpm = state.get("spindle_speed_rpm", 0)
    is_hard = state.get("material_type") in ("Steel", "Titanium")
    # Higher precision simulated if RPM is optimal for material hardness
    achieved_tol = 0.01 if not is_hard and rpm > 1000 else 0.08

    return {
        "log": [f"{UNISPSC_CODE}:execute_toolpath"],
        "result": {"achieved_tolerance": achieved_tol},
    }


def evaluate_quality(state: State) -> dict[str, Any]:
    """Verifies if the milled part meets the input specifications."""
    threshold = state.get("tolerance_threshold", 0.1)
    achieved = state.get("result", {}).get("achieved_tolerance", 1.0)

    status = "SUCCESS" if achieved <= threshold else "FAIL"
    report = f"Milling {status}: Achieved {achieved}mm vs required {threshold}mm"

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_quality"],
        "quality_report": report,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "tolerance": achieved,
                "status": status,
                "report": report
            },
            "ok": status == "SUCCESS"
        }
    }


_g = StateGraph(State)
_g.add_node("setup", setup_milling_operation)
_g.add_node("process", execute_toolpath)
_g.add_node("inspect", evaluate_quality)

_g.add_edge(START, "setup")
_g.add_edge("setup", "process")
_g.add_edge("process", "inspect")
_g.add_edge("inspect", END)

graph = _g.compile()
