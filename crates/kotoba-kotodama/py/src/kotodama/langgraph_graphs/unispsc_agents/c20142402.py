# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20142402 — Proc (segment 20).

Bespoke logic for Proc (Processing / Proppants) equipment and services
within the Mining and Well Drilling Machinery segment.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20142402"
UNISPSC_TITLE = "Proc"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20142402"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Proc (Mining/Well Drilling)
    proc_request_id: str
    material_grade: str
    volume_m3: float
    verification_passed: bool


def analyze_proc_requirement(state: State) -> dict[str, Any]:
    """Analyzes the specific processing or proppant requirement."""
    inp = state.get("input") or {}
    req_id = inp.get("request_id", "REQ-20142402-001")
    grade = inp.get("grade", "Standard Mesh")
    volume = float(inp.get("volume", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_proc_requirement"],
        "proc_request_id": req_id,
        "material_grade": grade,
        "volume_m3": volume,
    }


def verify_technical_compliance(state: State) -> dict[str, Any]:
    """Verifies that the material grade meets well-stimulation standards."""
    grade = state.get("material_grade", "")
    # Simulation: specific grades are compliant for this segment
    compliant_grades = ["Standard Mesh", "High Strength", "Resin Coated"]
    is_compliant = grade in compliant_grades

    return {
        "log": [f"{UNISPSC_CODE}:verify_technical_compliance"],
        "verification_passed": is_compliant,
    }


def generate_proc_manifest(state: State) -> dict[str, Any]:
    """Generates the final procurement and processing manifest."""
    is_ok = state.get("verification_passed", False)

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "segment": UNISPSC_SEGMENT,
        "did": UNISPSC_DID,
        "request_id": state.get("proc_request_id"),
        "status": "Verified" if is_ok else "Compliance Failure",
        "ok": is_ok,
    }

    return {
        "log": [f"{UNISPSC_CODE}:generate_proc_manifest"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("analyze_proc_requirement", analyze_proc_requirement)
_g.add_node("verify_technical_compliance", verify_technical_compliance)
_g.add_node("generate_proc_manifest", generate_proc_manifest)

_g.add_edge(START, "analyze_proc_requirement")
_g.add_edge("analyze_proc_requirement", "verify_technical_compliance")
_g.add_edge("verify_technical_compliance", "generate_proc_manifest")
_g.add_edge("generate_proc_manifest", END)

graph = _g.compile()
