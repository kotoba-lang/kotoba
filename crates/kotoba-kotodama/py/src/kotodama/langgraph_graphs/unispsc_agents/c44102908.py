from typing import TypedDict
from langgraph.graph import StateGraph, END

class MaintenanceState(TypedDict):
    product_name: str
    requires_sds: bool
    is_validated: bool

def check_sds(state: MaintenanceState):
    return {"requires_sds": True}

def validate_product(state: MaintenanceState):
    return {"is_validated": True}

graph = StateGraph(MaintenanceState)
graph.add_node("check_sds", check_sds)
graph.add_node("validate", validate_product)
graph.add_edge("check_sds", "validate")
graph.add_edge("validate", END)
graph.set_entry_point("check_sds")
graph = graph.compile()
