# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25172505"
UNISPSC_TITLE = "Tube"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25172505"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Tube domain fields
    material_grade: str
    outer_diameter_mm: float
    wall_thickness_mm: float
    pressure_rating_psi: int
    inspection_passed: bool


def validate_specifications(state: State) -> dict[str, Any]:
    """Validates the physical and material specifications of the tube."""
    inp = state.get("input") or {}
    od = float(inp.get("outer_diameter_mm", 0.0))
    wt = float(inp.get("wall_thickness_mm", 0.0))
    material = str(inp.get("material_grade", "ASTM A513"))

    # Basic physical validation
    valid = od > wt and wt > 0
    return {
        "log": [f"{UNISPSC_CODE}:validate_specifications"],
        "outer_diameter_mm": od,
        "wall_thickness_mm": wt,
        "material_grade": material,
        "inspection_passed": valid,
    }


def perform_stress_test(state: State) -> dict[str, Any]:
    """Calculates theoretical burst pressure and verifies safety margins."""
    wt = state.get("wall_thickness_mm", 0.0)
    od = state.get("outer_diameter_mm", 0.0)

    # Simplified Barlow's Formula for pressure rating
    # P = (2 * S * t) / D where S is allowable stress
    material_stress = 20000  # PSI constant for simulation
    if od > 0:
        calculated_limit = int((2 * material_stress * wt) / od)
    else:
        calculated_limit = 0

    return {
        "log": [f"{UNISPSC_CODE}:perform_stress_test"],
        "pressure_rating_psi": calculated_limit,
        "inspection_passed": state.get("inspection_passed", False) and calculated_limit > 0,
    }


def issue_compliance_cert(state: State) -> dict[str, Any]:
    """Finalizes the tube's record and issues a compliance status."""
    passed = state.get("inspection_passed", False)
    return {
        "log": [f"{UNISPSC_CODE}:issue_compliance_cert"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "certified": passed,
            "metadata": {
                "material": state.get("material_grade"),
                "dimensions": f"{state.get('outer_diameter_mm')}mm OD x {state.get('wall_thickness_mm')}mm WT",
                "max_psi": state.get("pressure_rating_psi"),
            },
            "status": "CERTIFIED" if passed else "NON_COMPLIANT",
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specifications", validate_specifications)
_g.add_node("perform_stress_test", perform_stress_test)
_g.add_node("issue_compliance_cert", issue_compliance_cert)

_g.add_edge(START, "validate_specifications")
_g.add_edge("validate_specifications", "perform_stress_test")
_g.add_edge("perform_stress_test", "issue_compliance_cert")
_g.add_edge("issue_compliance_cert", END)

graph = _g.compile()
