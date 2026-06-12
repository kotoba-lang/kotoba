from typing import TypedDict
from langgraph.graph import StateGraph, END

class BladeProcurementState(TypedDict):
    blade_type: str
    material_certified: bool
    safety_check_passed: bool

def validate_materials(state: BladeProcurementState):
    state['material_certified'] = True
    return state

def check_safety_compliance(state: BladeProcurementState):
    state['safety_check_passed'] = True
    return state

graph = StateGraph(BladeProcurementState)
graph.add_node('validate', validate_materials)
graph.add_node('safety', check_safety_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
