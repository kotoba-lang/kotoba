# codemod:2605231400-unispsc-gemini-bespoke v1
import operator
from typing import Annotated, Any, TypedDict
from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24141706"
UNISPSC_TITLE = "Spool"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24141706"

class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    material_type: str
    winding_tension_newtons: float
    current_length_meters: float
    is_defective: bool
    storage_bin_id: str

def validate_spool_specs(state: State) -> dict[str, Any]:
    """Inspects input specifications for the spool material and dimensions."""
    inp = state.get("input") or {}
    material = str(inp.get("material", "industrial-filament"))
    length = float(inp.get("length_m", 500.0))
    return {
        "log": [f"{UNISPSC_CODE}:validate_spool_specs"],
        "material_type": material,
        "current_length_meters": length,
        "storage_bin_id": f"BIN-{UNISPSC_CODE}-{hash(material) % 1000}"
    }

def calculate_spool_load(state: State) -> dict[str, Any]:
    """Determines appropriate winding tension and checks for defects."""
    material = state.get("material_type", "")
    length = state.get("current_length_meters", 0.0)

    # Simple logic: heavier or more rigid materials require higher tension
    if "copper" in material.lower() or "steel" in material.lower():
        tension = 85.5
    else:
        tension = 22.0

    is_defective = length <= 0 or tension > 200.0

    return {
        "log": [f"{UNISPSC_CODE}:calculate_spool_load"],
        "winding_tension_newtons": tension,
        "is_defective": is_defective
    }

def emit_inventory_record(state: State) -> dict[str, Any]:
    """Finalizes the spool record for material handling systems."""
    is_ok = not state.get("is_defective", False)
    return {
        "log": [f"{UNISPSC_CODE}:emit_inventory_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "material": state.get("material_type"),
            "tension": state.get("winding_tension_newtons"),
            "bin": state.get("storage_bin_id"),
            "status": "OPERATIONAL" if is_ok else "QUARANTINED",
            "ok": is_ok
        }
    }

_g = StateGraph(State)
_g.add_node("validate", validate_spool_specs)
_g.add_node("process", calculate_spool_load)
_g.add_node("emit", emit_inventory_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "process")
_g.add_edge("process", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
