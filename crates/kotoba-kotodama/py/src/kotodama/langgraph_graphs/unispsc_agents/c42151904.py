from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalProductState(TypedDict):
    product_name: str
    is_compliant: bool
    safety_check_passed: bool

def validate_product(state: DentalProductState):
    # Perform semantic check for medical compliance
    return {"is_compliant": True, "safety_check_passed": True}

def process_procurement(state: DentalProductState):
    # Route to quality control if compliant
    return {"safety_check_passed": True}

graph = StateGraph(DentalProductState)
graph.add_node("validate", validate_product)
graph.add_node("process", process_procurement)
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph.set_entry_point("validate")
graph = graph.compile()
