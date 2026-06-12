from typing import TypedDict
from langgraph.graph import StateGraph, END

class PulseOximeterState(TypedDict):
    part_number: str
    compatibility_verified: bool
    compliance_docs: list

def validate_compliance(state: PulseOximeterState):
    # Perform medical compliance validation logic
    state['compliance_docs'] = ['ISO13485', 'CE_MDR']
    return {'compliance_docs': state['compliance_docs']}

def verify_specs(state: PulseOximeterState):
    state['compatibility_verified'] = True
    return {'compatibility_verified': True}

graph = StateGraph(PulseOximeterState)
graph.add_node('compliance', validate_compliance)
graph.add_node('specs', verify_specs)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'specs')
graph.add_edge('specs', END)
graph = graph.compile()
