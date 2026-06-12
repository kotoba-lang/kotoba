from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    material_compliance: bool
    sterility_check: bool
    procurement_approved: bool

def validate_materials(state: DentalSupplyState):
    state['material_compliance'] = True
    return state

def check_certification(state: DentalSupplyState):
    state['sterility_check'] = True
    return state

def finalize_order(state: DentalSupplyState):
    state['procurement_approved'] = state['material_compliance'] and state['sterility_check']
    return state

graph = StateGraph(DentalSupplyState)
graph.add_node("validate", validate_materials)
graph.add_node("certify", check_certification)
graph.add_node("approve", finalize_order)
graph.set_entry_point("validate")
graph.add_edge("validate", "certify")
graph.add_edge("certify", "approve")
graph.add_edge("approve", END)

graph = graph.compile()
