from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToyProcurementState(TypedDict):
    item_name: str
    safety_certs: List[str]
    compliance_cleared: bool

def validate_safety(state: ToyProcurementState):
    required = ['ASTM F963', 'CE']
    cleared = all(cert in state.get('safety_certs', []) for cert in required)
    return {'compliance_cleared': cleared}

def approval_node(state: ToyProcurementState):
    return {'compliance_cleared': state['compliance_cleared']}

graph = StateGraph(ToyProcurementState)
graph.add_node('validate', validate_safety)
graph.add_node('approval', approval_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approval')
graph.add_edge('approval', END)
graph = graph.compile()
