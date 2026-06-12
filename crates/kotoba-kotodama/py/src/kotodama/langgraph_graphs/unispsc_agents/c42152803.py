from typing import TypedDict
from langgraph.graph import StateGraph

class PeriodontalToolState(TypedDict):
    tool_id: str
    material_certified: bool
    sterilization_passed: bool

def validate_materials(state: PeriodontalToolState):
    return {"material_certified": True}

def check_sterilization_compliance(state: PeriodontalToolState):
    return {"sterilization_passed": True}

graph = StateGraph(PeriodontalToolState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("check_sterilization_compliance", check_sterilization_compliance)
graph.add_edge("validate_materials", "check_sterilization_compliance")
graph.set_entry_point("validate_materials")
graph.set_finish_point("check_sterilization_compliance")
graph = graph.compile()
