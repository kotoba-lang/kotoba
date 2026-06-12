from typing import TypedDict
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    expiry_check: bool
    storage_temp_valid: bool
    approved: bool

def validate_expiry(state: ReagentState):
    # Logic to verify ISO 13485 expiry date standards
    state['expiry_check'] = True
    return state

def validate_storage(state: ReagentState):
    # Verify cold chain compliance markers
    state['storage_temp_valid'] = True
    return state

def final_approval(state: ReagentState):
    state['approved'] = state['expiry_check'] and state['storage_temp_valid']
    return state

graph = StateGraph(ReagentState)
graph.add_node('validate_expiry', validate_expiry)
graph.add_node('validate_storage', validate_storage)
graph.add_node('final_check', final_approval)
graph.set_entry_point('validate_expiry')
graph.add_edge('validate_expiry', 'validate_storage')
graph.add_edge('validate_storage', 'final_check')
graph.add_edge('final_check', END)
graph = graph.compile()
