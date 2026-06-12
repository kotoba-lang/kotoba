from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolSpecState(TypedDict):
    tool_type: str
    material_compliance: bool
    is_verified: bool

def validate_material(state: ToolSpecState):
    return {"material_compliance": state.get("tool_type") == "Chrome-Vanadium"}

def verify_specs(state: ToolSpecState):
    return {"is_verified": state["material_compliance"]}

graph_builder = StateGraph(ToolSpecState)
graph_builder.add_node("validate", validate_material)
graph_builder.add_node("verify", verify_specs)
graph_builder.add_edge("validate", "verify")
graph_builder.add_edge("verify", END)
graph_builder.set_entry_point("validate")
graph = graph_builder.compile()
