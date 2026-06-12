from typing import TypedDict
from langgraph.graph import StateGraph, END

class VehicleState(TypedDict):
    specs: dict
    approved: bool

def validate_safety_compliance(state: VehicleState):
    specs = state.get('specs', {})
    is_safe = all(key in specs for key in ['load_capacity_kg', 'safety_certification_ce_iso'])
    return {'approved': is_safe}

graph = StateGraph(VehicleState)
graph.add_node('validate', validate_safety_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
