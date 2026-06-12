from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
class BrassPartState(TypedDict):
    part_id: str
    material_compliance: bool
    dimensional_check_passed: bool
    final_approval: bool
def check_material(state: BrassPartState):
    # Simulate material analysis logic
    return {"material_compliance": True}
def validate_specs(state: BrassPartState):
    # Validate dimensions against ISO/JIS standards
    return {"dimensional_check_passed": True}
def approve_procurement(state: BrassPartState):
    return {"final_approval": state["material_compliance"] and state["dimensional_check_passed"]}
graph = StateGraph(BrassPartState)
graph.add_node("check_material", check_material)
graph.add_node("validate_specs", validate_specs)
graph.add_node("approve", approve_procurement)
graph.set_entry_point("check_material")
graph.add_edge("check_material", "validate_specs")
graph.add_edge("validate_specs", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
