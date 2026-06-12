from typing import TypedDict
from langgraph.graph import StateGraph, END

class DefenseState(TypedDict):
    struct_type: str
    compliance_checked: bool
    clearance_granted: bool

def validate_defense_specs(state: DefenseState):
    # Simulate CAD/Spec validation for defense structural requirements
    state['compliance_checked'] = True
    return state

def check_export_controls(state: DefenseState):
    # Simulate regulatory/dual-use export check
    state['clearance_granted'] = True
    return state

graph = StateGraph(DefenseState)
graph.add_node('validate', validate_defense_specs)
graph.add_node('export_review', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_review')
graph.add_edge('export_review', END)
graph = graph.compile()
