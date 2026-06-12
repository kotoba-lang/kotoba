# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14111529"
UNISPSC_TITLE = "Binder"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14111529"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for office binders
    ring_configuration: str
    spine_dimension_mm: int
    material_compliance: bool
    sheet_count_limit: int


def validate_material_specs(state: State) -> dict[str, Any]:
    """Verify the physical composition and ring style of the binder."""
    inp = state.get("input") or {}
    ring_style = inp.get("ring_style", "O-Ring")
    material = inp.get("material", "Recycled PVC")

    return {
        "log": [f"{UNISPSC_CODE}:validate_material_specs"],
        "ring_configuration": ring_style,
        "material_compliance": "Recycled" in material or "Poly" in material,
    }


def calculate_capacity_thresholds(state: State) -> dict[str, Any]:
    """Determine sheet capacity based on spine width and ring geometry."""
    inp = state.get("input") or {}
    # Default 25mm spine if not provided
    width = inp.get("spine_width", 25)

    # Heuristic for sheet capacity (approx 10 sheets per mm for standard paper)
    capacity = width * 10

    return {
        "log": [f"{UNISPSC_CODE}:calculate_capacity_thresholds"],
        "spine_dimension_mm": width,
        "sheet_count_limit": capacity,
    }


def finalize_inventory_record(state: State) -> dict[str, Any]:
    """Package the binder specifications into a final asset record."""
    ring_cfg = state.get("ring_configuration")
    limit = state.get("sheet_count_limit")
    is_compliant = state.get("material_compliance", False)

    return {
        "log": [f"{UNISPSC_CODE}:finalize_inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "rings": ring_cfg,
                "spine_mm": state.get("spine_dimension_mm"),
                "max_sheets": limit,
                "eco_compliant": is_compliant,
            },
            "status": "verified" if is_compliant else "pending_review",
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_material_specs)
_g.add_node("calculate", calculate_capacity_thresholds)
_g.add_node("finalize", finalize_inventory_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "calculate")
_g.add_edge("calculate", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
