from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_content: str
    compliance_validated: bool
    final_approval: bool

def validate_content(state: ProcurementState):
    print('Validating educational content alignment...')
    return {'compliance_validated': True}

def approve_procurement(state: ProcurementState):
    print('Finalizing procurement order...')
    return {'final_approval': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_content)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
