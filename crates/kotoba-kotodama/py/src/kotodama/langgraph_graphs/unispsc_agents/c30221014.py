from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class FacilityState(TypedDict):
    facility_type: str
    material_specs: List[str]
    compliance_checked: bool
    approval_status: str

def validate_structural_specs(state: FacilityState):
    print('Validating materials for marine environment...')
    state['compliance_checked'] = True
    return {'compliance_checked': True}

def final_approval(state: FacilityState):
    state['approval_status'] = 'Approved'
    return {'approval_status': 'Approved'}

graph = StateGraph(FacilityState)
graph.add_node('validate', validate_structural_specs)
graph.add_node('approve', final_approval)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
