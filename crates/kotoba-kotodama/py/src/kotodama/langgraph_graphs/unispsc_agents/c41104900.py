from typing import TypedDict
from langgraph.graph import StateGraph, END

class FiltrationState(TypedDict):
    material_specs: dict
    compliance_checked: bool
    approved: bool

def validate_materials(state: FiltrationState):
    # Perform chemical resistance validation
    state['compliance_checked'] = True
    return state

def check_certification(state: FiltrationState):
    # Verify ISO or sterility standards
    state['approved'] = state['compliance_checked'] and True
    return state

graph = StateGraph(FiltrationState)
graph.add_node('validate', validate_materials)
graph.add_node('certify', check_certification)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)

graph = graph.compile()
