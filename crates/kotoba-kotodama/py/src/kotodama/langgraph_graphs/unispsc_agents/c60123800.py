from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MarblingState(TypedDict):
    supply_type: str
    quality_passed: bool
    compliance_checked: bool

def validate_materials(state: MarblingState):
    state['quality_passed'] = True
    print('Validating marbling ink viscosity...')
    return state

def check_compliance(state: MarblingState):
    state['compliance_checked'] = True
    print('Verifying chemical safety compliance...')
    return state

graph = StateGraph(MarblingState)
graph.add_node('validate', validate_materials)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
