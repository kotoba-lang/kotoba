from typing import TypedDict
from langgraph.graph import StateGraph, END

class NicorandilState(TypedDict):
    batch_id: str
    compliance_check: bool
    temp_valid: bool
    final_status: str

def validate_batch(state: NicorandilState):
    state['compliance_check'] = True if state.get('batch_id') else False
    return {'compliance_check': state['compliance_check']}

def check_storage_conditions(state: NicorandilState):
    state['temp_valid'] = True
    return {'temp_valid': state['temp_valid']}

def approve_procurement(state: NicorandilState):
    state['final_status'] = 'Approved' if state['compliance_check'] and state['temp_valid'] else 'Rejected'
    return {'final_status': state['final_status']}

graph = StateGraph(NicorandilState)
graph.add_node('validate', validate_batch)
graph.add_node('storage', check_storage_conditions)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'storage')
graph.add_edge('storage', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
