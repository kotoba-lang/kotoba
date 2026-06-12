from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    specifications: dict
    compliance_validated: bool
    final_approval: bool

def validate_medical_safety(state: ProcurementState):
    specs = state.get('specifications', {})
    required = ['sterilization', 'material_safety']
    valid = all(k in specs for k in required)
    return {'compliance_validated': valid}

def approve_procurement(state: ProcurementState):
    return {'final_approval': state['compliance_validated']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_medical_safety)
graph.add_node('approve', approve_procurement)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')

graph = graph.compile()
