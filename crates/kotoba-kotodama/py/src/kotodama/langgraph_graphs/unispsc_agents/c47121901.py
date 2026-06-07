from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SqueegeeHolsterState(TypedDict):
    material: str
    attachment_type: str
    is_compliant: bool

def validate_material(state: SqueegeeHolsterState):
    # Business logic for material durability check
    return {"is_compliant": state.get("material") in ["nylon", "heavy-duty-plastic"]}

def finish_workflow(state: SqueegeeHolsterState):
    return {"is_compliant": True}

graph = StateGraph(SqueegeeHolsterState)
graph.add_node("validate", validate_material)
graph.add_node("finalize", finish_workflow)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
