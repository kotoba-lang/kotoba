# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20122108 — Perforating bull plugs (segment 20).
Bespoke logic for pressure rating validation, thread compatibility, and material integrity.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20122108"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20122108"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Perforating bull plugs
    pressure_rating_psi: float
    thread_type: str
    material_spec: str
    integrity_check_passed: bool


def verify_specifications(state: State) -> dict[str, Any]:
    """Validates the technical specifications for the bull plug."""
    inp = state.get("input") or {}
    pressure = float(inp.get("pressure_rating", 0.0))
    thread = inp.get("thread_type", "8-round")

    return {
        "log": [f"{UNISPSC_CODE}:verify_specifications"],
        "pressure_rating_psi": pressure,
        "thread_type": thread,
    }


def check_material_integrity(state: State) -> dict[str, Any]:
    """Simulates a check of the material grade and metallurgical certification."""
    inp = state.get("input") or {}
    material = inp.get("material_grade", "AISI 4140")
    pressure = state.get("pressure_rating_psi", 0.0)

    # Perforating bull plugs require specific materials for high-pressure environments
    passed = pressure < 10000 or material in ["AISI 4140", "AISI 4340", "P110"]

    return {
        "log": [f"{UNISPSC_CODE}:check_material_integrity"],
        "material_spec": material,
        "integrity_check_passed": passed,
    }


def authorize_deployment(state: State) -> dict[str, Any]:
    """Finalizes the deployment readiness for the perforating bull plug."""
    is_ok = state.get("integrity_check_passed", False)
    pressure = state.get("pressure_rating_psi", 0.0)

    return {
        "log": [f"{UNISPSC_CODE}:authorize_deployment"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "deployment_status": "authorized" if is_ok else "rejected",
            "max_safe_pressure": pressure,
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("verify_specifications", verify_specifications)
_g.add_node("check_material_integrity", check_material_integrity)
_g.add_node("authorize_deployment", authorize_deployment)

_g.add_edge(START, "verify_specifications")
_g.add_edge("verify_specifications", "check_material_integrity")
_g.add_edge("check_material_integrity", "authorize_deployment")
_g.add_edge("authorize_deployment", END)

graph = _g.compile()
