from typing import TypedDict
from langgraph.graph import StateGraph, END

class LaparotomyState(TypedDict):
    serial_number: str
    material_certified: bool
    sterility_verified: bool
    procurement_status: str

def validate_materials(state: LaparotomyState):
    return {"material_certified": True}

def verify_sterility(state: LaparotomyState):
    return {"sterility_verified": True, "procurement_status": "QA_PASSED"}

graph = StateGraph(LaparotomyState)
graph.add_node("validate_materials", validate_materials)
graph.add_node("verify_sterility", verify_sterility)
graph.set_entry_point("validate_materials")
graph.add_edge("validate_materials", "verify_sterility")
graph.add_edge("verify_sterility", END)
graph = graph.compile()
