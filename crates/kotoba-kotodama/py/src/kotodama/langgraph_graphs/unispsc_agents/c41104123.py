from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SputumProcurementState(TypedDict):
    item_id: str
    spec_data: dict
    is_compliant: bool
    validation_logs: List[str]

def validate_sterilization(state: SputumProcurementState) -> SputumProcurementState:
    spec = state.get('spec_data', {})
    if spec.get('sterilization_method') in ['EO', 'Gamma']:
        state['validation_logs'].append('Sterilization validated')
    else:
        state['is_compliant'] = False
    return state

def check_integrity(state: SputumProcurementState) -> SputumProcurementState:
    if state.get('spec_data', {}).get('leak_proof_rating') == 'High':
        state['validation_logs'].append('Containment confirmed')
    else:
        state['is_compliant'] = False
    return state

graph = StateGraph(SputumProcurementState)
graph.add_node('sterilization_check', validate_sterilization)
graph.add_node('integrity_check', check_integrity)
graph.set_entry_point('sterilization_check')
graph.add_edge('sterilization_check', 'integrity_check')
graph.add_edge('integrity_check', END)
graph = graph.compile()
