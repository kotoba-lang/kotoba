from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MiningPartsState(TypedDict):
    part_specs: dict
    validation_log: Annotated[list, add_messages]
    is_approved: bool

def validate_specs(state: MiningPartsState):
    specs = state.get("part_specs", {})
    is_valid = all(k in specs for k in ["material_grade", "tensile_strength_mpa"])
    return {"is_approved": is_valid, "validation_log": ["Specs validated"]}

def route_by_spec(state: MiningPartsState):
    return "end" if state["is_approved"] else "error"

graph = StateGraph(MiningPartsState)
graph.add_node("validate", validate_specs)
graph.add_edge("validate", END)
graph.set_entry_point("validate")
graph = graph.compile()
