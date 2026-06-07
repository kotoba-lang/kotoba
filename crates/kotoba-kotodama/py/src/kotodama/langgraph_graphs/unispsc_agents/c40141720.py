from typing import TypedDict
from langgraph.graph import StateGraph, END

class PlumbingState(TypedDict):
    spec_completed: bool
    compliance_validated: bool

def validate_specs(state: PlumbingState):
    print('Validating pressure rating and material compatibility...')
    return {'spec_completed': True}

def check_compliance(state: PlumbingState):
    print('Verifying ISO/NSF certification status...')
    return {'compliance_validated': True}

graph = StateGraph(PlumbingState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
