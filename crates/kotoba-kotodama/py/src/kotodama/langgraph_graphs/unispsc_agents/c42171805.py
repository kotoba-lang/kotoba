from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_medical_spec(state: ProcurementState):
    specs = state.get('spec_data', {})
    # Logic: Verify stainless steel grade and regulatory certification
    is_compliant = 'grade_316L' in specs.get('material', '') and 'fda_clearance' in specs
    return {'is_compliant': is_compliant}

def approval_step(state: ProcurementState):
    return {'is_compliant': state['is_compliant']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_medical_spec)
graph.add_node('approve', approval_step)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
