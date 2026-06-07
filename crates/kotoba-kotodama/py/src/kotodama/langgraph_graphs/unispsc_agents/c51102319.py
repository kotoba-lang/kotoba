from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    is_sterile: bool
    temp_log_valid: bool
    approved: bool

def validate_batch(state: ProcurementState):
    state['is_sterile'] = True if state.get('batch_id') else False
    return state

def compliance_check(state: ProcurementState):
    state['approved'] = state['is_sterile'] and state.get('temp_log_valid', False)
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_batch)
graph.add_node('compliance', compliance_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
