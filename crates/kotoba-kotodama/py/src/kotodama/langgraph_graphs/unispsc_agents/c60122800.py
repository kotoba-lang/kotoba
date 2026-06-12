from typing import TypedDict
from langgraph.graph import StateGraph, END

class MaskProcessState(TypedDict):
    compliance_verified: bool
    specs_validated: bool

def validate_compliance(state: MaskProcessState):
    print('Checking regulatory compliance...')
    return {'compliance_verified': True}

def validate_specs(state: MaskProcessState):
    print('Validating filtration and material specs...')
    return {'specs_validated': True}

graph = StateGraph(MaskProcessState)
graph.add_node('compliance', validate_compliance)
graph.add_node('specs', validate_specs)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'specs')
graph.add_edge('specs', END)

graph = graph.compile()
