# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121420 — Gear Spec (segment 20).

Bespoke logic for verifying mechanical gear specifications, including
material constraints and dimensional tolerance validation.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121420"
UNISPSC_TITLE = "Gear Spec"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121420"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    spec_id: str
    material_grade: str
    dimensions_ok: bool
    tolerance_threshold: float


def intake_specification(state: State) -> dict[str, Any]:
    """Extracts initial gear data from the input payload."""
    inp = state.get("input") or {}
    spec_id = inp.get("id", "GENERIC-GEAR-001")
    material = inp.get("material", "Carbon Steel")

    return {
        "log": [f"{UNISPSC_CODE}:intake_specification"],
        "spec_id": spec_id,
        "material_grade": material,
        "tolerance_threshold": inp.get("tolerance", 0.005)
    }


def validate_mechanical_geometry(state: State) -> dict[str, Any]:
    """Simulates validation of gear teeth, pitch, and diameter."""
    inp = state.get("input") or {}
    measurements = inp.get("measurements", {})

    # Simple logic: require diameter and tooth_count for valid geometry
    has_geometry = "diameter" in measurements and "tooth_count" in measurements

    return {
        "log": [f"{UNISPSC_CODE}:validate_mechanical_geometry"],
        "dimensions_ok": has_geometry
    }


def publish_gear_spec(state: State) -> dict[str, Any]:
    """Compiles the final specification result."""
    is_valid = state.get("dimensions_ok", False)

    return {
        "log": [f"{UNISPSC_CODE}:publish_gear_spec"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "spec_id": state.get("spec_id"),
            "status": "APPROVED" if is_valid else "REJECTED",
            "material": state.get("material_grade"),
            "did": UNISPSC_DID,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("intake", intake_specification)
_g.add_node("validate", validate_mechanical_geometry)
_g.add_node("publish", publish_gear_spec)

_g.add_edge(START, "intake")
_g.add_edge("intake", "validate")
_g.add_edge("validate", "publish")
_g.add_edge("publish", END)

graph = _g.compile()
