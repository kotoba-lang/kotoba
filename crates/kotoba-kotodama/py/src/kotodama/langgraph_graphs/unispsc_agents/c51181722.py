from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    batch_id: str
    compliance_docs: List[str]
    temp_log_verified: bool
    approved: bool

def validate_compliance(state: DrugProcurementState):
    state['compliance_docs'] = ['CoA', 'GMP-Cert']
    return {'compliance_docs': state['compliance_docs']}

def verify_storage(state: DrugProcurementState):
    state['temp_log_verified'] = True
    return {'temp_log_verified': True}

def finalize_approval(state: DrugProcurementState):
    state['approved'] = all([state['compliance_docs'], state['temp_log_verified']])
    return {'approved': state['approved']}

graph = StateGraph(DrugProcurementState)
graph.add_node('validate', validate_compliance)
graph.add_node('storage', verify_storage)
graph.add_node('approval', finalize_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'storage')
graph.add_edge('storage', 'approval')
graph.add_edge('approval', END)
graph = graph.compile()
