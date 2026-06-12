from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class TrimState(TypedDict):
    part_specs: dict
    validation_log: List[str]
    approved: bool

def validate_materials(state: TrimState):
    log = state.get('validation_log', [])
    specs = state.get('part_specs', {})
    status = specs.get('material') is not None
    log.append(f"Material check: {'PASSED' if status else 'FAILED'}")
    return {"validation_log": log, "approved": status}

def check_dimensions(state: TrimState):
    log = state.get('validation_log', [])
    specs = state.get('part_specs', {})
    valid = 'dimensions' in specs
    log.append(f"CAD dimension check: {'PASSED' if valid else 'FAILED'}")
    return {"validation_log": log, "approved": valid}

graph = StateGraph(TrimState)
graph.add_node("material_check", validate_materials)
graph.add_node("dim_check", check_dimensions)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "dim_check")
graph.add_edge("dim_check", END)
graph = graph.compile()
