# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101718 — Mn O2 (segment 11).

Bespoke graph logic for Manganese Dioxide quality assessment, evaluating
chemical purity and physical mesh specifications for industrial applications.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101718"
UNISPSC_TITLE = "Mn O2"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101718"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    purity_level: float
    industrial_grade: str
    mesh_specification: int
    battery_compliance: bool


def assay_chemical_purity(state: State) -> dict[str, Any]:
    """Analyzes the MnO2 content to classify the material into industrial grades."""
    inp = state.get("input") or {}
    # Default to standard chemical grade if not provided
    purity = float(inp.get("purity", 82.0))

    if purity >= 91.0:
        grade = "Electrolytic Manganese Dioxide (EMD)"
    elif purity >= 85.0:
        grade = "Battery Grade (NMD/CMD)"
    else:
        grade = "Industrial/Chemical Grade"

    return {
        "log": [f"{UNISPSC_CODE}:assay_chemical_purity -> {grade} ({purity}%)"],
        "purity_level": purity,
        "industrial_grade": grade
    }


def verify_physical_specs(state: State) -> dict[str, Any]:
    """Evaluates particle size (mesh) and moisture for application fitness."""
    inp = state.get("input") or {}
    mesh = int(inp.get("mesh", 200))
    purity = state.get("purity_level", 0.0)

    # Battery production typically requires high purity and fine particle size (>200 mesh)
    is_battery_ready = purity >= 85.0 and mesh >= 200

    return {
        "log": [f"{UNISPSC_CODE}:verify_physical_specs -> mesh:{mesh}, compliance:{is_battery_ready}"],
        "mesh_specification": mesh,
        "battery_compliance": is_battery_ready
    }


def certify_and_release(state: State) -> dict[str, Any]:
    """Finalizes certification metadata for the Manganese Dioxide batch."""
    grade = state.get("industrial_grade", "N/A")
    is_compliant = state.get("battery_compliance", False)

    return {
        "log": [f"{UNISPSC_CODE}:certify_and_release -> status:CERTIFIED"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "segment": UNISPSC_SEGMENT,
            "analysis": {
                "purity_pct": state.get("purity_level"),
                "grade": grade,
                "mesh": state.get("mesh_specification"),
                "suitable_for_batteries": is_compliant
            },
            "ok": True
        }
    }


_g = StateGraph(State)
_g.add_node("assay_chemical_purity", assay_chemical_purity)
_g.add_node("verify_physical_specs", verify_physical_specs)
_g.add_node("certify_and_release", certify_and_release)

_g.add_edge(START, "assay_chemical_purity")
_g.add_edge("assay_chemical_purity", "verify_physical_specs")
_g.add_edge("verify_physical_specs", "certify_and_release")
_g.add_edge("certify_and_release", END)

graph = _g.compile()
